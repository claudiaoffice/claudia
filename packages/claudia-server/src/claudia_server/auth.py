"""Who is connecting, and what may they do (E3.1).

People log in with a **name and a password that belong to one document**: there is no central user database
anywhere (D20, D35). The server asks a ``UserDirectory`` whether ``(document, name, password)`` is a user of that
document and gets an ``Account`` back, or ``None`` for anything that is not (wrong password, unknown name, unknown
document, missing credentials: always the same answer, so nothing can be learned about who exists).

The account's ``user`` becomes the *author* of its edits (it selects the undo history and shows up in every
update); its ``role`` decides whether it may write.

The directory that really matters lives inside the document file (E2.3, users and roles in the container).
``ScryptDirectory`` is the in-memory stand-in with the same interface, used by tests and by a development server;
the passwords in it are stored as scrypt hashes with a random salt, never as they are.

The name ``ai`` belongs to the assistant (E3.6): nobody can log in under it or be given it, however the server is
configured. Only the server makes that account (``Account.assistant()``).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Protocol

ROLES = ("owner", "editor", "viewer")
WRITE_ROLES = ("owner", "editor")
MIN_PASSWORD = 8
AI_USER = "ai"  # the assistant's name in every document: nobody else may use it
AI_COLOR = "#5b4bc4"  # Iris, the colour of the assistant everywhere
_NAME = re.compile(r"[\w .@-]{1,40}")


def normalized(name: str) -> str:
    """The form in which names are compared: Unicode-compatible, case-folded, single-spaced."""
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def is_reserved(name: str) -> bool:
    """Is ``name`` the assistant's (whatever its case, spacing or Unicode form)?"""
    return normalized(name) == AI_USER


class AuthRefused(Exception):
    """The credentials cannot be used and the message says why; it is shown to the person."""


@dataclass(frozen=True)
class Credentials:
    """What a person typed: a name and a password (either may be missing in a malformed request)."""

    user: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class Account:
    """A person (or the assistant) in a document: the name that authors their edits, and what they may do."""

    user: str
    role: str = "editor"
    system: bool = field(default=False, compare=False)  # the assistant's own account; only ``assistant()`` makes one

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        if not _NAME.fullmatch(self.user):
            raise ValueError(f"invalid user name {self.user!r}")
        if is_reserved(self.user) and not self.system:
            raise ValueError(f"the user name {AI_USER!r} is reserved for the AI assistant")

    @property
    def can_write(self) -> bool:
        """May this account change the document?"""
        return self.role in WRITE_ROLES

    @classmethod
    def assistant(cls) -> Account:
        """The account of the AI assistant (E3.6)."""
        return cls(AI_USER, "editor", system=True)


class UserDirectory(Protocol):
    """Where the users of a document are kept (inside the document file, E2.3)."""

    def verify(self, doc_id: str, credentials: Credentials) -> Account | None:
        """The account if ``credentials`` are a user of ``doc_id``; ``None`` for anything else.

        Raises ``AuthRefused`` for a name nobody may log in with."""

    def add_user(self, doc_id: str, name: str, password: str, role: str = "editor") -> Account:
        """Add a user to a document (the first one, the owner, when the document is created). ``ValueError`` with a
        message fit for the person if the name, role or password is not acceptable or the name is taken."""

    def remove_user(self, doc_id: str, name: str) -> None:
        """Remove a user; ``KeyError`` if there is none of that name."""


@dataclass(frozen=True)
class _Record:
    account: Account
    salt: bytes
    digest: bytes


class ScryptDirectory:
    """Users held in memory, passwords as scrypt hashes. The stand-in for the directory inside the document."""

    def __init__(self, cost: int = 2**14):
        self._cost = cost
        self._users: dict[tuple[str, str], _Record] = {}
        self._decoy = self._hash("no such user", b"\0" * 16)

    def _hash(self, password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(password.encode(), salt=salt, n=self._cost, r=8, p=1)

    def add_user(self, doc_id: str, name: str, password: str, role: str = "editor") -> Account:
        """Add a user to a document. ``ValueError`` for a bad name or role, a short password or a name taken."""
        account = Account(name, role)  # validates name, role and the reserved name
        if len(password) < MIN_PASSWORD:
            raise ValueError(f"the password needs at least {MIN_PASSWORD} characters")
        key = (doc_id, normalized(name))
        if key in self._users:
            raise ValueError(f"{name!r} is already a user of {doc_id}")
        salt = os.urandom(16)
        self._users[key] = _Record(account, salt, self._hash(password, salt))
        return account

    def remove_user(self, doc_id: str, name: str) -> None:
        """Remove a user; ``KeyError`` if there is none of that name."""
        del self._users[(doc_id, normalized(name))]

    def dump(self) -> dict:
        """The users as plain data (salts and hashes, never passwords), for a directory that keeps them on disk."""
        users = [
            {
                "doc": doc_id,
                "user": rec.account.user,
                "role": rec.account.role,
                "salt": rec.salt.hex(),
                "hash": rec.digest.hex(),
            }
            for (doc_id, _), rec in sorted(self._users.items())
        ]
        return {"cost": self._cost, "users": users}

    def load(self, data: dict) -> None:
        """Replace the users with those of ``dump``. The cost parameter of the data is kept (hashes depend on it)."""
        self._cost = int(data["cost"])
        self._decoy = self._hash("no such user", b"\0" * 16)
        self._users = {
            (item["doc"], normalized(item["user"])): _Record(
                Account(item["user"], item["role"]), bytes.fromhex(item["salt"]), bytes.fromhex(item["hash"])
            )
            for item in data["users"]
        }

    def verify(self, doc_id: str, credentials: Credentials) -> Account | None:
        """The account if name and password match a user of ``doc_id``, else ``None``."""
        name, password = credentials.user, credentials.password
        if isinstance(name, str) and is_reserved(name):
            raise AuthRefused(f"The name “{AI_USER}” belongs to the AI assistant. Choose another name.")
        if not (isinstance(name, str) and isinstance(password, str)):
            return None
        record = self._users.get((doc_id, normalized(name)))
        # An unknown name costs one hash as well, so the time does not tell which names are users.
        expected = record.digest if record else self._decoy
        given = self._hash(password, record.salt if record else b"\0" * 16)
        matches = hmac.compare_digest(expected, given)
        return record.account if record and matches else None
