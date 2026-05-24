"""Core async scanning engine — adaptive throttling, HTTP probe, live stats."""
""" I love emira btw """

import asyncio
import time
from dataclasses import dataclass, field

from .dns import DNSResolver
from .wordlists import load_wordlist
from .http import HTTPProber


@dataclass
class ScanConfig:
    target: str
    wordlists: list[str] = field(default_factory=lambda: ["default"])
    threads: int = 50
    timeout: float = 3.0
    resolvers: list[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    output_format: str = "text"
    output_file: str | None = None
    wildcard_check: bool = True
    http_probe: bool = False
    shuffle: bool = False
    dedup: bool = True
    filter_pattern: str | None = None
    # Adaptive throttling
    adaptive: bool = True
    min_threads: int = 5
    max_threads: int = 200
    rate_window: float = 2.0      # seconds to measure error rate
    error_threshold: float = 0.3  # >30% errors → slow down


@dataclass
class SubdomainResult:
    subdomain: str
    domain: str
    ips: list[str]
    cname: str | None = None
    http_status: int | None = None
    https_status: int | None = None
    http_title: str | None = None

    @property
    def fqdn(self) -> str:
        return f"{self.subdomain}.{self.domain}"


class AdaptiveThrottle:
    """Dynamically adjusts concurrency based on DNS error rate."""

    def __init__(self, config: ScanConfig):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.threads)
        self._window_start = time.monotonic()
        self._attempts = 0
        self._errors = 0
        self._current = config.threads
        self._lock = asyncio.Lock()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        return self._semaphore

    async def record(self, error: bool) -> None:
        if not self.config.adaptive:
            return
        async with self._lock:
            self._attempts += 1
            if error:
                self._errors += 1
            now = time.monotonic()
            if now - self._window_start >= self.config.rate_window and self._attempts >= 10:
                rate = self._errors / self._attempts
                if rate > self.config.error_threshold and self._current > self.config.min_threads:
                    self._current = max(self.config.min_threads, int(self._current * 0.7))
                    self._semaphore = asyncio.Semaphore(self._current)
                elif rate < 0.05 and self._current < self.config.max_threads:
                    self._current = min(self.config.max_threads, int(self._current * 1.2))
                    self._semaphore = asyncio.Semaphore(self._current)
                self._window_start = now
                self._attempts = 0
                self._errors = 0

    @property
    def current_threads(self) -> int:
        return self._current


async def _detect_wildcard(resolver: DNSResolver, domain: str) -> set[str]:
    import random, string
    ips: set[str] = set()
    for _ in range(3):
        fake = "".join(random.choices(string.ascii_lowercase, k=14))
        r = await resolver.resolve(fake, domain)
        if r:
            ips.update(r.ips)
    return ips


async def _worker(
    queue: asyncio.Queue,
    resolver: DNSResolver,
    prober: "HTTPProber | None",
    results: list[SubdomainResult],
    wildcard_ips: set[str],
    domain: str,
    throttle: AdaptiveThrottle,
    progress_cb,
) -> None:
    while True:
        subdomain = await queue.get()
        try:
            async with throttle.semaphore:
                result = await resolver.resolve(subdomain, domain)
                error = result is None

                if result and wildcard_ips and wildcard_ips.issuperset(set(result.ips)):
                    result = None  # wildcard hit

                if result:
                    if prober:
                        result = await prober.probe(result)
                    results.append(result)

                await throttle.record(error)
                progress_cb(found=result is not None, threads=throttle.current_threads)
        finally:
            queue.task_done()


async def run_scan(
    config: ScanConfig,
    progress_cb=None,
) -> list[SubdomainResult]:
    """Run subdomain scan. progress_cb(found, threads) called after each attempt."""

    if progress_cb is None:
        def progress_cb(**_): pass

    resolver = DNSResolver(resolvers=config.resolvers, timeout=config.timeout)
    prober = HTTPProber(timeout=config.timeout) if config.http_probe else None
    throttle = AdaptiveThrottle(config)

    # Load + process wordlist
    words = load_wordlist(
        config.wordlists,
        dedup=config.dedup,
        shuffle=config.shuffle,
        filter_pattern=config.filter_pattern,
    )

    # Wildcard detection
    wildcard_ips: set[str] = set()
    if config.wildcard_check:
        wildcard_ips = await _detect_wildcard(resolver, config.target)

    queue: asyncio.Queue = asyncio.Queue()
    for w in words:
        await queue.put(w)

    results: list[SubdomainResult] = []
    workers = [
        asyncio.create_task(
            _worker(queue, resolver, prober, results, wildcard_ips, config.target, throttle, progress_cb)
        )
        for _ in range(min(config.threads, len(words)))
    ]

    await queue.join()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    return sorted(results, key=lambda r: r.fqdn)
