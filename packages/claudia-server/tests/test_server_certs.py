"""The server's own TLS certificate: made once, kept, renewed when a name is missing."""

import sys

import pytest

from claudia_server.certs import CertificateError, ensure_certificate
from claudia_server.state import write_private


@pytest.fixture
def certificate(tmp_path):
    return ensure_certificate(tmp_path / "state")


def test_a_certificate_is_made_once_and_kept(tmp_path):
    first = ensure_certificate(tmp_path)
    again = ensure_certificate(tmp_path)
    assert first.fingerprint == again.fingerprint and first.self_signed_by_us
    assert {"localhost", "127.0.0.1", "::1"} <= set(first.names)
    assert first.fingerprint.startswith("SHA256:") and len(first.fingerprint) == 7 + 32 * 3 - 1


def test_a_new_name_makes_a_new_certificate(tmp_path):
    first = ensure_certificate(tmp_path)
    second = ensure_certificate(tmp_path, ("claudia.example.org",))
    assert "claudia.example.org" in second.names and second.fingerprint != first.fingerprint
    assert ensure_certificate(tmp_path, ("claudia.example.org",)).fingerprint == second.fingerprint


def test_a_damaged_certificate_of_ours_is_replaced(tmp_path):
    first = ensure_certificate(tmp_path)
    first.cert_file.write_text("garbage")
    assert ensure_certificate(tmp_path).fingerprint != first.fingerprint


def test_given_certificates_are_checked(tmp_path, certificate):
    given = ensure_certificate(None, (), certificate.cert_file, certificate.key_file)
    assert not given.self_signed_by_us and given.fingerprint == certificate.fingerprint
    with pytest.raises(CertificateError, match="go together"):
        ensure_certificate(None, (), certificate.cert_file, None)
    with pytest.raises(CertificateError, match="cannot read the certificate"):
        ensure_certificate(None, (), tmp_path / "nope.pem", certificate.key_file)
    with pytest.raises(CertificateError, match="private key"):
        ensure_certificate(None, (), certificate.cert_file, tmp_path / "nope.key")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_secrets_are_written_for_their_owner_only(tmp_path):
    target = tmp_path / "secret"
    write_private(target, b"x")
    assert target.read_bytes() == b"x"
    assert (target.stat().st_mode & 0o077) == 0
