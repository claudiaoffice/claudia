"""Can this window connect to the server at an address? (E5.8): see connection.py.

Most tests talk to a real little server on the loopback address (plain and over TLS with certificates made by
``openssl``); the classification of TLS failures that cannot be produced that way (an expired certificate) uses a fake
transport. No GTK.
"""

from __future__ import annotations

import http.server
import json
import ssl
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from certs import Made, authority, issued_by, needs_openssl, self_signed

from claudia_shell_gtk import connection, x509
from claudia_shell_gtk.connection import (
    Fetched,
    HttpTransport,
    NeedsTrust,
    Reached,
    Refused,
    Response,
    TlsVerifyError,
    Unreachable,
    check,
)
from claudia_shell_gtk.servers import parse_address

OK = Response(200, b'{"ok": true}')


def docs(app: str) -> Response:
    return Response(200, json.dumps({"app": app, "documents": []}).encode())


# ------------------------------------------------------------------------------------------------ a real server


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    routes: dict[str, Response]

    def do_GET(self) -> None:  # noqa: N802 (the name http.server asks for)
        reply = self.routes.get(self.path, Response(404, b"{}"))
        self.send_response(reply.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply.body)))
        self.end_headers()
        self.wfile.write(reply.body)

    def log_message(self, *args: object) -> None:
        pass


@contextmanager
def serve(routes: dict[str, Response], certificate: Made | None = None) -> Iterator[str]:
    """A server on a free loopback port; yields its address (``https://…`` when it has a certificate)."""
    handler = type("Handler", (_Handler,), {"routes": routes})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    if certificate is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate.cert, certificate.key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"{'https' if certificate else 'http'}://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def claudia(app: str) -> dict[str, Response]:
    return {"/api/health": OK, "/api/docs": docs(app)}


def run(address: str, app: str = "computes", **options: object):
    return check(parse_address(address), app, **options)  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------------------- plain http


def test_a_server_of_the_same_app_is_reached() -> None:
    with serve(claudia("computes")) as address:
        outcome = run(address)
    assert outcome == Reached(origin=address, app="computes")


def test_a_server_of_another_app_is_refused_naming_both_apps() -> None:
    with serve(claudia("composes")) as address:
        outcome = run(address, "computes")
    assert isinstance(outcome, Refused)
    assert outcome.code == "wrong_app"
    assert "Claudia Composes" in outcome.message
    assert "Claudia Computes" in outcome.message


def test_a_server_that_hides_its_app_is_left_to_the_hello_check() -> None:
    """A server that asks for a secret before it lists documents does not say which app it is: the page's hello,
    which names the app, is checked again when the page loads (bridge.py)."""
    for status in (401, 403, 404):
        routes = {"/api/health": OK, "/api/docs": Response(status, b"{}")}
        with serve(routes) as address:
            assert run(address) == Reached(origin=address, app=None)


@pytest.mark.parametrize(
    "routes",
    [
        {},  # a web server that has no /api/health
        {"/api/health": Response(200, b"<html>hello</html>")},
        {"/api/health": Response(200, b'{"ok": false}')},
        {"/api/health": Response(200, b"[1]")},
        {"/api/health": Response(500, b"{}")},
        {"/api/health": OK, "/api/docs": Response(200, b"not json")},
        {"/api/health": OK, "/api/docs": Response(200, b'{"app": 5}')},
        {"/api/health": OK, "/api/docs": Response(200, b'{"app": "unknown-app"}')},
    ],
)
def test_something_that_is_not_a_claudia_server_is_refused(routes: dict[str, Response]) -> None:
    with serve(routes) as address:
        outcome = run(address)
    assert isinstance(outcome, Refused)
    assert outcome.code == "not_claudia"
    assert "Claudia server" in outcome.message


def test_a_server_that_is_not_there_is_unreachable_and_the_message_names_the_address() -> None:
    with serve({}) as address:
        pass  # the server is gone again: its port is closed
    outcome = run(address)
    assert isinstance(outcome, Refused)
    assert outcome.code == "unreachable"
    assert address.removeprefix("http://") in outcome.message


def test_a_server_that_answers_too_slowly_is_unreachable() -> None:
    class Slow:
        def get(self, address, paths, *, verify):  # noqa: ANN001, ANN201
            raise Unreachable

    outcome = run("http://127.0.0.1:9", transport=Slow())
    assert isinstance(outcome, Refused)
    assert outcome.code == "unreachable"


def test_a_plain_http_server_on_an_https_address_is_not_a_claudia_server() -> None:
    with serve(claudia("computes")) as address:
        outcome = run(address.replace("http://", "https://"))
    assert isinstance(outcome, Refused)
    assert outcome.code == "not_claudia"


