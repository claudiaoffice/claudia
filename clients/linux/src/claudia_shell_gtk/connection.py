"""Can this window connect to the server at an address? (E5.8) No GTK; it blocks, so call it from a worker thread.

:func:`check` is the second and third step of the order the mock-up shows (``notes/mockups/connect-and-trust.svg``,
panel D; step 1, the address itself, is :func:`claudia_shell_gtk.servers.parse_address`):

* **reach it, check the certificate** — the server answers ``/api/health`` over TLS. A certificate that the system
  trusts needs no question. One that nobody vouches for (self-signed, an authority the system does not know, a name
  that is not the server's) is *offered to the person* as :class:`NeedsTrust`, unless it is the very certificate she
  trusted before (``trust``). One that has expired — or is not valid yet, or is broken in any other way — is never
  offered: it is refused;
* **same app** — ``/api/docs`` names the app the server runs, and it must be the app of this window. A server that
  keeps its document list behind a secret does not say; the page's own hello, which names the app, is checked again
  when the page loads (``bridge``).

Whether the server is a Claudia server and runs the right app is decided *before* the person is asked to trust its
certificate: nobody should be asked about a server that she could not use anyway.

The network is behind :class:`HttpTransport` (``ssl`` and ``http.client`` from the standard library — the shell has no
dependencies), so everything else is tested with real local servers or with a fake transport. The certificate that
is judged is the one of the **same connection** that answered, so it cannot be swapped between the check and the
answer. (The web view makes its own connection afterwards; it checks the same pin — ``webpage``.)
"""

from __future__ import annotations

import http.client
import json
import ssl
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, NamedTuple, Protocol

from . import x509
from .i18n import translate as _
from .identity import UnknownApp
from .identity import get as get_identity
from .servers import Address

__all__ = [
    "MAX_BODY",
    "Fetched",
    "HttpTransport",
    "NeedsTrust",
    "NotHttp",
    "Outcome",
    "Reached",
    "Refused",
    "Response",
    "TlsVerifyError",
    "Transport",
    "Unreachable",
    "check",
]

HEALTH_PATH = "/api/health"
DOCS_PATH = "/api/docs"
MAX_BODY = 4 * 1024 * 1024
"""Bytes read of one answer at most. A server of another kind must not be able to fill the memory."""
TIMEOUT = 8.0

# X509_V_ERR_* values that a person may overrule by trusting the very certificate (see ``trust``).
_UNKNOWN_ISSUER = frozenset({18, 19, 20, 21})  # self-signed; self-signed in chain; no local issuer; no first cert
_NAME_MISMATCH = frozenset({62, 64})  # host name / IP address does not match
_EXPIRED = 10


class Response(NamedTuple):
    status: int
    body: bytes


class Fetched(NamedTuple):
    """The answers to a list of paths, all from one connection, and the certificate that connection showed."""

    responses: Mapping[str, Response]
    certificate: bytes | None
    """DER of the server's certificate, when the connection was TLS and not verified by the system."""


class TlsVerifyError(Exception):
    """The system refused the certificate; ``code`` is OpenSSL's ``X509_V_ERR_*`` number."""

    def __init__(self, code: int) -> None:
        super().__init__(f"certificate verification failed ({code})")
        self.code = code


class Unreachable(Exception):
    """Nobody answered: refused, unknown host, no route, timed out."""


class NotHttp(Exception):
    """Somebody answered, but not with HTTP (or not within :data:`MAX_BODY`)."""


class Transport(Protocol):
    """How a check talks to a server."""

    def get(self, address: Address, paths: Sequence[str], *, verify: bool) -> Fetched:
        """GET ``paths`` over one connection. ``verify=False`` accepts any certificate and returns it (DER)."""


class HttpTransport:
    """The real transport. ``cafile`` replaces the system's authorities (tests); ``timeout`` is per network step."""

    def __init__(self, *, cafile: str | None = None, timeout: float = TIMEOUT) -> None:
        self._cafile = cafile
        self._timeout = timeout

    def _context(self, verify: bool) -> ssl.SSLContext:
        if verify:
            return ssl.create_default_context(cafile=self._cafile)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def get(self, address: Address, paths: Sequence[str], *, verify: bool) -> Fetched:
        tls = address.scheme == "https"
        connection: http.client.HTTPConnection = (
            http.client.HTTPSConnection(
                address.host, address.port, timeout=self._timeout, context=self._context(verify)
            )
            if tls
            else http.client.HTTPConnection(address.host, address.port, timeout=self._timeout)
        )
        answers: dict[str, Response] = {}
        try:
            connection.connect()
            der = connection.sock.getpeercert(binary_form=True) if tls and not verify else None  # type: ignore[union-attr]
            for path in paths:
                connection.request("GET", path, headers={"Accept": "application/json", "User-Agent": "claudia-shell"})
                reply = connection.getresponse()
                body = reply.read(MAX_BODY + 1)
                if len(body) > MAX_BODY:
                    raise NotHttp("answer too large")
                answers[path] = Response(reply.status, body)
        except ssl.SSLCertVerificationError as problem:  # before OSError: it is one
            raise TlsVerifyError(problem.verify_code) from problem
        except (ssl.SSLError, http.client.HTTPException, ValueError) as problem:
            raise NotHttp(str(problem)) from problem
        except OSError as problem:
            raise Unreachable(str(problem)) from problem
        finally:
            connection.close()
        return Fetched(answers, der)


