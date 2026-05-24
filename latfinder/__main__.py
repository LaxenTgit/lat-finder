"""lat-finder CLI."""

import asyncio
import sys
import argparse

from latfinder import __version__
from latfinder.core import ScanConfig, SubdomainResult, run_scan, _detect_wildcard
from latfinder.dns import DNSResolver
from latfinder.wordlists import load_wordlist
from latfinder.output import ResultFormatter, ProgressBar

BANNER = (
    "\033[36m\033[1m"
    "  _       _     ___ _           _\n"
    " | |     | |   |  _(_)_ __   __| | ___ _ __\n"
    " | |     | |   | |_| | '_ \\ / _` |/ _ \\ '__|\n"
    " | |___  | |___|  _| | | | | (_| |  __/ |\n"
    " |_____| |_____|_| |_|_| |_|\\__,_|\\___|_|\n"
    "\033[0m"
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lat-finder",
        description="Fast async subdomain discovery tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("domain", help="Target domain (e.g. example.com)")

    g_wl = p.add_argument_group("wordlist")
    g_wl.add_argument("-w", "--wordlist", action="append", default=[],
                      metavar="FILE", dest="wordlists",
                      help="Wordlist path or built-in name; repeatable for multiple lists")
    g_wl.add_argument("--shuffle", action="store_true", help="Randomize wordlist order")
    g_wl.add_argument("--no-dedup", action="store_true", help="Keep duplicate entries")
    g_wl.add_argument("--filter", metavar="REGEX", help="Only test words matching regex")

    g_scan = p.add_argument_group("scan")
    g_scan.add_argument("-t", "--threads", type=int, default=50, metavar="N")
    g_scan.add_argument("--timeout", type=float, default=3.0)
    g_scan.add_argument("-r", "--resolvers", default="8.8.8.8,1.1.1.1")
    g_scan.add_argument("--no-adaptive", action="store_true",
                        help="Disable adaptive thread throttling")
    g_scan.add_argument("--no-wildcard", action="store_true")
    g_scan.add_argument("--http-probe", action="store_true",
                        help="Probe found subdomains over HTTP/HTTPS")

    g_out = p.add_argument_group("output")
    g_out.add_argument("-o", "--output", metavar="FILE")
    g_out.add_argument("-f", "--format", choices=["text", "json", "csv"], default="text")

    p.add_argument("-v", "--version", action="version", version=f"lat-finder {__version__}")
    return p


async def main_async(args: argparse.Namespace) -> int:
    print(BANNER)

    wordlists = args.wordlists or ["default"]
    config = ScanConfig(
        target=args.domain,
        wordlists=wordlists,
        threads=args.threads,
        timeout=args.timeout,
        resolvers=args.resolvers.split(","),
        output_format=args.format,
        output_file=args.output,
        wildcard_check=not args.no_wildcard,
        http_probe=args.http_probe,
        shuffle=args.shuffle,
        dedup=not args.no_dedup,
        filter_pattern=args.filter,
        adaptive=not args.no_adaptive,
    )

    formatter = ResultFormatter(config.output_format, config.output_file)

    try:
        from latfinder.wordlists import load_wordlist
        words = load_wordlist(config.wordlists, dedup=config.dedup,
                              shuffle=config.shuffle, filter_pattern=config.filter_pattern)
    except FileNotFoundError as e:
        formatter.error(str(e))
        return 1

    resolver = DNSResolver(resolvers=config.resolvers, timeout=config.timeout)
    wildcard_ips: set[str] = set()
    if config.wildcard_check:
        wildcard_ips = await _detect_wildcard(resolver, config.target)

    formatter.print_header(config.target, len(words), config.threads, wildcard_ips)

    bar = ProgressBar(total=len(words), target=config.target)

    found_buf: list[SubdomainResult] = []

    def on_progress(found: bool, threads: int) -> None:
        bar.update(found=found, threads=threads)
        # Flush buffered results above the progress bar
        while found_buf:
            r = found_buf.pop(0)
            bar.finish()
            formatter.print_result(r)

    # Patch run_scan to also feed found_buf via callback
    async def patched_progress(found_result, **kwargs):
        if found_result:
            found_buf.append(found_result)
        on_progress(**kwargs)

    # We need per-result callback; re-implement scan inline to intercept results
    from latfinder.core import AdaptiveThrottle, _worker
    from latfinder.http import HTTPProber
    import asyncio

    throttle = AdaptiveThrottle(config)
    prober = HTTPProber(timeout=config.timeout) if config.http_probe else None
    results: list[SubdomainResult] = []

    def progress_cb(found: bool, threads: int) -> None:
        bar.update(found=found, threads=threads)

    queue: asyncio.Queue = asyncio.Queue()
    for w in words:
        await queue.put(w)

    workers = [
        asyncio.create_task(
            _worker(queue, resolver, prober, results, wildcard_ips,
                    config.target, throttle, progress_cb)
        )
        for _ in range(min(config.threads, len(words)))
    ]

    # Print results as they arrive while workers are running
    prev_count = 0
    while not queue.empty() or any(not t.done() for t in workers):
        await asyncio.sleep(0.15)
        while prev_count < len(results):
            bar.finish()
            formatter.print_result(results[prev_count])
            prev_count += 1

    await queue.join()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    # Print any remaining
    while prev_count < len(results):
        bar.finish()
        formatter.print_result(results[prev_count])
        prev_count += 1

    bar.finish()
    formatter.summary()
    formatter.close()
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
