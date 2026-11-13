"""Reading the few facts about a server certificate that a person is asked to judge (E5.8): see x509.py."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from certs import Made, authority, issued_by, needs_openssl, openssl_fact, self_signed

from claudia_shell_gtk import x509

pytestmark = needs_openssl


@pytest.fixture
def selfsigned(tmp_path: Path) -> Made:
    return self_signed(tmp_path, "s", cn="demo.example.org", org="Demo Org")


def test_the_fingerprint_is_the_sha256_of_the_der_encoding(selfsigned: Made) -> None:
    der = selfsigned.der()
    assert x509.parse(der).sha256 == hashlib.sha256(der).hexdigest()
    assert x509.parse(der).sha256 == openssl_fact(selfsigned.cert, "-fingerprint -sha256").replace(":", "").lower()


def test_a_name_is_shown_by_its_common_name_first(selfsigned: Made) -> None:
    assert x509.parse(selfsigned.der()).subject == "demo.example.org"


def test_a_name_without_a_common_name_falls_back_to_the_organisation(tmp_path: Path) -> None:
    import subprocess

    cert = tmp_path / "o.pem"
    subprocess.run(  # noqa: S603
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(tmp_path / "o.key"),  # noqa: S607
            "-out",
            str(cert),
            "-days",
            "5",
            "-subj",
            "/O=Only Org/OU=Unit",
        ],
        check=True,
        capture_output=True,
    )
    der = subprocess.run(
        ["openssl", "x509", "-in", str(cert), "-outform", "DER"],  # noqa: S603, S607
        check=True,
        capture_output=True,
    ).stdout
    assert x509.parse(der).subject == "Only Org"


def test_validity_is_read_as_utc(selfsigned: Made) -> None:
    parsed = x509.parse(selfsigned.der())
    expected_end = datetime.strptime(openssl_fact(selfsigned.cert, "-enddate"), "%b %d %H:%M:%S %Y %Z")  # noqa: DTZ007
    assert parsed.not_after == expected_end.replace(tzinfo=UTC)
    assert parsed.not_before.tzinfo is UTC
    assert parsed.not_before <= datetime.now(UTC) <= parsed.not_after


def test_a_certificate_that_signed_itself_says_so(selfsigned: Made) -> None:
    assert x509.parse(selfsigned.der()).self_signed


def test_a_certificate_from_an_authority_is_not_self_signed(tmp_path: Path) -> None:
    ca = authority(tmp_path, "ca", cn="Test Authority")
    leaf = issued_by(tmp_path, "leaf", ca, cn="demo.example.org")
    parsed = x509.parse(leaf.der())
    assert not parsed.self_signed
    assert parsed.issuer == "Test Authority"
    assert parsed.subject == "demo.example.org"


def test_validity_can_be_asked_for_a_moment(selfsigned: Made) -> None:
    parsed = x509.parse(selfsigned.der())
    assert parsed.is_valid_at(datetime.now(UTC))
    assert not parsed.is_valid_at(parsed.not_after.replace(year=parsed.not_after.year + 1))
    assert not parsed.is_valid_at(parsed.not_before.replace(year=parsed.not_before.year - 1))


def test_alternative_names_are_listed(selfsigned: Made) -> None:
    assert set(x509.parse(selfsigned.der()).names) >= {"localhost", "127.0.0.1"}


@pytest.mark.parametrize("junk", [b"", b"not a certificate", b"\x30\x03\x01\x01\x00", b"\x30\x82\xff\xff" + b"\0" * 10])
def test_anything_that_is_not_a_certificate_is_an_error_not_a_crash(junk: bytes) -> None:
    with pytest.raises(x509.CertificateError):
        x509.parse(junk)


def test_a_truncated_certificate_is_an_error(selfsigned: Made) -> None:
    der = selfsigned.der()
    for cut in (10, len(der) // 2, len(der) - 1):
        with pytest.raises(x509.CertificateError):
            x509.parse(der[:cut])
