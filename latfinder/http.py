"""HTTP/HTTPS probe for discovered subdomains."""

import asyncio
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import SubdomainResult

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


async def _fetch(url: str, timeout: float) -> tuple[int | None, str | None]:
    """Return (status_code, page_title) or (None, None) on failure."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                url.split("://")[1].split("/")[0].split(":")[0],
                443 if url.startswith("https") else 80,
                ssl=url.startswith("https"),
            ),
            timeout=timeout,
        )
        host = url.split("://")[1].split("/")[0]
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"User-Agent: lat-finder/0.2.0\r\n"
            f"Connection: close\r\n\r\n"
        )
        writer.write(request.encode())
        await writer.drain()

        raw = b""
        try:
            while True:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                if not chunk:
                    break
                raw += chunk
                if len(raw) > 32768:
                    break
        except (asyncio.TimeoutError, ConnectionResetError):
            pass
        finally:
            writer.close()

        text = raw.decode("utf-8", errors="replace")
        lines = text.split("\r\n")
        status = None
        if lines and lines[0].startswith("HTTP/"):
            try:
                status = int(lines[0].split()[1])
            except (IndexError, ValueError):
                pass

        title = None
        m = _TITLE_RE.search(text)
        if m:
            title = " ".join(m.group(1).strip().split())[:80]

        return status, title

    except Exception:
        return None, None


class HTTPProber:
    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    async def probe(self, result: "SubdomainResult") -> "SubdomainResult":
        fqdn = result.fqdn
        http_status, _ = await _fetch(f"http://{fqdn}", self.timeout)
        https_status, title = await _fetch(f"https://{fqdn}", self.timeout)

        result.http_status = http_status
        result.https_status = https_status
        result.http_title = title
        return result
