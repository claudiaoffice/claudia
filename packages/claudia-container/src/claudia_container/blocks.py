"""Blocks and the head record (E2.1, E2.5): how the history and the chat rest in the document file.

A **block** holds a run of journal payloads: they are framed, compressed and sealed (AES-256-GCM) with the key of their
domain. The authenticated data names the document, the domain, the number of the block and the hash of the block
before it, so a block opens in exactly one place: it cannot be changed, moved, swapped with another, taken from another
document or put after a different predecessor. Blocks of a domain form a chain: the hash of a block is the SHA-256 of
its stored bytes, and the next block was sealed knowing it.

The **head** says how many blocks each domain has, the hash of the last one, and the number of the last journal
generation that is folded into the blocks. It is sealed with the history key. Somebody who holds the file but no key can
still remove the newest blocks, but then the head no longer fits and the file is refused. Not covered: putting back an
older copy of the whole file (the head of an old copy fits its old blocks).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import struct
import zlib
from collections.abc import Sequence
from dataclasses import dataclass

from .crypto import DecryptionError, open_sealed, seal
from .slots import Domain

BLOCK_TARGET_BYTES = 1024 * 1024
"""A block is closed once its payloads together are this large (before compression); small ones are filled up."""

MAX_BLOCK_BYTES = 64 * 1024 * 1024
"""What a block may hold at most once opened. A file cannot make the reader allocate more than this."""

GENESIS = bytes(32)
"""The hash that "the block before the first block" has."""

_DOMAIN_BYTE = {Domain.CONTENT: 1, Domain.HISTORY: 2, Domain.CHAT: 3}


class BlockError(Exception):
    """A block or the head cannot be opened here: wrong key, wrong place, changed, or not a block at all."""


def block_hash(stored: bytes) -> bytes:
    """The hash that links the next block to this one."""
    return hashlib.sha256(stored).digest()


@dataclass(frozen=True)
class Place:
    """Where a block belongs: its document, its domain, its number (from 1) and the hash of the block before it."""

    doc_id: str
    domain: Domain
    number: int
    previous: bytes


def _aad(place: Place) -> bytes:
    name = place.doc_id.encode()
    number = struct.pack(">I", place.number)
    domain = bytes([_DOMAIN_BYTE[place.domain]])
    return b"claudia/block/1" + struct.pack(">H", len(name)) + name + domain + number + place.previous


def seal_block(key: bytes, place: Place, payloads: Sequence[bytes]) -> bytes:
    """The stored form of the block at ``place`` holding ``payloads``."""
    framed = struct.pack(">I", len(payloads)) + b"".join(struct.pack(">I", len(p)) + p for p in payloads)
    return seal(key, zlib.compress(framed, 6), _aad(place))


def open_block(key: bytes, place: Place, stored: bytes) -> list[bytes]:
    """The payloads of a block. :class:`BlockError` if it does not belong exactly at ``place`` or was changed."""
    try:
        compressed = open_sealed(key, stored, _aad(place))
    except DecryptionError as error:
        raise BlockError("the block cannot be opened: wrong key or place, or it was changed") from error
    inflater = zlib.decompressobj()
    try:
        framed = inflater.decompress(compressed, MAX_BLOCK_BYTES + 1)
    except zlib.error as error:
        raise BlockError("the block is damaged") from error
    if len(framed) > MAX_BLOCK_BYTES or inflater.unconsumed_tail:
        raise BlockError("the block is too large")
    return _unframe(framed)


def _unframe(framed: bytes) -> list[bytes]:
    try:
        (count,) = struct.unpack_from(">I", framed, 0)
        payloads, position = [], 4
        for _ in range(count):
            (size,) = struct.unpack_from(">I", framed, position)
            position += 4
            if position + size > len(framed):
                raise BlockError("the block is damaged")
            payloads.append(framed[position : position + size])
            position += size
    except struct.error as error:
        raise BlockError("the block is damaged") from error
    if position != len(framed):
        raise BlockError("the block is damaged")
    return payloads


@dataclass(frozen=True)
class Chain:
    """How far a domain's chain of blocks goes: the number of blocks and the hash of the last one."""

    blocks: int
    last: bytes


@dataclass(frozen=True)
class Head:
    """What the file promises about its blocks (see the module text)."""

    generation: int
    """The last journal generation whose records are in the blocks (-1 for none yet)."""
    history: Chain
    chat: Chain

    @classmethod
    def empty(cls) -> Head:
        """The head of a document without blocks."""
        return cls(-1, Chain(0, GENESIS), Chain(0, GENESIS))

    def chain(self, domain: Domain) -> Chain:
        """The chain of ``domain`` (history or chat)."""
        return self.history if domain is Domain.HISTORY else self.chat


def _head_aad(doc_id: str) -> bytes:
    return b"claudia/head/1" + doc_id.encode()


def seal_head(key: bytes, doc_id: str, head: Head) -> bytes:
    """The stored form of the head; ``key`` is the history key."""
    data = {
        "generation": head.generation,
        "history": {"blocks": head.history.blocks, "last": base64.b64encode(head.history.last).decode()},
        "chat": {"blocks": head.chat.blocks, "last": base64.b64encode(head.chat.last).decode()},
    }
    return seal(key, json.dumps(data).encode(), _head_aad(doc_id))


def _chain_of(data: object) -> Chain:
    blocks, last = data["blocks"], base64.b64decode(data["last"], validate=True)  # type: ignore[index]
    if not isinstance(blocks, int) or isinstance(blocks, bool) or blocks < 0 or len(last) != len(GENESIS):
        raise ValueError("not a chain")
    return Chain(blocks, last)


def open_head(key: bytes, doc_id: str, stored: bytes) -> Head:
    """The head. :class:`BlockError` if it is not this document's head under this key."""
    try:
        data = json.loads(open_sealed(key, stored, _head_aad(doc_id)))
        generation = data["generation"]
        if not isinstance(generation, int) or isinstance(generation, bool) or generation < -1:
            raise ValueError("not a generation")
        return Head(generation, _chain_of(data["history"]), _chain_of(data["chat"]))
    except (DecryptionError, ValueError, KeyError, TypeError, binascii.Error) as error:
        raise BlockError("the head cannot be opened: wrong key or document, or it was changed") from error
