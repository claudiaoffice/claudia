"""Which servers a client may connect to, and the per-app list of them (E5.8): see servers.py. No GTK, no network.

The address rules are a security rule of the shell (D102, and the decision that goes with this module): plain http
only ever reaches this computer, so a password or a document never crosses a network unencrypted by a typing slip.
"""

from __future__ import annotations

import pytest

from claudia_shell_gtk import servers
from claudia_shell_gtk.servers import AddressRefused, parse_address

# ------------------------------------------------------------------------------------------------------- addresses


@pytest.mark.parametrize(
    ("typed", "origin"),
    [
        ("https://demo.example.org:8420", "https://demo.example.org:8420"),
        ("https://demo.example.org", "https://demo.example.org"),
        ("https://Demo.Example.ORG/", "https://demo.example.org"),
        ("https://demo.example.org:443", "https://demo.example.org"),  # the scheme's own port is not part of the origin
        ("http://127.0.0.1:41233", "http://127.0.0.1:41233"),
        ("http://127.0.0.1:80", "http://127.0.0.1"),
        ("http://localhost:8420", "http://localhost:8420"),
        ("http://[::1]:8420", "http://[::1]:8420"),
        ("https://[2001:db8::1]:8420", "https://[2001:db8::1]:8420"),
        ("  https://demo.example.org:8420  ", "https://demo.example.org:8420"),
    ],
)
def test_an_address_becomes_one_canonical_origin(typed: str, origin: str) -> None:
    assert parse_address(typed).origin == origin


def test_a_bare_host_is_https_not_a_guess_at_something_weaker() -> None:
    assert parse_address("demo.example.org:8420").origin == "https://demo.example.org:8420"
    assert parse_address("demo.example.org").origin == "https://demo.example.org"


@pytest.mark.parametrize("typed", ["http://127.0.0.1:1", "http://127.1.2.3", "http://localhost", "http://[::1]"])
def test_plain_http_reaches_this_computer(typed: str) -> None:
    assert parse_address(typed).is_loopback


@pytest.mark.parametrize(
    "typed",
    [
        "http://192.0.2.7:8420",
        "http://demo.example.org:8420",
        "http://localhost.evil.example",  # starts like localhost, is not
        "http://127.0.0.1.evil.example",  # starts like an address, is not
        "http://0.0.0.0:8420",  # "any address": reaches other machines too
        "http://[::]:8420",
    ],
)
def test_plain_http_to_anything_else_is_refused(typed: str) -> None:
    with pytest.raises(AddressRefused) as refused:
        parse_address(typed)
    assert refused.value.code == "insecure"
    assert "https" in str(refused.value)


@pytest.mark.parametrize(
    "typed",
    [
        "",
        "   ",
        "ftp://demo.example.org",
        "ws://demo.example.org",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://",
        "https://user:secret@demo.example.org",  # never a password in an address
        "https://demo.example.org/claudia",  # an origin only: the page and its socket share one
        "https://demo.example.org/?doc=1",
        "https://demo.example.org/#top",
        "https://demo.example.org:99999",
        "https://demo.example.org:abc",
        "https://demo example.org",
        "https://demo.example.org:8420:1",
        "https://" + "a" * 300 + ".example.org",
    ],
)
def test_anything_that_is_not_the_address_of_a_server_is_refused(typed: str) -> None:
    with pytest.raises(AddressRefused) as refused:
        parse_address(typed)
    assert refused.value.code == "bad_address"


def test_a_refusal_says_what_to_type_instead() -> None:
    with pytest.raises(AddressRefused) as refused:
        parse_address("")
    assert "demo.example.org" in str(refused.value)


def test_the_default_label_of_a_server_is_its_host_and_port() -> None:
    assert servers.default_label("https://demo.example.org:8420") == "demo.example.org:8420"
    assert servers.default_label("https://demo.example.org") == "demo.example.org"


# ----------------------------------------------------------------------------------------------------------- lists


def entry(origin: str, label: str = "x", custom: bool = False, **extra: object) -> dict:
    return {"origin": origin, "label": label, "custom": custom, **extra}


def test_a_list_keeps_valid_entries_in_order_with_canonical_origins() -> None:
    kept = servers.sanitize(
        [entry("https://A.example.org/", "A", True), entry("https://b.example.org:8420", "B")],
    )
    assert kept == [entry("https://a.example.org", "A", True), entry("https://b.example.org:8420", "B")]


