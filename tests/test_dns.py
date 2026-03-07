import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from mail_sovereignty.dns import get_resolvers, lookup_cname_chain, lookup_mx, lookup_spf, make_resolvers, resolve_mx_cnames


@pytest.fixture(autouse=True)
def reset_dns_globals():
    """Reset module-level globals before each test."""
    import mail_sovereignty.dns as dns_mod
    dns_mod._resolvers = None


class TestMakeResolvers:
    def test_returns_list_of_three(self):
        resolvers = make_resolvers()
        assert isinstance(resolvers, list)
        assert len(resolvers) == 3

    def test_first_uses_system_dns(self):
        resolvers = make_resolvers()
        # First resolver uses system defaults (no explicit nameservers set by us)
        assert resolvers[0] is not resolvers[1]


class TestGetResolvers:
    def test_lazy_init(self):
        import mail_sovereignty.dns as dns_mod
        assert dns_mod._resolvers is None

        with patch("mail_sovereignty.dns.make_resolvers") as mock:
            mock.return_value = ["r1", "r2", "r3"]
            result = get_resolvers()
        assert result == ["r1", "r2", "r3"]
        assert dns_mod._resolvers is not None

    def test_cached(self):
        import mail_sovereignty.dns as dns_mod
        dns_mod._resolvers = ["cached"]
        assert get_resolvers() == ["cached"]


class TestLookupMx:
    async def test_success(self):
        mock_rr = MagicMock()
        mock_rr.exchange = "mail.example.ch."
        mock_answer = [mock_rr]

        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await lookup_mx("example.ch")
        assert result == ["mail.example.ch"]

    async def test_nxdomain_returns_empty(self):
        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(side_effect=dns.resolver.NXDOMAIN())

        mock_resolver2 = AsyncMock()
        mock_resolver2.resolve = AsyncMock(return_value=[])

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver, mock_resolver2]):
            result = await lookup_mx("nonexistent.ch")
        assert result == []
        # NXDOMAIN is terminal — second resolver should NOT be called
        mock_resolver2.resolve.assert_not_called()

    async def test_timeout_retries_next_resolver(self):
        mock_rr = MagicMock()
        mock_rr.exchange = "mail.example.ch."
        mock_answer = [mock_rr]

        mock_resolver1 = AsyncMock()
        mock_resolver1.resolve = AsyncMock(side_effect=dns.exception.Timeout())

        mock_resolver2 = AsyncMock()
        mock_resolver2.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver1, mock_resolver2]):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await lookup_mx("example.ch")
        assert result == ["mail.example.ch"]

    async def test_noanswer_retries_next_resolver(self):
        mock_rr = MagicMock()
        mock_rr.exchange = "mail.example.ch."
        mock_answer = [mock_rr]

        mock_resolver1 = AsyncMock()
        mock_resolver1.resolve = AsyncMock(side_effect=dns.resolver.NoAnswer())

        mock_resolver2 = AsyncMock()
        mock_resolver2.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver1, mock_resolver2]):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await lookup_mx("example.ch")
        assert result == ["mail.example.ch"]

    async def test_nonameservers_retries(self):
        mock_rr = MagicMock()
        mock_rr.exchange = "mail.example.ch."
        mock_answer = [mock_rr]

        mock_resolver1 = AsyncMock()
        mock_resolver1.resolve = AsyncMock(side_effect=dns.resolver.NoNameservers())

        mock_resolver2 = AsyncMock()
        mock_resolver2.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver1, mock_resolver2]):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await lookup_mx("example.ch")
        assert result == ["mail.example.ch"]

    async def test_all_resolvers_fail(self):
        resolvers = []
        for _ in range(3):
            r = AsyncMock()
            r.resolve = AsyncMock(side_effect=dns.exception.Timeout())
            resolvers.append(r)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=resolvers):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await lookup_mx("example.ch")
        assert result == []

    async def test_generic_exception_retries(self):
        mock_rr = MagicMock()
        mock_rr.exchange = "mail.example.ch."
        mock_answer = [mock_rr]

        mock_resolver1 = AsyncMock()
        mock_resolver1.resolve = AsyncMock(side_effect=RuntimeError("boom"))

        mock_resolver2 = AsyncMock()
        mock_resolver2.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver1, mock_resolver2]):
            result = await lookup_mx("example.ch")
        assert result == ["mail.example.ch"]