def test_a_huge_answer_is_not_read_into_memory() -> None:
    routes = {"/api/health": Response(200, b" " * (connection.MAX_BODY + 10))}
    with serve(routes) as address:
        outcome = run(address)
    assert isinstance(outcome, Refused)
    assert outcome.code == "not_claudia"


# ---------------------------------------------------------------------------------------------------- https


@needs_openssl
class TestSelfSigned:
    @pytest.fixture
    def cert(self, tmp_path: Path) -> Made:
        return self_signed(tmp_path, "srv", cn="demo.example.org", org="Demo Org")

    def test_an_unknown_certificate_must_be_judged_by_the_person(self, cert: Made) -> None:
        with serve(claudia("computes"), cert) as address:
            outcome = run(address)
        assert isinstance(outcome, NeedsTrust)
        assert outcome.origin == address
        assert outcome.reason == "unknown_issuer"
        assert outcome.previous is None
        assert outcome.certificate == x509.parse(cert.der())
        assert outcome.app == "computes"

    def test_the_trusted_certificate_is_accepted(self, cert: Made) -> None:
        pin = x509.parse(cert.der()).sha256
        with serve(claudia("computes"), cert) as address:
            outcome = run(address, trusted={address: {"sha256": pin, "since": ""}})
        assert outcome == Reached(origin=address, app="computes", fingerprint=pin)

    def test_another_certificate_than_the_trusted_one_is_a_changed_certificate(self, cert: Made) -> None:
        old = "ab" * 32
        with serve(claudia("computes"), cert) as address:
            outcome = run(address, trusted={address: {"sha256": old, "since": ""}})
        assert isinstance(outcome, NeedsTrust)
        assert outcome.previous == old

    def test_a_certificate_trusted_for_another_address_does_not_count(self, cert: Made) -> None:
        pin = x509.parse(cert.der()).sha256
        with serve(claudia("computes"), cert) as address:
            outcome = run(address, trusted={"https://elsewhere.example.org": {"sha256": pin, "since": ""}})
        assert isinstance(outcome, NeedsTrust)

    def test_a_server_of_the_wrong_app_is_refused_before_the_person_is_asked_to_trust_it(self, cert: Made) -> None:
        with serve(claudia("composes"), cert) as address:
            outcome = run(address)
        assert isinstance(outcome, Refused)
        assert outcome.code == "wrong_app"

    def test_something_that_is_not_claudia_is_refused_before_the_person_is_asked_to_trust_it(self, cert: Made) -> None:
        with serve({}, cert) as address:
            outcome = run(address)
        assert isinstance(outcome, Refused)
        assert outcome.code == "not_claudia"

    def test_an_expired_certificate_is_never_offered_for_trust(self, cert: Made) -> None:
        later = datetime.now(UTC) + timedelta(days=400)
        with serve(claudia("computes"), cert) as address:
            outcome = run(address, now=lambda: later)
        assert isinstance(outcome, Refused)
        assert outcome.code == "certificate_expired"
        assert "expired" in outcome.message
        assert "127.0.0.1" in outcome.message

    def test_a_pinned_certificate_that_has_expired_is_not_accepted_either(self, cert: Made) -> None:
        pin = x509.parse(cert.der()).sha256
        later = datetime.now(UTC) + timedelta(days=400)
        with serve(claudia("computes"), cert) as address:
            outcome = run(address, trusted={address: {"sha256": pin, "since": ""}}, now=lambda: later)
        assert isinstance(outcome, Refused)
        assert outcome.code == "certificate_expired"

    def test_a_certificate_that_is_not_valid_yet_is_never_offered_for_trust(self, cert: Made) -> None:
        earlier = datetime.now(UTC) - timedelta(days=400)
        with serve(claudia("computes"), cert) as address:
            outcome = run(address, now=lambda: earlier)
        assert isinstance(outcome, Refused)
        assert outcome.code == "certificate_invalid"


