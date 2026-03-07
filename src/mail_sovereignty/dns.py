import asyncio
import logging

import dns.asyncresolver
import dns.exception
import dns.resolver

logger = logging.getLogger(__name__)

_resolvers = None

_RETRYABLE = (dns.exception.Timeout, dns.resolver.NoAnswer, dns.resolver.NoNameservers)


def make_resolvers() -> list[dns.asyncresolver.Resolver]:
    """Create a list of async resolvers pointing to different DNS servers."""
    resolvers = []
    for nameservers in [None, ["8.8.8.8", "8.8.4.4"], ["1.1.1.1", "1.0.0.1"]]:
        r = dns.asyncresolver.Resolver()
        if nameservers:
            r.nameservers = nameservers
        r.timeout = 10
        r.lifetime = 15
        resolvers.append(r)
    return resolvers


def get_resolvers() -> list[dns.asyncresolver.Resolver]:
    global _resolvers
    if _resolvers is None:
        _resolvers = make_resolvers()
    return _resolvers


async def lookup_mx(domain: str) -> list[str]:
    """Return list of MX exchange hostnames."""
    resolvers = get_resolvers()
    for i, resolver in enumerate(resolvers):
        try:
            answers = await resolver.resolve(domain, 'MX')
            return sorted(str(r.exchange).rstrip('.').lower() for r in answers)
        except dns.resolver.NXDOMAIN:
            return []
        except _RETRYABLE as e:
            logger.debug("MX %s: %s on resolver %d, retrying", domain, type(e).__name__, i)
            await asyncio.sleep(0.5)
            continue
        except Exception:
            continue
    logger.info("MX %s: all resolvers failed", domain)
    return []


async def lookup_spf(domain: str) -> str:
    """Return the SPF TXT record if found."""
    resolvers = get_resolvers()
    for i, resolver in enumerate(resolvers):
        try:
            answers = await resolver.resolve(domain, 'TXT')
            spf_records = []
            for r in answers:
                txt = b''.join(r.strings).decode('utf-8', errors='ignore')
                if txt.lower().startswith('v=spf1'):
                    spf_records.append(txt)
            if spf_records:
                return sorted(spf_records)[0]
            return ""
        except dns.resolver.NXDOMAIN:
            return ""
        except _RETRYABLE as e:
            logger.debug("SPF %s: %s on resolver %d, retrying", domain, type(e).__name__, i)
            await asyncio.sleep(0.5)
            continue
        except Exception:
            continue
    logger.info("SPF %s: all resolvers failed", domain)
    return ""


async def lookup_cname_chain(hostname: str, max_hops: int = 10) -> list[str]:
    """Follow CNAME chain for hostname. Return list of targets (empty if no CNAME)."""
    resolvers = get_resolvers()
    chain = []
    current = hostname

    for _ in range(max_hops):
        resolved = False
        for i, resolver in enumerate(resolvers):
            try:
                answers = await resolver.resolve(current, 'CNAME')
                target = str(list(answers)[0].target).rstrip('.').lower()
                chain.append(target)
                current = target
                resolved = True
                break
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                break
            except _RETRYABLE as e:
                logger.debug("CNAME %s: %s on resolver %d, retrying", current, type(e).__name__, i)
                await asyncio.sleep(0.5)
                continue
            except Exception:
                continue
        if not resolved:
            break

    return chain


async def resolve_mx_cnames(mx_hosts: list[str]) -> dict[str, str]:
    """For each MX host, follow CNAME chain. Return mapping of host -> final target (only for hosts with CNAMEs)."""
    result = {}
    for host in mx_hosts:
        chain = await lookup_cname_chain(host)
        if chain:
            result[host] = chain[-1]
    return result
