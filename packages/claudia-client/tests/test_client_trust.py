"""Trusting a server's certificate like an SSH host, against a real TLS server."""

import socket
import ssl
import threading
import time
import urllib.request

import pytest

uvicorn = pytest.importorskip("uvicorn")

from claudia_client import TlsPolicy, UntrustedCertificate, fingerprint_of  # noqa: E402

from claudia_core.testing import ListModel  # noqa: E402
from claudia_server import Hub, MemoryProvider, ScryptDirectory, create_app, ensure_certificate  # noqa: E402


class TlsServer:
    """A real server on a free port, with TLS, in a thread."""

    def __init__(self, certificate):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        app = create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(cost=2**4))
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            ssl_certfile=str(certificate.cert_file),
            ssl_keyfile=str(certificate.key_file),
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(250):
            if self.server.started:
                break
            time.sleep(0.02)
        else:
            raise RuntimeError("server did not start")
        self.host = "127.0.0.1"
        self.address = f"127.0.0.1:{self.port}"

    def stop(self):
        self.server.should_exit = True
        self.thread.join(10)


@pytest.fixture
def certificate(tmp_path):
    return ensure_certificate(tmp_path / "state")


@pytest.fixture
def server(certificate):
    running = TlsServer(certificate)
    yield running
    running.stop()


@pytest.fixture
def policy(tmp_path):
    return TlsPolicy(known_servers=tmp_path / "known.json")


def health(server, context=None):
    return urllib.request.urlopen(f"https://{server.address}/api/health", context=context, timeout=5)


def test_the_server_speaks_https_and_not_plain_http(server):
    unverified = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    unverified.check_hostname, unverified.verify_mode = False, ssl.CERT_NONE
    with health(server, unverified) as reply:
        assert reply.status == 200
    with pytest.raises(OSError):
        urllib.request.urlopen(f"http://{server.address}/api/health", timeout=5).read()
    with pytest.raises(OSError):  # (a client that does not trust the certificate is refused by its own checks)
        health(server)


def test_an_unknown_certificate_is_not_trusted_unasked(server, certificate, policy):
    with pytest.raises(UntrustedCertificate) as refused:
        policy.context_for(server.host, server.port)
    assert refused.value.fingerprint == certificate.fingerprint
    assert certificate.fingerprint in str(refused.value) and "--trust-new-server" in str(refused.value)
    assert not policy.known_path.exists(), "nothing is remembered until the person says so"


def test_trusting_it_once_is_enough_afterwards(server, certificate, policy):
    first = TlsPolicy(accept_new=True, known_servers=policy.known_path).context_for(server.host, server.port)
    with health(
        server, first
    ) as reply:  # (the context it returns trusts that certificate and works for the connection)
        assert reply.status == 200
    again = TlsPolicy(known_servers=policy.known_path).context_for(server.host, server.port)  # told nothing this time
    with health(server, again) as reply:
        assert reply.status == 200


def test_a_certificate_given_as_cacert_is_trusted_and_nothing_is_remembered(server, certificate, tmp_path):
    policy = TlsPolicy(cafile=certificate.cert_file, known_servers=tmp_path / "k.json")
    with health(server, policy.context_for(server.host, server.port)) as reply:
        assert reply.status == 200
    assert not (tmp_path / "k.json").exists()


def test_another_certificate_than_the_remembered_one_is_refused_loudly(server, certificate, policy):
    pem = "-----BEGIN CERTIFICATE-----\nx\n-----END CERTIFICATE-----\n"
    policy.trust(server.address.replace("127.0.0.1", server.host), "SHA256:" + ":".join(["00"] * 32), pem)
    accepting = TlsPolicy(accept_new=True, known_servers=policy.known_path)
    with pytest.raises(UntrustedCertificate, match="WARNING.*intercepting") as refused:
        accepting.context_for(server.host, server.port)
    assert refused.value.fingerprint == certificate.fingerprint  # (accepting new servers does not override a change)
    assert policy.forget(server.address) and not policy.forget(server.address)
    accepting.context_for(server.host, server.port)


def test_a_server_without_tls_is_never_silently_downgraded(tmp_path):
    with socket.socket() as plain:
        plain.bind(("127.0.0.1", 0))
        plain.listen()
        port = plain.getsockname()[1]
        with pytest.raises(OSError):
            TlsPolicy(known_servers=tmp_path / "k.json").context_for("127.0.0.1", port, timeout=2)


def test_the_fingerprint_matches_the_one_the_server_shows(certificate):
    der = ssl.PEM_cert_to_DER_cert(certificate.cert_file.read_text())
    assert fingerprint_of(der) == certificate.fingerprint
