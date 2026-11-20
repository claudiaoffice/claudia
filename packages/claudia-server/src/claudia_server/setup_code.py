"""The setup code: proof that whoever names a server's first administrator runs the server (SEC-12, D1370, D1371).

While a server has no administrator, anyone who reaches its settings pages could otherwise name one, and an
administrator can make the server run programs (SEC-16). So the server makes a code at every start that ends with
nobody named, says it only where its operator looks — the start banner (its log) and ``admin/setup-code`` in its
state folder, readable by its own account — and ``setup`` asks for it. The server never sends it: no answer of any
request contains it. The desktop apps read the file and hand the code to their own page (D1373).

A code is 12 characters of Crockford's base32 (60 bits), shown in groups of four. Typing it, case, dashes and spaces
do not matter, and the letters people mistake for digits count as those digits (O as 0, I and L as 1)."""

from __future__ import annotations

import contextlib
import hmac
import secrets
from dataclasses import dataclass
from pathlib import Path

from .server_settings import admin_dir
from .state import private_dir, write_private

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
"""The digits and letters of Crockford's base32, which leaves out I, L, O and U."""
LENGTH = 12
CODE_FILE = "setup-code"
_LOOK_ALIKES = str.maketrans({"O": "0", "I": "1", "L": "1"})


def normalize(text: str) -> str:
    """A typed code as it is compared: upper case, without dashes and white space, O as 0, I and L as 1."""
    return "".join(text.split()).replace("-", "").upper().translate(_LOOK_ALIKES)


@dataclass(frozen=True)
class SetupCode:
    """One server run's setup code. ``value`` is the bare code (``K7QM4TXR92HB``); ``str()`` gives it in groups."""

    value: str

    def __post_init__(self) -> None:
        if len(self.value) != LENGTH or not set(self.value) <= set(ALPHABET):
            raise ValueError(f"a setup code is {LENGTH} characters of Crockford's base32")

    @classmethod
    def of(cls, text: str) -> SetupCode:
        """The code ``text`` writes, as typed (see :func:`normalize`). ``ValueError`` if it is not one."""
        return cls(normalize(text))

    @classmethod
    def make(cls) -> SetupCode:
        """A new random code (``secrets``)."""
        return cls("".join(secrets.choice(ALPHABET) for _ in range(LENGTH)))

    def matches(self, given: object) -> bool:
        """Is ``given`` (as typed) this code? Compared in constant time; anything but a string is not."""
        if not isinstance(given, str):
            return False
        return hmac.compare_digest(normalize(given).encode("utf-8"), self.value.encode("utf-8"))

    def __str__(self) -> str:
        return "-".join(self.value[i : i + 4] for i in range(0, LENGTH, 4))


def code_path(state_dir: Path) -> Path:
    """Where the code of the running server is written under ``state_dir``."""
    return admin_dir(state_dir) / CODE_FILE


def write_code(state_dir: Path, code: SetupCode) -> None:
    """Write ``code`` for the server's own account only (the folder 0700, the file 0600, replaced atomically)."""
    private_dir(admin_dir(state_dir))
    write_private(code_path(state_dir), f"{code}\n".encode())


def read_code(state_dir: Path) -> SetupCode | None:
    """The code written under ``state_dir``, or ``None`` if there is none or the file is not a code."""
    try:
        return SetupCode.of(code_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def remove_code(state_dir: Path) -> None:
    """Remove the file, if there is one (once an administrator exists, or at a start that needs no code)."""
    with contextlib.suppress(FileNotFoundError):
        code_path(state_dir).unlink()