class TestLookupSpf:
    async def test_success(self):
        mock_rr = MagicMock()
        mock_rr.strings = [b"v=spf1 include:example.ch -all"]
        mock_answer = [mock_rr]

        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await lookup_spf("example.ch")
        assert result == "v=spf1 include:example.ch -all"

    async def test_nxdomain_returns_empty(self):
        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(side_effect=dns.resolver.NXDOMAIN())

        mock_resolver2 = AsyncMock()

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver, mock_resolver2]):
            result = await lookup_spf("nonexistent.ch")
        assert result == ""
        mock_resolver2.resolve.assert_not_called()

    async def test_timeout_retries_next_resolver(self):
        mock_rr = MagicMock()
        mock_rr.strings = [b"v=spf1 include:example.ch -all"]
        mock_answer = [mock_rr]

        mock_resolver1 = AsyncMock()
        mock_resolver1.resolve = AsyncMock(side_effect=dns.exception.Timeout())

        mock_resolver2 = AsyncMock()
        mock_resolver2.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver1, mock_resolver2]):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await lookup_spf("example.ch")
        assert result == "v=spf1 include:example.ch -all"

    async def test_all_resolvers_fail(self):
        resolvers = []
        for _ in range(3):
            r = AsyncMock()
            r.resolve = AsyncMock(side_effect=dns.exception.Timeout())
            resolvers.append(r)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=resolvers):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await lookup_spf("example.ch")
        assert result == ""

    async def test_generic_exception_retries(self):
        mock_rr = MagicMock()
        mock_rr.strings = [b"v=spf1 include:example.ch -all"]
        mock_answer = [mock_rr]

        mock_resolver1 = AsyncMock()
        mock_resolver1.resolve = AsyncMock(side_effect=RuntimeError("boom"))

        mock_resolver2 = AsyncMock()
        mock_resolver2.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver1, mock_resolver2]):
            result = await lookup_spf("example.ch")
        assert result == "v=spf1 include:example.ch -all"

    async def test_no_spf_returns_empty(self):
        mock_rr = MagicMock()
        mock_rr.strings = [b"google-site-verification=abc"]
        mock_answer = [mock_rr]

        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(return_value=mock_answer)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await lookup_spf("example.ch")
        assert result == ""


class TestLookupCnameChain:
    async def test_single_cname(self):
        mock_rr = MagicMock()
        mock_rr.target = "mail.protection.outlook.com."

        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(
            side_effect=[
                [mock_rr],  # first call returns CNAME
                dns.resolver.NoAnswer(),  # second call: no more CNAMEs
            ]
        )

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await lookup_cname_chain("mail.example.ch")
        assert result == ["mail.protection.outlook.com"]

    async def test_no_cname(self):
        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(side_effect=dns.resolver.NoAnswer())

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await lookup_cname_chain("mail.example.ch")
        assert result == []

    async def test_chain_of_two(self):
        mock_rr1 = MagicMock()
        mock_rr1.target = "intermediate.example.com."
        mock_rr2 = MagicMock()
        mock_rr2.target = "mail.protection.outlook.com."

        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(
            side_effect=[
                [mock_rr1],
                [mock_rr2],
                dns.resolver.NoAnswer(),
            ]
        )

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await lookup_cname_chain("mail.example.ch")
        assert result == ["intermediate.example.com", "mail.protection.outlook.com"]

    async def test_nxdomain_stops_chain(self):
        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(side_effect=dns.resolver.NXDOMAIN())

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await lookup_cname_chain("mail.example.ch")
        assert result == []

    async def test_timeout_retries_next_resolver(self):
        mock_rr = MagicMock()
        mock_rr.target = "mail.protection.outlook.com."

        mock_resolver1 = AsyncMock()
        mock_resolver1.resolve = AsyncMock(side_effect=dns.exception.Timeout())

        mock_resolver2 = AsyncMock()
        mock_resolver2.resolve = AsyncMock(
            side_effect=[
                [mock_rr],
                dns.resolver.NoAnswer(),
            ]
        )

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver1, mock_resolver2]):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await lookup_cname_chain("mail.example.ch")
        assert result == ["mail.protection.outlook.com"]


class TestResolveMxCnames:
    async def test_returns_mapping(self):
        mock_rr = MagicMock()
        mock_rr.target = "mail.protection.outlook.com."

        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(
            side_effect=[
                [mock_rr],
                dns.resolver.NoAnswer(),
            ]
        )

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await resolve_mx_cnames(["mail.example.ch"])
        assert result == {"mail.example.ch": "mail.protection.outlook.com"}

    async def test_no_cnames_returns_empty(self):
        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(side_effect=dns.resolver.NoAnswer())

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await resolve_mx_cnames(["mail.example.ch"])
        assert result == {}

    async def test_mixed_hosts(self):
        """One host has a CNAME, another doesn't."""
        mock_rr = MagicMock()
        mock_rr.target = "mail.protection.outlook.com."

        call_count = 0

        async def side_effect(hostname, rdtype):
            nonlocal call_count
            call_count += 1
            if hostname == "mail.example.ch" and call_count == 1:
                return [mock_rr]
            raise dns.resolver.NoAnswer()

        mock_resolver = AsyncMock()
        mock_resolver.resolve = AsyncMock(side_effect=side_effect)

        with patch("mail_sovereignty.dns.get_resolvers", return_value=[mock_resolver]):
            result = await resolve_mx_cnames(["mail.example.ch", "mail2.example.ch"])
        assert result == {"mail.example.ch": "mail.protection.outlook.com"}
