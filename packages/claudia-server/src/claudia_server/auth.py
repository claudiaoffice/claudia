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
configured. Only the server makes that account (``Account.assistant()``), and only the server decides which protocol
methods it may call (``allowed_methods``, checked by ``MethodTable.dispatch``, SEC-10): the model that drives it
offers no guarantee of its own, so the account itself is where the limit has to live.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

ROLES = ("owner", "editor", "viewer")
WRITE_ROLES = ("owner", "editor")
_RANK = {"viewer": 0, "editor": 1, "owner": 2}
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
    """A person (or the assistant) in a document: the name that authors their edits, and what they may do.

    ``allowed_methods`` is checked by ``MethodTable.dispatch`` (SEC-10): ``None`` (the default, every ordinary
    person) means no extra limit beyond the role; a set means this account may not *write* through a method outside
    it, however the method is reached (the wire, the assistant, a future remote engine). It never limits reading."""

    user: str
    role: str = "editor"
    system: bool = field(default=False, compare=False)  # the assistant's own account; only ``assistant()`` makes one
    allowed_methods: frozenset[str] | None = field(default=None, compare=False)

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
    def assistant(cls, allowed_methods: Iterable[str] | None = None) -> Account:
        """The account of the AI assistant (E3.6). ``allowed_methods`` are the write methods it may call; production
        always gives an explicit, small set (``apps.MODEL_METHODS`` of the document's app); ``None`` (the default)
        means no limit beyond the role and is for tests that are not about this boundary."""
        names = None if allowed_methods is None else frozenset(allowed_methods)
        return cls(AI_USER, "editor", system=True, allowed_methods=names)

    def acting_for(self, asker_role: str, writes: Iterable[str] | None) -> Account:
        """The account this one works under for one request (D261): never stronger than the person who asked.

        The role is the weaker of this account's and the asker's (so the AI is never an owner, and never an editor
        for a viewer), and the methods it may write through are the ones of its own allow-list that ``writes`` also
        names (``writes=None`` adds no limit). An account with no allow-list of its own (``None``) takes ``writes``
        as it is."""
        weaker = self.role if _RANK[self.role] <= _RANK[asker_role] else asker_role
        if writes is None:
            allowed = self.allowed_methods
        else:
            names = frozenset(writes)
            allowed = names if self.allowed_methods is None else self.allowed_methods & names
        return Account(self.user, weaker, system=self.system, allowed_methods=allowed)


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


@runtime_checkable
class RecoverableDirectory(Protocol):
    """A directory whose documents have a recovery key (D105): a way back in for somebody who lost their password."""

    def new_recovery_key(self, doc_id: str) -> str:
        """Make a new recovery key for the document, replacing the old one, and return it for the owner to write
        down. The directory keeps nothing of it. ``ValueError`` with a sentence if that is not possible now."""

    def recover(self, doc_id: str, recovery_key: str, name: str, new_password: str) -> Account | None:
        """Give ``name`` the password ``new_password`` using the recovery key; the account, or ``None`` if the key is
        not the document's (a document that does not exist gives the same answer). ``ValueError`` with a sentence for
        a key that is not a key, an unacceptable name or a weak password."""


@runtime_checkable
class RosterDirectory(Protocol):
    """A directory that can list every person of a document, not just who happens to be connected right now."""

    def list_people(self, doc_id: str) -> list[Account]:
        """Everybody who may log in to this document, in the order they were added."""


@runtime_checkable
class LeavableDirectory(Protocol):
    """A directory where a person can remove themself, with nothing more than their own password."""

    def leave(self, doc_id: str, name: str, password: str) -> bool:
        """``name`` removes themself; ``False`` if ``password`` is wrong (or there is nobody of that name: the same
        refusal, D50). ``ValueError`` with a sentence if ``name`` is the document's only owner."""


@runtime_checkable
class TransferableDirectory(Protocol):
    """A directory whose documents can change who owns them (E2.3). A role is sealed inside its own slot (D102), so
    handing one over needs both people's current passwords, one at each step: the owner proposes with their own now,
    the new owner accepts with theirs when they are ready."""

    def propose_owner_transfer(self, doc_id: str, old_owner: str, old_owner_password: str, new_owner: str) -> bool:
        """``old_owner`` (who must be the document's current owner) asks ``new_owner`` (who must already be an
        editor) to become the owner instead. A later proposal for the same document replaces one that was not yet
        accepted. ``False`` if ``old_owner_password`` is wrong. ``ValueError`` with a sentence if ``old_owner`` is
        not the owner, ``new_owner`` is not currently an editor, or they are the same person."""

    def accept_owner_transfer(self, doc_id: str, new_owner: str, new_owner_password: str) -> Account | None:
        """``new_owner`` accepts a transfer proposed to them, with their own password. The new account (now the
        owner), or ``None`` for anything that keeps it from going through: nothing was proposed to them, it already
        went through, it expired, or the password is wrong — the same answer whichever it is (D50)."""


@runtime_checkable
class DeletableDirectory(Protocol):
    """A directory that can remove a whole document, not just a person in it."""

    def delete_document(self, doc_id: str, owner: str, owner_password: str) -> bool:
        """Remove the document for good: its file, its history and its chat. ``False`` if ``owner_password`` is
        wrong or ``owner`` is not currently an owner of the document (the same refusal either way); nothing is
        removed then."""


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
