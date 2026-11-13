"""Performance guards for lists (E9.21): derived numbering must cost nothing while people type.

Scaling tests, not stopwatches (see ``claudia-core/tests/test_performance.py``): the same operation on a document
of a given size with and without list items, or on a small and a large one.
"""

import gc
import time

from claudia_composes import InsertText, SetListItem, TextModel
from claudia_composes.model import Block
from claudia_core import Document, ListBook, ListDef, ListItem, MemoryStore

SMALL, LARGE = 2_000, 20_000


def text_with(paragraphs: int, *, items: bool) -> Document:
    item = ListItem("l1") if items else None
    blocks = [Block(f"b{n}", "body", "x", (), item) for n in range(1, paragraphs + 1)]
    return Document(TextModel(blocks, lists=ListBook([ListDef("l1", "numbers")])), store=MemoryStore())


def best_of(repeat: int, fn) -> float:
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        best = float("inf")
        for _ in range(repeat):
            started = time.perf_counter()
            fn()
            best = min(best, time.perf_counter() - started)
        return best
    finally:
        if was_enabled:
            gc.enable()


def test_typing_costs_the_same_in_a_text_full_of_list_items_as_in_one_without():
    plain, listed = text_with(LARGE, items=False), text_with(LARGE, items=True)
    last = f"b{LARGE}"

    def typing(doc):
        return lambda: [doc.execute(InsertText(last, 0, "a"), author="ann") for _ in range(20)]

    assert best_of(3, typing(listed)) < best_of(3, typing(plain)) * 2.0


def test_numbering_a_paragraph_grows_at_most_with_the_size_of_the_text():
    """Setting an item may renumber everything behind it, so it is linear in the text by design (named in the
    docs); it must not be worse than that."""

    def cost(paragraphs: int) -> float:
        doc = text_with(paragraphs, items=True)
        return best_of(
            3, lambda: [doc.execute(SetListItem("b1", ListItem("l1", n % 2)), author="ann") for n in range(5)]
        )

    assert cost(LARGE) < cost(SMALL) * 10 * 2.5
