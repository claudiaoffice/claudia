"""Who may configure this server — a separate identity from any document's users.

A document's users live inside that document, with no central directory anywhere (D20, D35): that is what keeps
Claudia's privacy model simple. A server's *administrators* are a different thing entirely. Configuring the AI
model, the LaTeX installation, the access secret or the document cap has nothing to do with any one document, so
it is kept once, for the server itself, never inside a document and never shared between servers.

On a server that only answers to this computer (``--host 127.0.0.1``, the default), nobody needs to be an
administrator: whoever is running the process already controls it, and asking them to sign in to their own laptop
would be exactly the kind of friction this project tries to avoid for people who never touch a server flag. The
moment the server is told to listen on anything else, more than one person could plausibly reach its settings, so
it needs exactly one administrator before those settings do anything but ask for one (``needs_administrator``).
After that, administrators manage themselves and each other the same way a document's first owner invites the
next (D50) — there is no super-user above them, and removing the last one is refused outright.

Passwords are scrypt hashes with a random salt, the same scheme as a document's own users
(:class:`claudia_server.auth.ScryptDirectory`); this directory is simpler because there is only ever one server's
worth of names to key on, not one per document."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import unicodedata
from dataclasses import dataclass

MIN_ADMIN_PASSWORD = 8
_NAME = re.compile(r"[\w .@-]{1,40}")
_DECOY_PASSWORD = "no such administrator"


def normalized(name: str) -> str:
    """The form in which administrator names are compared: Unicode-compatible, case-folded, single-spaced."""
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


@dataclass(frozen=True)
class AdminAccount:
    """One administrator: a name and when they were added. Never the password, and nothing document-shaped
    (no role: every administrator can do everything a settings page offers)."""

    name: str
    added: str  # ISO 8601 UTC, claudia_core.clock.utc_now()

    def __post_init__(self):
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"invalid administrator name {self.name!r}")


@dataclass(frozen=True)
class _Record:
    account: AdminAccount
    salt: bytes
    digest: bytes


class AdminDirectory:
    """The server's administrators, held in memory and (see ``server_settings.py``) written to ``admins.json``
    under the server's state folder, so they survive a restart. A server always has at least one administrator
    once it has any: :meth:`remove` refuses to take the last one away."""

    def __init__(self, cost: int = 2**14):
        self._cost = cost
        self._admins: dict[str, _Record] = {}
        self._decoy = self._hash(_DECOY_PASSWORD, b"\0" * 16)

    def _hash(self, password: str, salt: bytes) -> bytes:
        return hashlib.scrypt(password.encode(), salt=salt, n=self._cost, r=8, p=1)

    def __len__(self) -> int:
        return len(self._admins)

    def list_admins(self) -> list[AdminAccount]:
        """Every administrator, in the order they were added."""
        return [record.account for record in self._admins.values()]

    def add(self, name: str, password: str, *, added: str) -> AdminAccount:
        """Add an administrator. ``ValueError`` for a bad name, a short password, or a name already taken."""
        account = AdminAccount(name, added)  # validates the name
        if len(password) < MIN_ADMIN_PASSWORD:
            raise ValueError(f"the password needs at least {MIN_ADMIN_PASSWORD} characters")
        key = normalized(name)
        if key in self._admins:
            raise ValueError(f"{name!r} is already an administrator")
        salt = os.urandom(16)
        self._admins[key] = _Record(account, salt, self._hash(password, salt))
        return account

    def remove(self, name: str) -> None:
        """Remove an administrator. ``KeyError`` if there is none of that name. ``ValueError`` if it is the last
        one: a server must always have somebody who can configure it."""
        key = normalized(name)
        if key not in self._admins:
            raise KeyError(name)
        if len(self._admins) <= 1:
            raise ValueError("the last administrator cannot be removed")
        del self._admins[key]

    def verify(self, name: object, password: object) -> AdminAccount | None:
        """The administrator if ``name`` and ``password`` match, else ``None``.

        An unknown name costs one hash as well (the decoy), so the time taken does not tell which names exist."""
        if not (isinstance(name, str) and isinstance(password, str)):
            return None
        record = self._admins.get(normalized(name))
        expected = record.digest if record else self._decoy
        given = self._hash(password, record.salt if record else b"\0" * 16)
        matches = hmac.compare_digest(expected, given)
        return record.account if record and matches else None

    def change_password(self, name: str, password: str) -> None:
        """Change an administrator's own password. ``KeyError`` if there is none of that name. ``ValueError`` for a
        password that is too short."""
        key = normalized(name)
        if key not in self._admins:
            raise KeyError(name)
        if len(password) < MIN_ADMIN_PASSWORD:
            raise ValueError(f"the password needs at least {MIN_ADMIN_PASSWORD} characters")
        record = self._admins[key]
        salt = os.urandom(16)
        self._admins[key] = _Record(record.account, salt, self._hash(password, salt))

    def dump(self) -> dict:
        """The administrators as plain data (salts and hashes, never passwords), for writing to disk."""
        admins = [
            {"name": rec.account.name, "added": rec.account.added, "salt": rec.salt.hex(), "hash": rec.digest.hex()}
            for rec in self._admins.values()
        ]
        return {"cost": self._cost, "admins": admins}

    def load(self, data: dict) -> None:
        """Replace the administrators with those of :meth:`dump`. The cost parameter of the data is kept (hashes
        depend on it)."""
        self._cost = int(data["cost"])
        self._decoy = self._hash(_DECOY_PASSWORD, b"\0" * 16)
        self._admins = {
            normalized(item["name"]): _Record(
                AdminAccount(item["name"], item["added"]), bytes.fromhex(item["salt"]), bytes.fromhex(item["hash"])
            )
            for item in data["admins"]
        }


def needs_administrator(exposed: bool, admin_count: int) -> bool:
    """Should the server ask somebody to become its first administrator?

    Only ever once, and only when it matters: a server that answers to this computer alone (``exposed`` is
    ``False``) trusts whoever is running it and never asks, whether or not it has administrators. The moment it is
    told to listen beyond that, it needs exactly one before its settings pages do anything but offer to make one."""
    return exposed and admin_count == 0