def test_a_list_drops_what_cannot_be_a_server() -> None:
    kept = servers.sanitize(
        [
            entry("http://192.0.2.7:8420"),  # plain http elsewhere
            entry("javascript:alert(1)"),
            {"origin": 7, "label": "x", "custom": False},
            {"label": "no origin", "custom": False},
            "not even an object",
            entry("https://ok.example.org", "OK"),
        ]
    )
    assert [e["origin"] for e in kept] == ["https://ok.example.org"]


def test_a_list_has_each_server_once_the_first_entry_wins() -> None:
    kept = servers.sanitize([entry("https://a.example.org", "first"), entry("https://A.example.org/", "second")])
    assert [e["label"] for e in kept] == ["first"]


def test_a_missing_or_bad_label_becomes_the_default_one() -> None:
    kept = servers.sanitize(
        [
            {"origin": "https://a.example.org", "custom": False},
            {"origin": "https://b.example.org", "label": "   ", "custom": False},
            {"origin": "https://c.example.org", "label": 5, "custom": True},
        ]
    )
    assert [e["label"] for e in kept] == ["a.example.org", "b.example.org", "c.example.org"]


def test_a_long_label_is_cut() -> None:
    kept = servers.sanitize([entry("https://a.example.org", "x" * 500)])
    assert len(kept[0]["label"]) == servers.MAX_LABEL


def test_the_list_has_a_limit_so_a_page_cannot_fill_the_settings_file() -> None:
    many = [entry(f"https://s{i}.example.org") for i in range(servers.MAX_SERVERS + 30)]
    assert len(servers.sanitize(many)) == servers.MAX_SERVERS


def test_anything_but_a_list_is_nothing() -> None:
    for raw in (None, {}, "x", 3, {"origin": "https://a.example.org"}):
        assert servers.sanitize(raw) == []


def test_a_remembered_list_never_holds_this_computers_server() -> None:
    """Its port changes with every start, and the shell adds it afresh each time (``for_page``)."""
    kept = servers.sanitize(
        [entry("http://127.0.0.1:41233", "This computer", True, local=True), entry("https://a.example.org")]
    )
    assert [e["origin"] for e in kept] == ["https://a.example.org"]


def test_a_loopback_server_that_is_not_marked_local_is_kept() -> None:
    """A developer's own server on another port is a server like any other."""
    kept = servers.sanitize([entry("http://localhost:8420", "dev")])
    assert [e["origin"] for e in kept] == ["http://localhost:8420"]


def test_the_page_gets_this_computer_first_and_the_remembered_servers_after_it() -> None:
    saved = [entry("https://a.example.org", "A")]
    shown = servers.for_page(saved, local_origin="http://127.0.0.1:41233", local_label="This computer")
    assert shown[0] == entry("http://127.0.0.1:41233", "This computer", True, local=True)
    assert shown[1:] == saved


def test_without_a_local_server_the_page_gets_only_the_remembered_ones() -> None:
    saved = [entry("https://a.example.org", "A")]
    assert servers.for_page(saved, local_origin=None, local_label="This computer") == saved


def test_a_remembered_server_at_the_local_address_is_not_shown_twice() -> None:
    saved = [entry("http://127.0.0.1:41233", "old"), entry("https://a.example.org", "A")]
    shown = servers.for_page(saved, local_origin="http://127.0.0.1:41233", local_label="This computer")
    assert [e["origin"] for e in shown] == ["http://127.0.0.1:41233", "https://a.example.org"]
    assert shown[0]["label"] == "This computer"


def test_remembering_a_connection_adds_the_server_or_keeps_what_the_person_named_it() -> None:
    saved = [entry("https://a.example.org", "My A", True)]
    after = servers.remember(saved, "https://a.example.org")
    assert after == saved  # renamed by the person: theirs to keep
    after = servers.remember(saved, "https://b.example.org:8420")
    assert [e["origin"] for e in after] == ["https://a.example.org", "https://b.example.org:8420"]
    assert after[1] == entry("https://b.example.org:8420", "b.example.org:8420", False)


def test_remembering_does_not_change_the_list_it_was_given() -> None:
    saved = [entry("https://a.example.org", "A")]
    servers.remember(saved, "https://b.example.org")
    assert len(saved) == 1


def test_the_list_limit_is_the_one_the_contract_allows() -> None:
    from claudia_shell_gtk import contract

    assert servers.MAX_SERVERS == contract.MAX_SERVER_LIST
