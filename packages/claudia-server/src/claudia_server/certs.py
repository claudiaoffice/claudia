"""The server's TLS certificate.

Traffic to and from the server is encrypted (https:// and wss://) unless it is switched off. The certificate is

* the one given with ``--tls-cert`` / ``--tls-key`` (from Let's Encrypt, mkcert, your company ...), or
* one the server makes for itself, once, in ``<state dir>/tls/`` and keeps using. It is self-signed: browsers warn
  about it once and the desktop client asks the person to trust its fingerprint (which is printed at start-up).
  It names ``localhost``, ``127.0.0.1``, ``::1``, this computer's host name and whatever ``--tls-name`` adds
  (give the name or address people will type, or they will be warned about a mismatch); it is made anew when it
  is about to expire or a name is missing.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import socket
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .state import default_state_dir, private_dir, write_private

VALID_DAYS = 3 * 365
RENEW_BEFORE = dt.timedelta(days=30)


class CertificateError(Exception):
    """The certificate or its key cannot be used. The message is meant for the person running the server."""


@dataclass(frozen=True)
class Certificate:
    cert_file: Path
    key_file: Path
    fingerprint: str  # SHA256:AB:CD:...
    names: tuple[str, ...]  # what it is valid for
    self_signed_by_us: bool  # made by this server (so clients will have to trust it by hand)


def _fingerprint(cert: x509.Certificate) -> str:
    digest = cert.fingerprint(hashes.SHA256()).hex().upper()
    return "SHA256:" + ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


def _names_of(cert: x509.Certificate) -> tuple[str, ...]:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return ()
    return tuple(san.get_values_for_type(x509.DNSName)) + tuple(str(i) for i in san.get_values_for_type(x509.IPAddress))


def _load(cert_file: Path) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(cert_file.read_bytes())
    except (OSError, ValueError) as exc:
        raise CertificateError(f"cannot read the certificate {cert_file}: {exc}") from exc


def wanted_names(extra: tuple[str, ...] = ()) -> list[str]:
    names = ["localhost", "127.0.0.1", "::1"]
    for candidate in (socket.gethostname(), socket.getfqdn(), *extra):
        name = candidate.strip()
        if name and name not in names:
            names.append(name)
    return names


def _make(names: list[str], cert_file: Path, key_file: Path) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    alternative: list[x509.GeneralName] = []
    for name in names:
        try:
            alternative.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            alternative.append(x509.DNSName(name))
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, names[0] if names else "localhost"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Claudia server"),
        ]
    )
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(hours=1))
        .not_valid_after(now + dt.timedelta(days=VALID_DAYS))
        .add_extension(x509.SubjectAlternativeName(alternative), critical=False)
        # Self-signed, so it is also its own authority: that is what lets a client that was told to trust this one
        # certificate check it (see claudia_client/trust.py).
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    private_dir(cert_file.parent)
    write_private(
        key_file,
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
    )
    write_private(cert_file, cert.public_bytes(serialization.Encoding.PEM))


def ensure_certificate(
    state_dir: str | Path | None = None,
    extra_names: tuple[str, ...] = (),
    cert_file: str | Path | None = None,
    key_file: str | Path | None = None,
) -> Certificate:
    """The certificate to serve with: the given one, else ours (made if it is missing, expiring or lacks a name)."""
    if cert_file or key_file:
        if not (cert_file and key_file):
            raise CertificateError("--tls-cert and --tls-key go together")
        cert_path, key_path = Path(cert_file).expanduser(), Path(key_file).expanduser()
        cert = _load(cert_path)
        if not key_path.is_file():
            raise CertificateError(f"cannot read the private key {key_path}")
        if cert.not_valid_after_utc < dt.datetime.now(dt.UTC):
            raise CertificateError(f"the certificate {cert_path} has expired ({cert.not_valid_after_utc:%Y-%m-%d})")
        return Certificate(cert_path, key_path, _fingerprint(cert), _names_of(cert), False)

    folder = Path(state_dir).expanduser() if state_dir else default_state_dir()
    cert_path, key_path = folder / "tls" / "cert.pem", folder / "tls" / "key.pem"
    names = wanted_names(tuple(extra_names))
    if cert_path.is_file() and key_path.is_file():
        try:
            cert = _load(cert_path)
            soon = dt.datetime.now(dt.UTC) + RENEW_BEFORE
            # (the host name may change with every container: only what the person asked for must be there)
            required = {"localhost", "127.0.0.1", "::1", *(n.strip() for n in extra_names if n.strip())}
            if cert.not_valid_after_utc > soon and required <= set(_names_of(cert)):
                return Certificate(cert_path, key_path, _fingerprint(cert), _names_of(cert), True)
        except CertificateError:
            pass  # (a damaged file of ours: replaced below)
    try:
        _make(names, cert_path, key_path)
    except OSError as exc:
        raise CertificateError(f"cannot make a certificate in {cert_path.parent}: {exc}") from exc
    cert = _load(cert_path)
    return Certificate(cert_path, key_path, _fingerprint(cert), _names_of(cert), True)
