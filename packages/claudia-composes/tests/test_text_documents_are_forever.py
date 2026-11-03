"""A document written by the first, stub version of composes still opens (docs/versioning.md)."""

import json
from pathlib import Path

from claudia_composes import TextModel
from claudia_core import CommandLog, Document

FIXTURES = Path(__file__).parent / "fixtures"


def test_a_log_of_schema_1_opens_and_gives_the_same_text():
    log = CommandLog.from_data(json.loads((FIXTURES / "composes_v1.json").read_text()), TextModel.registry)
    doc = Document.open(TextModel, log)
    assert [b.text for b in doc.model.blocks] == ["ello, world"]
    assert doc.manifest().command_schemas["composes.InsertText"] == 2


def test_a_snapshot_of_state_schema_1_is_understood():
    model = TextModel.restore({"blocks": ["first", "second"]})
    assert [(b.id, b.style, b.text) for b in model.blocks] == [("b1", "body", "first"), ("b2", "body", "second")]
    assert sum(r.length for r in model.blocks[1].runs) == len("second")
    assert model.fresh_id() == "b3"
