"""The few facts about a server certificate that a person is asked to judge (E5.8). No GTK, no third-party package.

The shell runs on the distribution's Python and has no dependencies (``pyproject.toml``), so this reads the DER
encoding of an X.509 certificate itself — only what the "Trust this server?" dialog shows: who it is for, who issued
it, until when it is valid, the alternative names, whether it signed itself, and its SHA-256 fingerprint. It does
**not** verify anything: whether a certificate may be trusted is decided by the TLS library (``ssl``) and by the
person, never by this parser. Whatever is not a well-formed certificate is a :class:`CertificateError`, not a crash:
the bytes come from a server that has not been trusted yet.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

__all__ = ["Certificate", "CertificateError", "parse"]

_MAX_DISPLAY = 80
_OIDS = {
    b"\x55\x04\x03": "CN",
    b"\x55\x04\x0a": "O",
    b"\x55\x04\x0b": "OU",
}
_SAN_OID = b"\x55\x1d\x11"

_SEQUENCE, _SET, _INTEGER, _OID, _BOOLEAN, _OCTET_STRING = 0x30, 0x31, 0x02, 0x06, 0x01, 0x04
_UTC_TIME, _GENERALIZED_TIME = 0x17, 0x18
_CONTEXT_0, _CONTEXT_3 = 0xA0, 0xA3
_DNS_NAME, _IP_ADDRESS = 0x82, 0x87


class CertificateError(ValueError):
    """The bytes are not a certificate this module can read."""


@dataclass(frozen=True, slots=True)
class Certificate:
    """What a person needs to know to decide whether to trust a server's certificate."""

    subject: str
    """Who it is for. The common name, else the organisation, else the unit; ``""`` if the name has none of them."""
    issuer: str
    """Who vouched for it, named the same way."""
    not_before: datetime
    not_after: datetime
    names: tuple[str, ...]
    """The addresses it is valid for (DNS names and IP addresses)."""
    self_signed: bool
    """Does the issuer's name equal the subject's? (A claim of the certificate, not a verified fact.)"""
    sha256: str
    """The fingerprint, 64 lower case hex digits of the SHA-256 of the DER encoding."""

    def is_valid_at(self, moment: datetime) -> bool:
        """Is ``moment`` (timezone-aware) between the first and the last day of validity?"""
        return self.not_before <= moment <= self.not_after


