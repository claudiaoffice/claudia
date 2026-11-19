"""Who a connection is, behind a proxy (D1275, SEC-02, SEC-11): the address the nearest trusted proxy appended."""

import logging

import pytest
from starlette.requests import Request

from claudia_server.client_address import ClientAddress, forwarded_address

PROXY = "10.0.0.5"


@pytest.mark.parametrize(
    ("header", "hops", "expected"),
    [
        ("203.0.113.7", 1, "203.0.113.7"),
        # a client can write anything on the left: only the entry the proxy appended counts
        ("1.2.3.4, 203.0.113.7", 1, "203.0.113.7"),
        ("1.2.3.4, 203.0.113.7, 198.51.100.2", 2, "203.0.113.7"),
        ("2001:db8::1", 1, "2001:db8::1"),
        ("  203.0.113.7  ", 1, "203.0.113.7"),
    ],
)
def test_the_entry_n_places_from_the_right_is_the_client(header, hops, expected):
    assert forwarded_address(PROXY, header, hops) == expected


@pytest.mark.parametrize("header", [None, "", "not-an-address", "203.0.113.7, <script>", ","])
def test_a_missing_or_bad_header_is_the_proxys_own_address(header):
    assert forwarded_address(PROXY, header, 1) == PROXY


def test_fewer_entries_than_trusted_proxies_is_the_proxys_own_address():
    assert forwarded_address(PROXY, "203.0.113.7", 2) == PROXY


def test_no_trusted_proxy_means_the_header_is_ignored():
    assert forwarded_address(PROXY, "203.0.113.7", 0) == PROXY


def request(peer: str | None, forwarded: str | None) -> Request:
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    scope = {"type": "http", "method": "GET", "path": "/", "headers": headers, "client": (peer, 1234) if peer else None}
    return Request(scope)


def test_two_people_behind_one_proxy_are_two_addresses():
    behind = ClientAddress(trusted_hops=1)
    assert behind.of(request(PROXY, "203.0.113.7")) != behind.of(request(PROXY, "203.0.113.8"))


def test_without_a_proxy_a_spoofed_header_changes_nothing():
    direct = ClientAddress()
    assert direct.of(request("198.51.100.9", "203.0.113.7")) == "198.51.100.9"


def test_a_connection_without_a_peer_has_an_empty_address():
    assert ClientAddress().of(request(None, None)) == ""


def test_a_proxy_that_sends_no_header_is_said_in_the_log_once(caplog):
    behind = ClientAddress(trusted_hops=1)
    with caplog.at_level(logging.WARNING, logger="claudia_server"):
        assert behind.of(request(PROXY, None)) == PROXY
        assert behind.of(request(PROXY, None)) == PROXY
    assert len([r for r in caplog.records if "X-Forwarded-For" in r.getMessage()]) == 1