@needs_openssl
class TestIssuedByAnAuthority:
    @pytest.fixture
    def ca(self, tmp_path: Path) -> Made:
        return authority(tmp_path, "ca")

    def test_a_certificate_from_a_trusted_authority_needs_no_question(self, tmp_path: Path, ca: Made) -> None:
        leaf = issued_by(tmp_path, "leaf", ca)  # valid for 127.0.0.1
        with serve(claudia("computes"), leaf) as address:
            outcome = run(address, transport=HttpTransport(cafile=str(ca.cert)))
        assert outcome == Reached(origin=address, app="computes")

    def test_a_certificate_for_another_name_is_offered_with_that_reason(self, tmp_path: Path, ca: Made) -> None:
        leaf = issued_by(tmp_path, "leaf", ca, cn="other.example.org", san="DNS:other.example.org")
        with serve(claudia("computes"), leaf) as address:
            outcome = run(address, transport=HttpTransport(cafile=str(ca.cert)))
        assert isinstance(outcome, NeedsTrust)
        assert outcome.reason == "name_mismatch"
        assert not outcome.certificate.self_signed
        assert outcome.certificate.issuer == "Test Authority"

    def test_a_certificate_from_an_unknown_authority_is_offered_with_that_reason(
        self, tmp_path: Path, ca: Made
    ) -> None:
        leaf = issued_by(tmp_path, "leaf", ca)
        with serve(claudia("computes"), leaf) as address:
            outcome = run(address)  # the system does not know "Test Authority"
        assert isinstance(outcome, NeedsTrust)
        assert outcome.reason == "unknown_issuer"


# ------------------------------------------------------------------------------ failures a fake transport shows


class Fake:
    """A transport that answers as told, so that failures a real server cannot be made to show can be tested."""

    def __init__(self, *, verified: Fetched | Exception, unverified: Fetched | Exception | None = None) -> None:
        self._answers = {True: verified, False: unverified}
        self.calls: list[bool] = []

    def get(self, address, paths, *, verify):  # noqa: ANN001, ANN201
        self.calls.append(verify)
        answer = self._answers[verify]
        if isinstance(answer, Exception):
            raise answer
        assert answer is not None
        return answer


def good(app: str = "computes") -> Fetched:
    return Fetched({"/api/health": OK, "/api/docs": docs(app)}, None)


@pytest.mark.parametrize(("code", "expected"), [(10, "certificate_expired"), (9, "certificate_invalid")])
def test_an_expired_or_not_yet_valid_certificate_is_not_looked_at_any_further(code: int, expected: str) -> None:
    fake = Fake(verified=TlsVerifyError(code))
    outcome = run("https://demo.example.org", transport=fake)
    assert isinstance(outcome, Refused)
    assert outcome.code == expected
    assert "demo.example.org" in outcome.message
    assert fake.calls == [True]  # the unverified connection is not even made


@pytest.mark.parametrize("code", [7, 23, 24, 26, 0, 999])
def test_every_other_certificate_problem_is_a_plain_refusal(code: int) -> None:
    outcome = run("https://demo.example.org", transport=Fake(verified=TlsVerifyError(code)))
    assert isinstance(outcome, Refused)
    assert outcome.code == "certificate_invalid"


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        (18, "unknown_issuer"),
        (19, "unknown_issuer"),
        (20, "unknown_issuer"),
        (21, "unknown_issuer"),
        (62, "name_mismatch"),
        (64, "name_mismatch"),
    ],
)
@needs_openssl
def test_these_verification_failures_may_be_trusted_by_a_person(code: int, reason: str, tmp_path: Path) -> None:
    cert = self_signed(tmp_path, "c", cn="demo.example.org", san="DNS:demo.example.org")
    fake = Fake(verified=TlsVerifyError(code), unverified=Fetched(good().responses, cert.der()))
    outcome = run("https://demo.example.org", transport=fake)
    assert isinstance(outcome, NeedsTrust)
    assert outcome.reason == reason
    assert fake.calls == [True, False]


def test_an_unreadable_certificate_is_refused() -> None:
    fake = Fake(verified=TlsVerifyError(18), unverified=Fetched(good().responses, b"not a certificate"))
    outcome = run("https://demo.example.org", transport=fake)
    assert isinstance(outcome, Refused)
    assert outcome.code == "certificate_invalid"


def test_a_server_that_gives_no_certificate_at_all_is_refused() -> None:
    fake = Fake(verified=TlsVerifyError(18), unverified=Fetched(good().responses, None))
    outcome = run("https://demo.example.org", transport=fake)
    assert isinstance(outcome, Refused)
    assert outcome.code == "certificate_invalid"


def test_plain_http_never_asks_about_certificates() -> None:
    fake = Fake(verified=good())
    # (a loopback address over plain http: the transport is asked once, without TLS verification)
    fake._answers[False] = good()
    assert run("http://127.0.0.1:8420", transport=fake) == Reached(origin="http://127.0.0.1:8420", app="computes")


def test_the_check_refuses_an_address_that_the_shell_never_connects_to() -> None:
    from claudia_shell_gtk.servers import Address

    with pytest.raises(ValueError, match="loopback"):
        check(Address("http", "192.0.2.7", 8420), "computes", transport=Fake(verified=good()))
