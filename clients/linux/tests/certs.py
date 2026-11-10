"""Certificates for the tests, made with the ``openssl`` command line (tests skip when it is not installed)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

OPENSSL = shutil.which("openssl")
needs_openssl = pytest.mark.skipif(OPENSSL is None, reason="the openssl command is not installed")


@dataclass(frozen=True)
class Made:
    """A certificate and its private key, as files."""

    cert: Path
    key: Path

    def der(self) -> bytes:
        result = _run("x509", "-in", str(self.cert), "-outform", "DER")
        return result.stdout


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    assert OPENSSL is not None
    return subprocess.run([OPENSSL, *args], check=True, capture_output=True, cwd=cwd)  # noqa: S603


def self_signed(
    folder: Path,
    name: str,
    *,
    cn: str = "localhost",
    san: str = "DNS:localhost,IP:127.0.0.1",
    days: int = 30,
    org: str | None = None,
) -> Made:
    """A self-signed certificate valid for ``days`` days from now."""
    cert, key = folder / f"{name}.pem", folder / f"{name}.key"
    subject = f"/CN={cn}" + (f"/O={org}" if org else "")
    _run(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(key),
        "-out",
        str(cert),
        "-days",
        str(days),
        "-subj",
        subject,
        "-addext",
        f"subjectAltName={san}",
    )
    return Made(cert, key)


def issued_by(
    folder: Path,
    name: str,
    authority: Made,
    *,
    cn: str = "localhost",
    san: str = "DNS:localhost,IP:127.0.0.1",
    days: int = 30,
) -> Made:
    """A certificate for ``cn`` signed by ``authority`` (itself a self-signed certificate that may sign)."""
    cert, key = folder / f"{name}.pem", folder / f"{name}.key"
    request, extension = folder / f"{name}.csr", folder / f"{name}.ext"
    _run(
        "req", "-new", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(request), "-subj", f"/CN={cn}"
    )
    extension.write_text(f"subjectAltName={san}\n", encoding="utf-8")
    _run(
        "x509",
        "-req",
        "-in",
        str(request),
        "-CA",
        str(authority.cert),
        "-CAkey",
        str(authority.key),
        "-CAcreateserial",
        "-out",
        str(cert),
        "-days",
        str(days),
        "-extfile",
        str(extension),
    )
    return Made(cert, key)


def authority(folder: Path, name: str, *, cn: str = "Test Authority") -> Made:
    """A self-signed certificate that may sign others."""
    cert, key = folder / f"{name}.pem", folder / f"{name}.key"
    _run(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(key),
        "-out",
        str(cert),
        "-days",
        "30",
        "-subj",
        f"/CN={cn}/O=Test Org",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
        "-addext",
        "keyUsage=critical,keyCertSign",
    )
    return Made(cert, key)


def openssl_fact(cert: Path, option: str) -> str:
    """One line of ``openssl x509 -noout <option>``, minus its ``name=`` label."""
    out = _run("x509", "-in", str(cert), "-noout", *option.split()).stdout.decode().strip()
    return out.split("=", 1)[1] if "=" in out else out
