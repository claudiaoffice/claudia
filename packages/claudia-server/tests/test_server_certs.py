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


# SEC-06: our certificate is trusted by fingerprint, one certificate for one server; it must not be able to vouch for
# any other name, or whoever steals its key could sign a certificate for any site its holder visits.


def _signed_by(certificate, name: str):
    """A certificate for ``name`` signed with the private key of ``certificate``, as a thief of that key would make."""
    import datetime as dt

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    issuer = x509.load_pem_x509_certificate(certificate.cert_file.read_bytes())
    signer = serialization.load_pem_private_key(certificate.key_file.read_bytes(), password=None)
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
        .issuer_name(issuer.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(hours=1))
        .not_valid_after(now + dt.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(signer.public_key()), critical=False)
        .sign(signer, hashes.SHA256())
    )


def test_our_certificate_cannot_vouch_for_another_name(certificate):
    from cryptography import x509
    from cryptography.x509.verification import PolicyBuilder, Store, VerificationError

    ours = x509.load_pem_x509_certificate(certificate.cert_file.read_bytes())
    forged = _signed_by(certificate, "bank.example")
    verifier = PolicyBuilder().store(Store([ours])).build_server_verifier(x509.DNSName("bank.example"))
    with pytest.raises(VerificationError):
        verifier.verify(forged, [])


def test_a_client_that_trusts_exactly_our_certificate_connects(certificate):
    import socket
    import ssl
    import threading

    server_side = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_side.load_cert_chain(certificate.cert_file, certificate.key_file)
    client_side = ssl.create_default_context(cadata=certificate.cert_file.read_text())
    with socket.create_server(("127.0.0.1", 0)) as listener:

        def serve() -> None:
            conn, _ = listener.accept()
            with server_side.wrap_socket(conn, server_side=True) as tls:
                tls.sendall(b"ok")

        thread = threading.Thread(target=serve)
        thread.start()
        with (
            socket.create_connection(listener.getsockname()) as raw,
            client_side.wrap_socket(raw, server_hostname="localhost") as tls,
        ):
            assert tls.recv(2) == b"ok"
        thread.join(5)


def test_a_certificate_of_ours_that_can_sign_others_is_replaced(tmp_path):
    """A server made its certificate as an authority before SEC-06 (D2001): at the next start it makes a new one."""
    import datetime as dt
    import ipaddress

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    folder = tmp_path / "state"
    old = ensure_certificate(folder)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = dt.datetime.now(dt.UTC)
    as_before = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(hours=1))
        .not_valid_after(now + dt.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(a)) for a in ("127.0.0.1", "::1")]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    old.cert_file.write_bytes(as_before.public_bytes(serialization.Encoding.PEM))
    old.key_file.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    renewed = ensure_certificate(folder)
    made = x509.load_pem_x509_certificate(renewed.cert_file.read_bytes())
    assert renewed.fingerprint != old.fingerprint
    assert not made.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