class _Reader:
    """Walks the type-length-value elements of a DER string, never past its end."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._at = 0

    def done(self) -> bool:
        return self._at >= len(self._data)

    def next(self) -> tuple[int, bytes, bytes]:
        """The next element as (tag, content, whole element including its header)."""
        data, start = self._data, self._at
        if start + 2 > len(data):
            raise CertificateError("truncated")
        tag, first = data[start], data[start + 1]
        at = start + 2
        if first < 0x80:
            length = first
        else:
            size = first & 0x7F
            if size == 0 or size > 4 or at + size > len(data):
                raise CertificateError("bad length")  # also the "indefinite" form, which DER does not allow
            length = int.from_bytes(data[at : at + size], "big")
            at += size
        if at + length > len(data):
            raise CertificateError("truncated")
        self._at = at + length
        return tag, data[at : at + length], data[start : at + length]

    def expect(self, tag: int) -> tuple[bytes, bytes]:
        found, content, whole = self.next()
        if found != tag:
            raise CertificateError(f"expected tag {tag:#x}, found {found:#x}")
        return content, whole


def _text(tag: int, raw: bytes) -> str:
    try:
        if tag == 0x1E:  # BMPString
            text = raw.decode("utf-16-be")
        elif tag in (0x14, 0x1B):  # T61String and friends: in practice Latin-1
            text = raw.decode("latin-1")
        else:
            text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    # The text is shown in a dialog: a line break or a control character must not be able to fake a second line.
    clean = "".join(ch if ch.isprintable() else "?" for ch in text)
    return clean if len(clean) <= _MAX_DISPLAY else clean[: _MAX_DISPLAY - 1] + "…"


def _name(content: bytes) -> str:
    """The most telling part of a distinguished name: CN, else O, else OU."""
    found: dict[str, str] = {}
    sets = _Reader(content)
    while not sets.done():
        group, _ = sets.expect(_SET)
        pairs = _Reader(group)
        while not pairs.done():
            pair, _ = pairs.expect(_SEQUENCE)
            reader = _Reader(pair)
            oid, _ = reader.expect(_OID)
            tag, value, _ = reader.next()
            label = _OIDS.get(oid)
            if label and label not in found:
                found[label] = _text(tag, value)
    return found.get("CN") or found.get("O") or found.get("OU") or ""


def _time(reader: _Reader) -> datetime:
    tag, content, _ = reader.next()
    try:
        text = content.decode("ascii")
        if tag == _UTC_TIME and len(text) == 13 and text.endswith("Z"):
            year = int(text[:2])
            year += 1900 if year >= 50 else 2000
            rest = text[2:-1]
        elif tag == _GENERALIZED_TIME and len(text) == 15 and text.endswith("Z"):
            year, rest = int(text[:4]), text[4:-1]
        else:
            raise CertificateError("unknown time format")
        return datetime(
            year, int(rest[0:2]), int(rest[2:4]), int(rest[4:6]), int(rest[6:8]), int(rest[8:10]), tzinfo=UTC
        )
    except (UnicodeDecodeError, ValueError) as problem:
        raise CertificateError("bad time") from problem


def _ip(raw: bytes) -> str | None:
    import ipaddress

    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def _alternative_names(extensions: bytes) -> tuple[str, ...]:
    names: list[str] = []
    listing, _ = _Reader(extensions).expect(_SEQUENCE)
    items = _Reader(listing)
    while not items.done():
        body, _ = items.expect(_SEQUENCE)
        reader = _Reader(body)
        oid, _ = reader.expect(_OID)
        tag, content, _ = reader.next()
        if tag == _BOOLEAN:  # "critical"
            tag, content, _ = reader.next()
        if oid != _SAN_OID or tag != _OCTET_STRING:
            continue
        general, _ = _Reader(content).expect(_SEQUENCE)
        entries = _Reader(general)
        while not entries.done():
            kind, value, _ = entries.next()
            if kind == _DNS_NAME:
                names.append(_text(0x16, value))
            elif kind == _IP_ADDRESS and (address := _ip(value)):
                names.append(address)
    return tuple(names)


def parse(der: bytes) -> Certificate:
    """The facts about the certificate encoded in ``der``, or :class:`CertificateError`."""
    try:
        certificate, _ = _Reader(der).expect(_SEQUENCE)
        tbs, _ = _Reader(certificate).expect(_SEQUENCE)
        reader = _Reader(tbs)
        tag, content, whole = reader.next()
        if tag == _CONTEXT_0:  # the version; v1 certificates have none
            reader.expect(_INTEGER)  # the serial number
        elif tag != _INTEGER:
            raise CertificateError("no serial number")
        reader.expect(_SEQUENCE)  # signature algorithm
        issuer, issuer_whole = reader.expect(_SEQUENCE)
        validity, _ = reader.expect(_SEQUENCE)
        times = _Reader(validity)
        not_before, not_after = _time(times), _time(times)
        subject, subject_whole = reader.expect(_SEQUENCE)
        reader.expect(_SEQUENCE)  # the public key
        names: tuple[str, ...] = ()
        while not reader.done():
            tag, content, _ = reader.next()
            if tag == _CONTEXT_3:
                names = _alternative_names(content)
    except CertificateError:
        raise
    except (IndexError, ValueError) as problem:  # not meant to happen: the reader checks every bound
        raise CertificateError(str(problem)) from problem
    return Certificate(
        subject=_name(subject),
        issuer=_name(issuer),
        not_before=not_before,
        not_after=not_after,
        names=names,
        self_signed=issuer_whole == subject_whole,
        sha256=hashlib.sha256(der).hexdigest(),
    )
