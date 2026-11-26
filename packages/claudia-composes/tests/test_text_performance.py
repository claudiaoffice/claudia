"""Performance guards for lists (E9.21): derived numbering must cost nothing while people type.

Scaling tests, not stopwatches (see ``claudia-core/tests/test_performance.py``): the same operation on a document
of a given size with and without list items, or on a small and a large one; the work is counted (PERF-14).
"""

from claudia_composes import InsertText, TextModel
from claudia_composes.model import Paragraph
from claudia_core import Document, ListBook, ListDef, ListItem, MemoryStore, SetListItem
from claudia_core.testing import work_of

SMALL, LARGE = 2_000, 20_000


def text_with(count: int, *, items: bool) -> Document:
    item = ListItem("l1") if items else None
    paragraphs = [Paragraph(f"b{n}", "body", "x", (), item) for n in range(1, count + 1)]
    return Document(TextModel(paragraphs, lists=ListBook([ListDef("l1", "numbers")])), store=MemoryStore())


def test_typing_costs_the_same_in_a_text_full_of_list_items_as_in_one_without():
    plain, listed = text_with(LARGE, items=False), text_with(LARGE, items=True)
    last = f"b{LARGE}"

    def typing(doc):
        return lambda: [doc.execute(InsertText(last, 0, "a"), author="ann") for _ in range(20)]

    assert work_of(typing(listed)) < work_of(typing(plain)) * 2.0


def test_numbering_a_paragraph_grows_at_most_with_the_size_of_the_text():
    """Setting an item may renumber everything behind it, so it is linear in the text by design (named in the
    docs); it must not be worse than that."""

    def cost(paragraphs: int) -> int:
        doc = text_with(paragraphs, items=True)
        return work_of(lambda: [doc.execute(SetListItem("b1", ListItem("l1", n % 2)), author="ann") for n in range(5)])

    assert cost(LARGE) < cost(SMALL) * 10 * 2.5
