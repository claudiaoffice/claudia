"""Blocks and the head record (E2.1, E2.5): sealed, chained, bound to their document and place."""

import pytest

from claudia_container.blocks import (
    GENESIS,
    BlockError,
    Chain,
    Head,
    Place,
    block_hash,
    open_block,
    open_head,
    seal_block,
    seal_head,
)
from claudia_container.crypto import random_key, seal
from claudia_container.slots import Domain

KEY = random_key()
PAYLOADS = [b'{"t":"entry","d":{"rev":"main:1"}}', b'{"t":"entry","d":{"rev":"main:2"}}', b""]


def sealed(payloads=PAYLOADS, *, doc="plan", domain=Domain.HISTORY, number=1, previous=GENESIS, key=KEY):
    return seal_block(key, Place(doc, domain, number, previous), payloads)


def opened(data, *, doc="plan", domain=Domain.HISTORY, number=1, previous=GENESIS, key=KEY):
    return open_block(key, Place(doc, domain, number, previous), data)


def test_a_block_gives_back_what_went_in_in_the_same_order():
    assert opened(sealed()) == PAYLOADS


def test_an_empty_block_and_a_block_of_empty_payloads_are_fine():
    assert opened(sealed([])) == []
    assert opened(sealed([b"", b""])) == [b"", b""]


def test_a_block_hides_its_content_and_packs_repetitive_text_small():
    lines = [b'{"t":"entry","d":{"cmd":"cells.Set","value":"the-quarterly-forecast-4711"}}'] * 200
    data = sealed(lines)
    assert b"quarterly" not in data and b"cells.Set" not in data
    assert len(data) < len(b"".join(lines)) / 5


def test_the_hash_of_a_block_is_32_bytes_and_depends_on_every_byte():
    data = sealed()
    assert len(block_hash(data)) == 32 == len(GENESIS)
    assert block_hash(data) != block_hash(data[:-1] + bytes([data[-1] ^ 1]))


@pytest.mark.parametrize(
    "wrong",
    [
        {"key": random_key()},
        {"doc": "other"},
        {"domain": Domain.CHAT},
        {"number": 2},
        {"previous": bytes([1]) * 32},
    ],
    ids=["key", "document", "domain", "number", "previous block"],
)
def test_a_block_opens_only_in_its_own_place(wrong):
    with pytest.raises(BlockError):
        opened(sealed(), **wrong)


def test_a_changed_block_is_refused():
    data = bytearray(sealed())
    data[len(data) // 2] ^= 1
    with pytest.raises(BlockError):
        opened(bytes(data))


def test_a_cut_off_block_is_refused():
    with pytest.raises(BlockError):
        opened(sealed()[:20])
    with pytest.raises(BlockError):
        opened(b"")


def test_a_block_cannot_claim_to_be_enormous():
    import zlib

    from claudia_container.blocks import _aad

    bomb = zlib.compress(b"\0" * (80 * 1024 * 1024))  # authentic (sealed with the right key and place), but huge
    data = seal(KEY, bomb, _aad(Place("plan", Domain.HISTORY, 1, GENESIS)))
    with pytest.raises(BlockError, match="large"):
        opened(data)


def test_the_limit_on_a_block_is_checked_after_it_was_authenticated(monkeypatch):
    from claudia_container import blocks

    monkeypatch.setattr(blocks, "MAX_BLOCK_BYTES", 100)
    data = sealed([b"x" * 500])
    with pytest.raises(BlockError, match="large"):
        opened(data)


# --- the head ------------------------------------------------------------------------------------------------------


def head(**changes):
    values = {"generation": 3, "history": Chain(2, bytes([7]) * 32), "chat": Chain(0, GENESIS)}
    return Head(**{**values, **changes})


def test_the_head_gives_back_the_counts_hashes_and_generation():
    assert open_head(KEY, "plan", seal_head(KEY, "plan", head())) == head()


def test_a_head_without_blocks_starts_before_generation_zero():
    empty = Head.empty()
    assert (empty.generation, empty.history, empty.chat) == (-1, Chain(0, GENESIS), Chain(0, GENESIS))


@pytest.mark.parametrize("wrong", [{"key": random_key()}, {"doc": "other"}])
def test_a_head_opens_only_for_its_document_and_key(wrong):
    data = seal_head(KEY, "plan", head())
    with pytest.raises(BlockError):
        open_head(wrong.get("key", KEY), wrong.get("doc", "plan"), data)


def test_a_head_that_is_not_a_head_is_refused():
    from claudia_container.blocks import _head_aad

    negative = b'{"generation":1,"history":{"blocks":-1,"last":"AA=="}}'
    rubbish_heads = (b"not json", b'{"generation": "x"}', b"[]", negative)
    for rubbish in rubbish_heads:
        with pytest.raises(BlockError):
            open_head(KEY, "plan", seal(KEY, rubbish, _head_aad("plan")))
