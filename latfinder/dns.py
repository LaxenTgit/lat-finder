"""Async DNS resolution with multiple resolver support."""

import asyncio
import dns.asyncresolver
import dns.exception
import dns.rdatatype

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core import SubdomainResult


class DNSResolver:
    def __init__(self, resolvers: list[str], timeout: float = 3.0):
        self.resolvers = resolvers
        self.timeout = timeout
        self._resolver = dns.asyncresolver.Resolver()
        self._resolver.nameservers = resolvers
        self._resolver.timeout = timeout
        self._resolver.lifetime = timeout

    async def resolve(self, subdomain: str, domain: str) -> "SubdomainResult | None":
        from .core import SubdomainResult

        fqdn = f"{subdomain}.{domain}"
        ips: list[str] = []
        cname: str | None = None

        try:
            # Try A record
            answer = await self._resolver.resolve(fqdn, "A")
            ips = [r.address for r in answer]
        except (dns.exception.DNSException, Exception):
            pass

        if not ips:
            try:
                # Try CNAME
                answer = await self._resolver.resolve(fqdn, "CNAME")
                cname = str(answer[0].target).rstrip(".")
                # Resolve CNAME target
                try:
                    a_answer = await self._resolver.resolve(cname, "A")
                    ips = [r.address for r in a_answer]
                except Exception:
                    ips = []
            except (dns.exception.DNSException, Exception):
                return None

        if not ips and not cname:
            return None

        return SubdomainResult(
            subdomain=subdomain,
            domain=domain,
            ips=ips,
            cname=cname,
        )
