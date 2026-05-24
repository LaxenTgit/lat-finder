"""Rich terminal output with live progress bar and result table."""

import json
import sys
import time
from typing import TextIO, TYPE_CHECKING

if TYPE_CHECKING:
    from .core import SubdomainResult

# ANSI
_R = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_MAGENTA = "\033[35m"
_BG_DARK = "\033[48;5;235m"
_ERASE = "\033[2K\r"

# HTTP status colors
def _status_color(code: int | None) -> str:
    if code is None:       return _DIM
    if code < 300:         return _GREEN
    if code < 400:         return _CYAN
    if code < 500:         return _YELLOW
    return _RED

def _status_str(code: int | None) -> str:
    return f"{_status_color(code)}{code or '---'}{_R}"


# ── Progress bar ───────────────────────────────────────────────────────────────
class ProgressBar:
    BAR_WIDTH = 30

    def __init__(self, total: int, target: str):
        self.total = total
        self.target = target
        self._done = 0
        self._found = 0
        self._threads = 0
        self._start = time.monotonic()
        self._last_draw = 0.0

    def update(self, found: bool, threads: int) -> None:
        self._done += 1
        if found:
            self._found += 1
        self._threads = threads
        now = time.monotonic()
        if now - self._last_draw >= 0.08:   # ~12 fps
            self._draw()
            self._last_draw = now

    def _draw(self) -> None:
        pct = self._done / self.total if self.total else 0
        filled = int(self.BAR_WIDTH * pct)
        bar = f"{_GREEN}{'█' * filled}{_DIM}{'░' * (self.BAR_WIDTH - filled)}{_R}"
        elapsed = time.monotonic() - self._start
        rps = self._done / elapsed if elapsed > 0 else 0
        eta = (self.total - self._done) / rps if rps > 0 else 0

        line = (
            f"{_ERASE}"
            f"{_BOLD}{_CYAN}◈{_R} "
            f"[{bar}] "
            f"{_BOLD}{int(pct*100):3d}%{_R}  "
            f"{_DIM}{self._done}/{self.total}{_R}  "
            f"{_GREEN}✓{self._found}{_R}  "
            f"{_YELLOW}⚡{self._threads}t{_R}  "
            f"{_DIM}{rps:.0f}r/s  eta {eta:.0f}s{_R}"
        )
        sys.stderr.write(line)
        sys.stderr.flush()

    def finish(self) -> None:
        sys.stderr.write(f"{_ERASE}")
        sys.stderr.flush()


# ── Formatter ─────────────────────────────────────────────────────────────────
class ResultFormatter:
    def __init__(self, fmt: str = "text", output_file: str | None = None):
        self.fmt = fmt
        self._file: TextIO = open(output_file, "w") if output_file else sys.stdout
        self._results: list["SubdomainResult"] = []
        self._col_w = 0  # track longest fqdn for alignment

    def print_result(self, result: "SubdomainResult") -> None:
        self._results.append(result)
        self._col_w = max(self._col_w, len(result.fqdn))

        if self.fmt == "text":
            self._print_text(result)
        elif self.fmt == "json":
            print(json.dumps(self._to_dict(result)), file=self._file)
        elif self.fmt == "csv":
            print(
                f"{result.fqdn},{','.join(result.ips)},"
                f"{result.cname or ''},{result.http_status or ''},"
                f"{result.https_status or ''},{result.http_title or ''}",
                file=self._file,
            )

    def _print_text(self, r: "SubdomainResult") -> None:
        fqdn_col = f"{_BOLD}{r.fqdn}{_R}".ljust(self._col_w + 20)
        ips = f"{_YELLOW}[{', '.join(r.ips)}]{_R}" if r.ips else ""
        cname = f"  {_DIM}→ {r.cname}{_R}" if r.cname else ""

        http_part = ""
        if r.http_status is not None or r.https_status is not None:
            h  = f"http:{_status_str(r.http_status)}"
            hs = f"https:{_status_str(r.https_status)}"
            title = f"  {_DIM}\"{r.http_title}\"{_R}" if r.http_title else ""
            http_part = f"  {_DIM}│{_R} {h} {hs}{title}"

        print(f"{_GREEN}✓{_R} {fqdn_col} {ips}{cname}{http_part}", file=self._file)

    def _to_dict(self, r: "SubdomainResult") -> dict:
        return {
            "fqdn": r.fqdn,
            "subdomain": r.subdomain,
            "domain": r.domain,
            "ips": r.ips,
            "cname": r.cname,
            "http_status": r.http_status,
            "https_status": r.https_status,
            "http_title": r.http_title,
        }

    def print_header(self, target: str, wordlist_size: int, threads: int,
                     wildcard_ips: set[str]) -> None:
        print(f"\n{_BG_DARK}{_BOLD}  lat-finder  {_R}", file=sys.stderr)
        print(f"{_CYAN}  target   {_R}{_BOLD}{target}{_R}", file=sys.stderr)
        print(f"{_CYAN}  words    {_R}{wordlist_size:,}", file=sys.stderr)
        print(f"{_CYAN}  threads  {_R}{threads}", file=sys.stderr)
        if wildcard_ips:
            print(f"{_YELLOW}  wildcard {_R}{', '.join(wildcard_ips)}  (filtering)", file=sys.stderr)
        print(file=sys.stderr)

    def summary(self) -> None:
        count = len(self._results)
        print(
            f"\n{_BOLD}  {_GREEN}✓{_R}{_BOLD} {count} subdomain(s) found{_R}\n",
            file=sys.stderr,
        )

    def warn(self, msg: str)  -> None: print(f"{_YELLOW}[!] {msg}{_R}", file=sys.stderr)
    def info(self, msg: str)  -> None: print(f"{_CYAN}[*] {msg}{_R}", file=sys.stderr)
    def error(self, msg: str) -> None: print(f"{_RED}[✗] {msg}{_R}", file=sys.stderr)

    def close(self) -> None:
        if self._file is not sys.stdout:
            self._file.close()