@dataclass(frozen=True, slots=True)
class Reached:
    """The server answers, is a Claudia server, and (when it said) runs this window's app."""

    origin: str
    app: str | None
    """The app the server named, or ``None`` when it did not say (the hello check remains)."""
    fingerprint: str | None = None
    """The trusted certificate that was shown, when the connection relied on one."""


@dataclass(frozen=True, slots=True)
class Refused:
    """A stop. ``code`` is one of ``contract.CONNECT_FAILED_CODES``; ``message`` is written for the person."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class NeedsTrust:
    """The server is the right one, but its certificate is not vouched for: the person decides (dialogs A and B)."""

    origin: str
    app: str | None
    certificate: x509.Certificate
    reason: Literal["unknown_issuer", "name_mismatch"]
    previous: str | None
    """The fingerprint trusted before when it is *another* certificate now (dialog B), else ``None`` (dialog A)."""


Outcome = Reached | Refused | NeedsTrust


def _refused(code: str, message: str) -> Refused:
    return Refused(code, message)


def _not_claudia() -> Refused:
    return _refused("not_claudia", _("That does not look like a Claudia server."))


def _json(response: Response) -> object:
    try:
        return json.loads(response.body)
    except ValueError:
        return None


def _interpret(fetched: Fetched, expected_app: str) -> Refused | str | None:
    """Is this a Claudia server of ``expected_app``? A refusal, or the app it named (``None`` if it did not say)."""
    health = fetched.responses.get(HEALTH_PATH)
    body = _json(health) if health is not None and health.status == 200 else None
    if not (isinstance(body, dict) and body.get("ok") is True):
        return _not_claudia()
    docs = fetched.responses.get(DOCS_PATH)
    if docs is None or docs.status in (401, 403, 404):
        return None
    listing = _json(docs) if docs.status == 200 else None
    app = listing.get("app") if isinstance(listing, dict) else None
    try:
        other = get_identity(app) if isinstance(app, str) else None
    except UnknownApp:
        other = None
    if other is None:
        return _not_claudia()
    if app != expected_app:
        return _refused(
            "wrong_app",
            _("That server runs {other}. This window is {this} — open it there.").format(
                other=other.title, this=get_identity(expected_app).title
            ),
        )
    return app


def _certificate_refusal(code: int, host: str) -> Refused:
    if code == _EXPIRED:
        return _refused(
            "certificate_expired",
            _("The certificate of {host} has expired. Ask its administrator to renew it.").format(host=host),
        )
    return _refused("certificate_invalid", _("The certificate of {host} is not valid.").format(host=host))


def check(
    address: Address,
    expected_app: str,
    *,
    trusted: Mapping[str, Mapping[str, str]] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    transport: Transport | None = None,
) -> Outcome:
    """What happens when this window (of ``expected_app``) connects to ``address`` — see the module docstring.

    ``trusted`` is ``TrustStore.snapshot()``. Blocks for up to a few seconds: never call it from the GTK main loop.
    """
    if address.scheme == "http" and not address.is_loopback:
        raise ValueError("plain http is only for a loopback address")
    transport = transport or HttpTransport()
    paths = (HEALTH_PATH, DOCS_PATH)
    origin = address.origin
    try:
        if address.scheme == "http":
            return _decide(transport.get(address, paths, verify=False), expected_app, origin)
        try:
            return _decide(transport.get(address, paths, verify=True), expected_app, origin)
        except TlsVerifyError as problem:
            if problem.code not in _UNKNOWN_ISSUER | _NAME_MISMATCH:
                return _certificate_refusal(problem.code, address.host)
            reason: Literal["unknown_issuer", "name_mismatch"] = (
                "name_mismatch" if problem.code in _NAME_MISMATCH else "unknown_issuer"
            )
        return _unverified(
            transport,
            address,
            paths=paths,
            expected_app=expected_app,
            reason=reason,
            trusted=trusted or {},
            moment=now(),
        )
    except Unreachable:
        from .servers import default_label

        return _refused("unreachable", _("Could not reach {address}.").format(address=default_label(origin)))
    except (NotHttp, TlsVerifyError):
        return _not_claudia()


def _decide(fetched: Fetched, expected_app: str, origin: str) -> Outcome:
    verdict = _interpret(fetched, expected_app)
    return verdict if isinstance(verdict, Refused) else Reached(origin=origin, app=verdict)


def _unverified(
    transport: Transport,
    address: Address,
    *,
    paths: Sequence[str],
    expected_app: str,
    reason: Literal["unknown_issuer", "name_mismatch"],
    trusted: Mapping[str, Mapping[str, str]],
    moment: datetime,
) -> Outcome:
    """The system does not vouch for the certificate: look at it, answer for the app, then let the person judge."""
    origin = address.origin
    fetched = transport.get(address, paths, verify=False)
    if fetched.certificate is None:
        return _certificate_refusal(0, address.host)
    try:
        certificate = x509.parse(fetched.certificate)
    except x509.CertificateError:
        return _certificate_refusal(0, address.host)
    if not certificate.is_valid_at(moment):
        return _certificate_refusal(_EXPIRED if moment > certificate.not_after else 0, address.host)
    verdict = _interpret(fetched, expected_app)
    if isinstance(verdict, Refused):
        return verdict
    pin = (trusted.get(origin) or {}).get("sha256")
    if pin == certificate.sha256:
        return Reached(origin=origin, app=verdict, fingerprint=pin)
    return NeedsTrust(origin=origin, app=verdict, certificate=certificate, reason=reason, previous=pin)
