"""E1.3: schema versions, upcasters, refusal of newer logs, extension commands."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Self

import pytest

from claudia_core import (
    Command,
    CommandLog,
    Document,
    DocumentModel,
    MissingUpcaster,
    SchemaTooNew,
    UnknownCommand,
    new_registry,
)
from claudia_core.commands import Batch, encode
from claudia_core.testing import Insert, ListModel, Remove

FIXTURES = Path(__file__).parent / "fixtures"

tally = new_registry()


class Tally(DocumentModel):
    app: ClassVar[str] = "test-tally"
    registry = tally

    def __init__(self):
        self.total = {}

    @classmethod
    def empty(cls) -> Self:
        return cls()

    def serialize(self):
        return {"total": dict(self.total)}

    @classmethod
    def restore(cls, state):
        m = cls()
        m.total = dict(state["total"])
        return m


@tally.register
@dataclass(frozen=True)
class Add(Command):
    """Schema 1 stored ``{"n": 3}``. Schema 2 stores ``{"amount": 3, "unit": "ones"}``."""

    kind: ClassVar[str] = "tally.Add"
    schema: ClassVar[int] = 2
    amount: int
    unit: str = "ones"

    def apply(self, ctx):
        old = ctx.model.total.get(self.unit, 0)
        ctx.model.total[self.unit] = old + self.amount
        return Add(-self.amount, self.unit)

    def to_data(self):
        return {"amount": self.amount, "unit": self.unit}

    @classmethod
    def from_data(cls, data, registry):
        return cls(data["amount"], data["unit"])


@tally.upcaster("tally.Add", 1)
def _add_1_to_2(data):
    return {"amount": data["n"], "unit": "ones"}


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_old_schema_log_replays_after_a_version_bump():
    log = CommandLog.from_data(load_fixture("tally_v1.json"), tally)
    doc = Document.open(Tally, log)
    assert doc.model.total == {"ones": 8}
    assert doc.manifest().command_schemas == {"tally.Add": 2}  # what the document needs *now*


def test_newer_log_is_refused_with_a_clear_message():
    with pytest.raises(SchemaTooNew) as caught:
        CommandLog.from_data(load_fixture("tally_v3.json"), tally)
    assert "newer version of Claudia" in str(caught.value) and "schema 3" in str(caught.value)


def test_missing_upcaster_is_reported():
    registry = new_registry()

    @registry.register
    @dataclass(frozen=True)
    class Thing(Command):
        kind: ClassVar[str] = "x.Thing"
        schema: ClassVar[int] = 3

        def apply(self, ctx):
            return self

        def to_data(self):
            return {}

        @classmethod
        def from_data(cls, data, registry):
            return cls()

    with pytest.raises(MissingUpcaster):
        registry.decode({"k": "x.Thing", "s": 1, "d": {}})


def test_unknown_kind_points_at_missing_extension():
    with pytest.raises(UnknownCommand) as caught:
        ListModel.registry.decode({"k": "ext.stats.Fit", "s": 1, "d": {}})
    assert "extension" in str(caught.value)


def test_extension_commands_use_the_same_mechanism():
    registry = new_registry()

    @registry.register
    @dataclass(frozen=True)
    class Fit(Command):
        kind: ClassVar[str] = "ext.stats.Fit"

        def apply(self, ctx):
            return self

        def to_data(self):
            return {}

        @classmethod
        def from_data(cls, data, registry):
            return cls()

    assert registry.decode(encode(Fit())) == Fit()


def test_kind_must_be_namespaced_and_unique():
    registry = new_registry()
    with pytest.raises(ValueError):

        @registry.register
        @dataclass(frozen=True)
        class Bad(Command):
            kind: ClassVar[str] = "NoNamespace"

            def apply(self, ctx):
                return self

            def to_data(self):
                return {}

            @classmethod
            def from_data(cls, data, registry):
                return cls()


def test_batch_roundtrip_and_inverse_order():
    batch = Batch((Insert(0, 1), Insert(1, 2)), "two")
    again = ListModel.registry.decode(encode(batch))
    assert again == batch
    assert [type(c) for c in batch.leaves()] == [Insert, Insert]
    assert batch.label == "two"
    inverse = Batch((Remove(1), Remove(0)))
    assert inverse.undoable
