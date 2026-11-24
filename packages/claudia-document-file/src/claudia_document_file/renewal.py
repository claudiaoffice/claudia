"""Changing who may do what in an open document, and renewing keys when somebody loses some (E2.3, D1263, D1274).

* **Removing a person** renews every part key she held (a viewer: the content key; an editor or an owner: all three).
* **Lowering an editor or an owner to viewer** renews the history key and the chat key. The content key stays: a viewer
  holds it.
* **Raising a person**, or moving between editor and owner, renews nothing: it gives away only what the owner meant to
  give.

The rest of the file is sealed again under the new keys in **one atomic replacement** (the chains of blocks, the
record of what left, the head, the list of people, the kept original; the journal is folded in first, like packing does,
and starts again under the new keys). A crash leaves the old file or the new one, and a journal that the new file has
already taken in is ignored and replaced, as after packing.

The people who stay, and the recovery key, are given the new keys through their **inbox**
(:mod:`claudia_document_file.inbox`): a letter sealed to the public key of each, which her slot opens at her next login.
The person who is removed gets nothing, and her slot, her inbox and her private notes are deleted.

What this does not do: the person keeps what she has seen and every copy of the file that she holds, which her old keys
still open (D20). The new keys protect what is written from now on from anyone who holds only the old ones.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import blocks
from .blocks import Head, seal_head
from .crypto import DecryptionError, open_sealed, random_key, seal
from .file import (
    _HEAD,
    _ORIGINAL,
    _SNAPSHOT,
    _WRITE_LOCK,
    DocumentFileError,
    TamperedDocument,
    _carried,
    _changed,
    _consent_entries,
    _extend,
    _inbox_name,
    _journal_records,
    _letter,
    _load_chains,
    _manifest_of,
    _normalised,
    _open_folder_chain,
    _open_people_data,
    _original_aad,
    _people_blob,
    _read_entries,
    _require_all_keys,
    _sealed_chain,
    _slots_of,
    _snapshot_aad,
    _without_entry,
    _without_private,
    _write_zip,
    journal_path,
)
from .journal import JournalWriter
from .slots import ROLE_PARTS, Part, Role


class RenewalInterrupted(DocumentFileError):
    """The file already has the new keys, but the journal could not be started under them (the disk, say). Nothing is
    lost: ``keys`` are the new keys, and :func:`~claudia_document_file.begin` with them replaces the old journal, which
    the file has taken in."""

    def __init__(self, message: str, keys: dict[Part, bytes]) -> None:
        super().__init__(message)
        self.keys = keys


@dataclass(frozen=True)
class Renewed:
    """What a change of the people left behind: the keys of the document now (those of the owner who made the change,
    so all three), the writer of the journal (a new one if keys were renewed; the old one is closed then) and which
    part keys are new."""

    keys: dict[Part, bytes] = field(repr=False)  # secrets: never in a log line or a traceback (SEC-23)
    writer: JournalWriter
    renewed: frozenset[Part]


def change_role(
    path: Path,
    keys: Mapping[Part, bytes],
    writer: JournalWriter,
    name: str,
    role: Role,
    *,
    snapshot: bytes | None = None,
) -> Renewed:
    """Give ``name`` this role. ``keys`` are the document's (all three: ``PermissionError`` for anybody else).

    ``KeyError`` if there is nobody of that name, ``ValueError`` for the last owner. The same role changes nothing.
    ``snapshot`` becomes the snapshot of the file if keys are renewed (``None`` leaves the file without one, as after
    ``rewrite_journal``)."""
    return _change(path, keys, writer, name, role, snapshot)


def remove_person(
    path: Path, keys: Mapping[Part, bytes], writer: JournalWriter, name: str, *, snapshot: bytes | None = None
) -> Renewed:
    """Remove ``name`` and renew the keys she held. Her slot, her inbox and her private notes are deleted.

    ``KeyError`` if there is nobody of that name, ``ValueError`` for the last owner. See :func:`change_role`."""
    return _change(path, keys, writer, name, None, snapshot)


def _change(
    path: Path,
    keys: Mapping[Part, bytes],
    writer: JournalWriter,
    name: str,
    role: Role | None,
    snapshot: bytes | None,
) -> Renewed:
    _require_all_keys(keys)
    with _WRITE_LOCK:
        entries = _read_entries(path)
        manifest = _manifest_of(entries, path)
        people, recovery = _open_people_data(entries, manifest, keys)
        target = next((p for p in people if _normalised(p.name) == _normalised(name)), None)
        if target is None:
            raise KeyError(name)
        if role is target.role:
            return Renewed(dict(keys), writer, frozenset())
        others = [p for p in people if p is not target]
        if target.role is Role.OWNER and not any(p.role is Role.OWNER for p in others):
            raise ValueError("a document must keep at least one owner")
        if role is None:
            renewed, remaining = frozenset(ROLE_PARTS[target.role]), others
        else:
            lowered = target.role is not Role.VIEWER and role is Role.VIEWER
            renewed = frozenset({Part.HISTORY, Part.CHAT}) if lowered else frozenset()
            remaining = [replace(p, role=role) if p is target else p for p in people]
        new_keys = {part: random_key() if part in renewed else key for part, key in keys.items()}

        # who gets a letter: everybody who stays if keys are new, else only the person whose role changed
        recipients = remaining if renewed else [p for p in remaining if p.locator == target.locator]
        letters = {
            _inbox_name(p.locator): _letter(manifest, p.locator, p.public_key, p.role, new_keys) for p in recipients
        }
        if renewed and recovery is not None:
            letters[_inbox_name(recovery.locator)] = _letter(
                manifest, recovery.locator, recovery.public_key, Role.OWNER, new_keys
            )
        slots = _slots_of(entries, path)
        carried = _carried(entries)
        if role is None:
            slots = [s for s in slots if s.locator != target.locator]
            carried = _without_entry(_without_private(carried, target.private_id), _inbox_name(target.locator))
        blob = _people_blob(manifest, new_keys[Part.CONTENT], remaining, recovery)
        if not renewed:
            _write_zip(path, _changed(manifest), slots, blob, {**carried, **letters}, exclusive=False)
            return Renewed(dict(keys), writer, renewed)
        sealed = _resealed(path, entries, manifest, keys, new_keys, renewed, writer.generation, snapshot)
        kept = {n: d for n, d in carried.items() if n not in sealed.replaced}
        _write_zip(path, _changed(manifest), slots, blob, {**kept, **sealed.entries, **letters}, exclusive=False)
        generation = writer.generation
        writer.close()
        try:
            fresh = JournalWriter.replace(journal_path(path), manifest.binding, new_keys, generation + 1)
        except OSError as error:
            raise RenewalInterrupted(
                f"the keys are renewed but the journal could not be started: {error}", new_keys
            ) from error
    return Renewed(new_keys, fresh, renewed)


@dataclass(frozen=True)
class _Resealed:
    entries: dict[str, bytes]  # what takes the place of the old chains, head, snapshot and original
    replaced: frozenset[str]  # the names of the old ones: all of them are left behind


def _resealed(
    path: Path,
    entries: Mapping[str, bytes],
    manifest,
    old: Mapping[Part, bytes],
    new: Mapping[Part, bytes],
    renewed: frozenset[Part],
    generation: int,
    snapshot: bytes | None,
) -> _Resealed:
    """The chains, the head, the snapshot and the kept original under the new keys. The journal is folded in first."""
    binding = manifest.binding
    chains = _load_chains(entries, manifest, old)
    pending = dict(zip((Part.HISTORY, Part.CHAT), _journal_records(path, manifest, old, chains.head), strict=True))
    made: dict[str, bytes] = {}
    ends = {}
    for part in (Part.HISTORY, Part.CHAT):
        if part in renewed:
            payloads = [p for block in chains.opened[part] for p in block] + pending[part]
            found, end = _sealed_chain(new[part], binding, part, [], payloads)
        else:
            found, end = _extend(old[part], binding, part, chains, pending[part])
        made.update(found)
        ends[part] = end
    if Part.HISTORY in renewed:  # the record of what left is sealed with the history key
        audit = [p for block in chains.opened[blocks.AUDIT] for p in block]
        found, audit_end = _sealed_chain(new[Part.HISTORY], binding, blocks.AUDIT, [], audit)
    else:
        found = {f"{blocks.AUDIT}/{n:06d}.blk": d for n, d in enumerate(chains.stored[blocks.AUDIT], 1)}
        audit_end = chains.head.audit
    made.update(found)
    made[_HEAD] = seal_head(
        new[Part.HISTORY], binding, Head(generation, ends[Part.HISTORY], ends[Part.CHAT], audit_end)
    )
    if snapshot is not None:
        made[_SNAPSHOT] = seal(new[Part.CONTENT], snapshot, _snapshot_aad(binding))
    if Part.CONTENT in renewed and _ORIGINAL in entries:
        try:
            original = open_sealed(old[Part.CONTENT], entries[_ORIGINAL], _original_aad(binding))
        except DecryptionError as error:
            raise TamperedDocument("the kept original does not belong to this document or was changed") from error
        made[_ORIGINAL] = seal(new[Part.CONTENT], original, _original_aad(binding))
    consent = (
        _open_folder_chain(old[Part.CONTENT], binding, blocks.CONSENT, entries) if Part.CONTENT in renewed else None
    )
    if consent is not None:  # the owners' consent is sealed with the content key
        made.update(_consent_entries(new[Part.CONTENT], binding, consent))
    replaced = {
        n
        for n in entries
        if n in (_HEAD, _SNAPSHOT, _ORIGINAL)
        or n.startswith(("history/", "chat/", "audit/"))
        or (consent is not None and n.startswith(f"{blocks.CONSENT}/"))
    }
    if Part.CONTENT not in renewed:  # the original is carried as it is
        replaced.discard(_ORIGINAL)
    return _Resealed(made, frozenset(replaced))


__all__ = ["RenewalInterrupted", "Renewed", "change_role", "remove_person"]
