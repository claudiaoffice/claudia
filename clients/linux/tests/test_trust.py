"""Which certificates a person has chosen to trust, and how a fingerprint is shown (E5.8): see trust.py."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from claudia_shell_gtk import settings
from claudia_shell_gtk.trust import TrustStore, format_fingerprint

ORIGIN = "https://demo.example.org:8420"
PRINT = "0123456789abcdef" * 4


def store(tmp_path: Path) -> TrustStore:
    return TrustStore(tmp_path / "shell.json", today=lambda: date(2026, 11, 10))


def test_a_fingerprint_is_shown_in_four_lines_of_eight_bytes() -> None:
    lines = format_fingerprint(PRINT)
    assert lines == ["01:23:45:67:89:AB:CD:EF"] * 4


def test_a_fingerprint_that_is_not_one_is_refused() -> None:
    for bad in ("", "abc", "g" * 64, PRINT + "00"):
        with pytest.raises(ValueError, match="fingerprint"):
            format_fingerprint(bad)


def test_nothing_is_trusted_at_first(tmp_path: Path) -> None:
    trust = store(tmp_path)
    assert trust.pinned(ORIGIN) is None
    assert not trust.is_trusted(ORIGIN, PRINT)


def test_trusting_pins_that_one_certificate_for_that_one_origin(tmp_path: Path) -> None:
    trust = store(tmp_path)
    trust.trust(ORIGIN, PRINT)
    assert trust.is_trusted(ORIGIN, PRINT)
    assert not trust.is_trusted(ORIGIN, "f" * 64)  # another certificate at the same address
    assert not trust.is_trusted("https://other.example.org", PRINT)  # the same certificate somewhere else


def test_the_choice_survives_a_restart_and_records_the_day(tmp_path: Path) -> None:
    store(tmp_path).trust(ORIGIN, PRINT)
    again = store(tmp_path)
    assert again.pinned(ORIGIN) == PRINT
    assert settings.load_trusted(tmp_path / "shell.json")[ORIGIN] == {"sha256": PRINT, "since": "2026-11-10"}


def test_trusting_a_new_certificate_replaces_the_old_one(tmp_path: Path) -> None:
    trust = store(tmp_path)
    trust.trust(ORIGIN, PRINT)
    trust.trust(ORIGIN, "f" * 64)
    assert trust.pinned(ORIGIN) == "f" * 64


def test_forgetting_removes_the_pin_and_only_that_one(tmp_path: Path) -> None:
    trust = store(tmp_path)
    trust.trust(ORIGIN, PRINT)
    trust.trust("https://b.example.org", PRINT)
    trust.forget(ORIGIN)
    assert trust.pinned(ORIGIN) is None
    assert trust.pinned("https://b.example.org") == PRINT
    trust.forget("https://never-trusted.example.org")  # nothing to forget is not an error


def test_plain_http_cannot_be_trusted(tmp_path: Path) -> None:
    trust = store(tmp_path)
    with pytest.raises(ValueError, match="https"):
        trust.trust("http://127.0.0.1:8420", PRINT)


def test_the_mapping_for_the_checker_is_a_copy(tmp_path: Path) -> None:
    trust = store(tmp_path)
    trust.trust(ORIGIN, PRINT)
    snapshot = trust.snapshot()
    snapshot.clear()
    assert trust.pinned(ORIGIN) == PRINT


# ------------------------------------------------------------------------- when the web view may be told to go on


def test_the_web_view_may_go_on_only_for_the_pinned_certificate() -> None:
    import hashlib

    from claudia_shell_gtk.trust import may_override

    der = b"some certificate"
    pin = hashlib.sha256(der).hexdigest()
    unknown_ca, bad_identity = 1, 2
    assert may_override(der, pin, unknown_ca)
    assert may_override(der, pin, unknown_ca | bad_identity)
    assert not may_override(der, None, unknown_ca)  # nothing trusted for this address
    assert not may_override(b"another certificate", pin, unknown_ca)  # not the certificate that was trusted


@pytest.mark.parametrize("flag", [4, 8, 16, 32, 64])  # not activated, expired, revoked, insecure, generic error
def test_the_web_view_never_goes_on_past_a_certificate_that_is_broken_in_another_way(flag: int) -> None:
    import hashlib

    from claudia_shell_gtk.trust import may_override

    der = b"some certificate"
    assert not may_override(der, hashlib.sha256(der).hexdigest(), 1 | flag)
