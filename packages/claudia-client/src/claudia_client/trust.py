"""Which servers a client trusts when it connects over TLS (``wss://``, ``https://``).

A server with a certificate that a known authority signed (Let's Encrypt, your company's) is trusted like any web
site. A server that made its own certificate (what ``python3 -m claudia_server`` does when it is not given one) is
trusted like an SSH host: the first time, the person is shown its **fingerprint** and decides; the certificate is
then remembered for that address, and a different one later is refused loudly (it may be somebody in the middle).
The server prints its fingerprint when it starts, so it can be compared.

    policy = TlsPolicy(accept_new=False)         # raises UntrustedCertificate with the fingerprint, once
    policy.trust("host:8765", fingerprint)       # ... after the person said yes (or: TlsPolicy(accept_new=True))

Also trusted, for a server whose certificate comes from a private authority: the file named by ``cafile`` /
``$CLAUDIA_CA_CERT`` (a certificate, or several, in PEM format).
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import ssl
import sys
import tempfile
from pathlib import Path


def fingerprint_of(der: bytes) -> str:
    """``SHA256:AB:CD:...``, the way browsers and ``openssl`` show it."""
    digest = hashlib.sha256(der).hexdigest().upper()
    return "SHA256:" + ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


def config_dir() -> Path:
    """The per-user folder for what the client remembers (the trusted servers)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "claudia"


class UntrustedCertificate(Exception):
    """The server's certificate is not one this computer trusts (yet). The message says what to do."""

    def __init__(self, message: str, server: str, fingerprint: str):
        super().__init__(message)
        self.server = server
        self.fingerprint = fingerprint


class TlsPolicy:
    """Decides which server certificates a client accepts, and remembers the ones the person trusted."""

    def __init__(
        self,
        cafile: str | os.PathLike | None = None,
        accept_new: bool = False,
        known_servers: str | os.PathLike | None = None,
    ):
        self.cafile = str(cafile) if cafile else os.environ.get("CLAUDIA_CA_CERT") or None
        self.accept_new = accept_new or os.environ.get("CLAUDIA_TRUST_NEW_SERVER") == "1"
        self.known_path = Path(known_servers) if known_servers else config_dir() / "known_servers.json"

    # -- what is remembered ----------------------------------------------------------------
    def _known(self) -> dict:
        try:
            data = json.loads(self.known_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except OSError, ValueError:
            return {}

    def trust(self, server: str, fingerprint: str, pem: str) -> None:
        """Remember the certificate of ``server`` (``host:port``)."""
        known = self._known()
        known[server] = {"fingerprint": fingerprint, "pem": pem}
        self.known_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=self.known_path.parent, prefix=".known_servers.")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(known, handle, indent=1)
        os.replace(temp, self.known_path)

    def forget(self, server: str) -> bool:
        """Stop trusting the remembered certificate of ``server``; ``False`` if there was none."""
        known = self._known()
        if known.pop(server, None) is None:
            return False
        self.known_path.write_text(json.dumps(known, indent=1), encoding="utf-8")
        return True

    # -- deciding --------------------------------------------------------------------------
    def _verifying_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context()  # the system's authorities ...
        if self.cafile:
            context.load_verify_locations(cafile=self.cafile)  # ... and the one we were given
        return context

    def context_for(self, host: str, port: int, timeout: float = 10.0) -> ssl.SSLContext:
        """The TLS settings to connect to ``host:port`` with, or ``UntrustedCertificate``/``OSError``.

        The server is first asked, with full checking. If its certificate does not pass, the one it shows is
        compared with the one remembered for this address; the connection that follows trusts *that certificate
        and nothing else*, so it cannot be answered by anybody else."""
        context = self._verifying_context()
        try:
            self._handshake(host, port, context, timeout)
            return context
        except ssl.SSLCertVerificationError as failure:
            reason = failure.verify_message or str(failure)
        server = f"{host}:{port}"
        der = self._unverified_certificate(host, port, timeout)
        fingerprint = fingerprint_of(der)
        pem = ssl.DER_cert_to_PEM_cert(der)
        remembered = self._known().get(server)
        if remembered is not None and remembered.get("fingerprint") != fingerprint:
            raise UntrustedCertificate(
                f"WARNING: the certificate of {server} is not the one this computer remembers for it. "
                f"It is {fingerprint}; remembered: {remembered.get('fingerprint')}. "
                "Either the server was set up anew (then ask its administrator for the fingerprint and, if it matches, "
                f"remove the old entry with ``TlsPolicy.forget({server!r})``), "
                "or somebody is intercepting the connection.",
                server,
                fingerprint,
            )
        if remembered is None:
            if not self.accept_new:
                raise UntrustedCertificate(
                    f"{server} uses a certificate that no known authority signed ({reason}). "
                    f"Its fingerprint is {fingerprint}. If that is what the server printed when it started, "
                    "trust it with --trust-new-server (once; it is remembered), or give the certificate with "
                    "--cacert FILE.",
                    server,
                    fingerprint,
                )
            self.trust(server, fingerprint, pem)
        pinned = ssl.create_default_context(cadata=pem)  # (loads this certificate only, not the system's authorities)
        pinned.check_hostname = False  # the certificate itself was chosen by the person, whatever the address says
        return pinned

    @staticmethod
    def _handshake(host: str, port: int, context: ssl.SSLContext, timeout: float) -> None:
        with (
            socket.create_connection((host, port), timeout=timeout) as raw,
            context.wrap_socket(raw, server_hostname=host),
        ):
            pass

    @staticmethod
    def _unverified_certificate(host: str, port: int, timeout: float) -> bytes:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with (
            socket.create_connection((host, port), timeout=timeout) as raw,
            context.wrap_socket(raw, server_hostname=host) as tls,
        ):
            der = tls.getpeercert(binary_form=True)
        if not der:
            raise OSError("the server showed no certificate")
        return der
