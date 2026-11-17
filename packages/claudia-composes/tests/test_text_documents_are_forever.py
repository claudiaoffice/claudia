"""A document written by the first, stub version of composes still opens (docs/versioning.md).

Its snapshots do; its command logs need not: typing became the kernel's ``core.InsertText`` and ``core.DeleteText``
in step G, and the owner decided on 2026-11-16 that old command histories need not replay (section 7 of
``claudiaoffice-log/notes/text-structure-across-apps.md``)."""

from claudia_composes import TextModel


def test_a_snapshot_of_state_schema_1_is_understood():
    model = TextModel.restore({"blocks": ["first", "second"]})
    assert [(b.id, b.style, b.text) for b in model.blocks] == [("b1", "body", "first"), ("b2", "body", "second")]
    assert sum(r.length for r in model.blocks[1].runs) == len("second")
    assert model.fresh_id() == "b3"


def test_a_snapshot_of_state_schema_5_has_no_lists_and_opens_as_a_text_without_any():
    """Lists came with state schema 6 (E9.21); a text written before has neither a book of lists nor items."""
    state = TextModel().serialize()
    del state["lists"]
    model = TextModel.restore(state)
    assert len(model.lists) == 0 and model.labels() == {}
    assert all(b.item is None and "item" not in b.to_data() for b in model.blocks)
