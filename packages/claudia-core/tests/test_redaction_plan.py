"""The redaction contract (D229, D720–D726): what a redaction keeps, what it may change, what it takes with it."""

import json
from dataclasses import dataclass
from typing import ClassVar

import pytest

from claudia_core import (
    ChatRecord,
    Command,
    Document,
    Import,
    MemoryStore,
    Redacted,
    RedactedEvent,
    Redaction,
    RedactionError,
    RedactionPlan,
    Revision,
    new_registry,
)
from claudia_core.testing import FakeClock, Insert, ListModel, Remove, Replace

SECRET = 424242


def r(seq: int, branch: str = "main") -> Revision:
    return Revision(branch, seq)


def stored_text(store: MemoryStore) -> str:
    """Everything the store holds, as one text a byte scan can search."""
    entries = {str(rev): entry.to_data() for rev, entry in store.entries.items()}
    return json.dumps([entries, [c.to_data() for c in store.chat], [s.to_data() for s in store.snapshots]])


# --------------------------------------------------------------------------- a model whose redaction breaks later steps
naive = new_registry()


@naive.register
@dataclass(frozen=True)
class NaiveInsert(Command):
    """Keeps the default tombstone: once redacted it inserts nothing, so a later step that removes it fails."""

    kind: ClassVar[str] = "naive.Insert"
    index: int
    value: int

    def apply(self, ctx):
        ctx.model.items.insert(self.index, self.value)
        return NaiveRemove(self.index)

    def to_data(self):
        return {"index": self.index, "value": self.value}

    @classmethod
    def from_data(cls, data, registry):
        return cls(data["index"], data["value"])


@naive.register
@dataclass(frozen=True)
class NaiveRemove(Command):
    """Fails on an empty place; its own tombstone does nothing, so blanking it too lets the rest replay."""

    kind: ClassVar[str] = "naive.Remove"
    index: int

    def apply(self, ctx):
        items = ctx.model.items
        if not 0 <= self.index < len(items):
            raise IndexError(f"nothing at {self.index}")
        return NaiveInsert(self.index, items.pop(self.index))

    def to_data(self):
        return {"index": self.index}

    @classmethod
    def from_data(cls, data, registry):
        return cls(data["index"])


class NaiveModel(ListModel):
    app: ClassVar[str] = "test-naive"
    registry = naive


@pytest.fixture
def naive_doc():
    clock = FakeClock()
    return Document(NaiveModel(), clock=clock.time, lock_clock=clock.lock_time, store=MemoryStore())


def secret_doc(make_doc):
    doc = make_doc()
    doc.execute(Insert(0, 1), author="ana")
    doc.execute(Insert(1, SECRET), author="ben")  # main:2
    doc.execute(Replace(0, 5), author="ana")
    doc.save_checkpoint("ana", "before")
    doc.execute(Insert(2, 9), author="ana")
    return doc


# --------------------------------------------------------------------------- the plan (D721)
def test_a_plan_says_what_goes_and_what_the_document_looks_like_after(make_doc):
    doc = secret_doc(make_doc)
    plan = doc.plan_redaction([r(2)])
    assert isinstance(plan, RedactionPlan)
    assert plan.targets == (r(2),) and plan.dependents == () and plan.revisions == (r(2),)
    assert plan.changes_now and plan.after.items == [5, 0, 9]
    assert doc.model.items == [5, SECRET, 9] and not doc.log.get(r(2)).redacted  # planning changes nothing


def test_content_already_gone_from_the_document_is_removed_without_changing_what_anyone_sees(make_doc):
    doc = make_doc()
    doc.execute(Insert(0, SECRET), author="ana")
    doc.execute(Remove(0), author="ana")
    doc.execute(Insert(0, 7), author="ana")
    plan = doc.plan_redaction([r(1)])
    assert not plan.changes_now
    doc.redact(plan, author="ana")
    assert doc.model.items == [7]


def test_the_same_shape_stays_so_later_steps_still_apply(make_doc):
    """D720: a redacted step keeps lengths, places and ids; only the content goes."""
    doc = secret_doc(make_doc)
    doc.redact(doc.plan_redaction([r(2)]), author="ana")
    entry = doc.log.get(r(2))
    assert entry.redacted and entry.command == Insert(1, 0)
    assert doc.model.items == [5, 0, 9]


# --------------------------------------------------------------------------- later steps that need the content (D722)
def test_later_steps_that_would_break_are_named_and_blanked_with_it(naive_doc):
    doc = naive_doc
    doc.execute(NaiveInsert(0, SECRET), author="ana")
    doc.execute(NaiveRemove(0), author="ben")  # needs what main:1 put there
    doc.execute(NaiveInsert(0, 7), author="ana")
    plan = doc.plan_redaction([r(1)])
    assert plan.targets == (r(1),) and plan.dependents == (r(2),)
    assert plan.after.items == [7] and not plan.changes_now
    doc.redact(plan, author="ana")
    assert doc.log.get(r(1)).redacted and doc.log.get(r(2)).redacted
    assert doc.log.get(r(4)).command == Redaction((r(1), r(2)))
    assert str(SECRET) not in json.dumps(doc.log.to_data())


def test_a_bare_list_of_steps_is_refused_when_others_would_have_to_go_too(naive_doc):
    """Nobody's work is blanked without being shown first: the plan has to be asked for and looked at."""
    doc = naive_doc
    doc.execute(NaiveInsert(0, SECRET), author="ana")
    doc.execute(NaiveRemove(0), author="ben")
    with pytest.raises(RedactionError) as caught:
        doc.redact([r(1)], author="ana")
    assert "main:2" in str(caught.value)
    assert not doc.log.get(r(1)).redacted


def test_a_later_step_that_breaks_even_blanked_becomes_a_tombstone(make_doc):
    """D722 (2026-11-18): a later step whose same-shape blank still does not apply (``Remove`` keeps its index, but the
    item it removed was never inserted) becomes a no-op tombstone instead of stopping the redaction."""
    registry = new_registry()
    registry.register(Remove)
    registry.register(NaiveInsert)

    class Stubborn(ListModel):
        app: ClassVar[str] = "test-stubborn"

    Stubborn.registry = registry
    clock = FakeClock()
    doc = Document(Stubborn(), clock=clock.time, store=MemoryStore())
    doc.execute(NaiveInsert(0, SECRET), author="ana")
    doc.execute(Remove(0), author="ana")
    plan = doc.plan_redaction([r(1)])
    assert plan.dependents == (r(2),)
    doc.redact(plan, author="ana")
    assert doc.log.get(r(2)).command == Redacted("list.Remove", {})
    assert doc.model.items == []


def test_a_history_that_does_not_replay_before_the_redaction_is_not_blanked_further(make_doc):
    """The last resort: a step before every blanked one refuses, so the history was broken already. Nothing is
    blanked to hide that."""
    doc = secret_doc(make_doc)
    doc.log.replace_command(r(1), Remove(5))  # a history broken from the start
    with pytest.raises(RedactionError) as caught:
        doc.plan_redaction([r(2)])
    assert "does not replay" in str(caught.value)


def test_a_plan_is_only_good_for_the_document_it_was_made_for(make_doc):
    doc = secret_doc(make_doc)
    plan = doc.plan_redaction([r(2)])
    doc.execute(Insert(0, 3), author="ben")
    with pytest.raises(RedactionError) as caught:
        doc.redact(plan, author="ana")
    assert "changed" in str(caught.value)
    assert not doc.log.get(r(2)).redacted


def test_nothing_to_redact_and_what_cannot_be_redacted(make_doc):
    doc = secret_doc(make_doc)
    with pytest.raises(RedactionError):
        doc.plan_redaction([])
    with pytest.raises(RedactionError):
        doc.plan_redaction(chat=[1])  # there is no chat message 1
    with pytest.raises(RedactionError):
        doc.plan_redaction(parts={r(2): ["0"]})  # parts only for a step that is redacted


# --------------------------------------------------------------------------- hidden lines (D724)
def test_a_step_on_a_hidden_line_can_be_redacted(make_doc):
    doc = make_doc()
    doc.execute(Insert(0, 1), author="ana")  # main:1
    doc.save_checkpoint("ana", "clean")  # main:2
    doc.execute(Insert(1, SECRET), author="ben")  # main:3
    doc.restore_checkpoint(1, "ana")  # the document goes on on restore-1; main:3 is hidden
    assert r(3) in doc.side_revisions()
    plan = doc.plan_redaction([r(3)])
    assert not plan.changes_now
    doc.redact(plan, author="ana")
    assert doc.log.get(r(3)).redacted
    assert doc.peek_branch("main").items == [1, 0]
    assert str(SECRET) not in stored_text(doc.store)


def test_every_line_that_shares_a_step_must_still_replay(naive_doc):
    doc = naive_doc
    doc.execute(NaiveInsert(0, SECRET), author="ana")  # main:1, on both lines
    doc.save_checkpoint("ana", "one")  # main:2
    doc.execute(NaiveRemove(0), author="ben")  # main:3, hidden after the restore
    doc.restore_checkpoint(1, "ana")
    plan = doc.plan_redaction([r(1)])
    assert plan.dependents == (r(3),)
    assert plan.changes_now and plan.after.items == []


# --------------------------------------------------------------------------- chat (D724)
def test_a_chat_message_can_be_redacted(make_doc):
    doc = secret_doc(make_doc)
    doc.post_chat("ben", "@ana the password is hunter2", users=["ana", "ben"])
    doc.post_chat("ana", "thanks", users=["ana", "ben"])
    events = []
    doc.subscribe(lambda e: events.append(e) if isinstance(e, RedactedEvent) else None)
    plan = doc.plan_redaction(chat=[1])
    assert plan.chat == (1,) and plan.revisions == () and not plan.changes_now
    applied = doc.redact(plan, author="ana")
    first = doc.chat[0]
    assert first.redacted and first.text == "" and (first.number, first.author, first.to) == (1, "ben", "ana")
    assert doc.chat[1].text == "thanks"
    assert applied.command == Redaction((), (1,))
    assert events[-1].to_data() == {"type": "redacted", "revisions": [], "chat": [1]}
    assert "hunter2" not in stored_text(doc.store)


def test_a_redacted_chat_record_keeps_its_place_and_says_so():
    record = ChatRecord(3, "ben", "", "secret words", "2026-11-16T10:00:00.000Z", r(2))
    blank = record.blanked()
    assert blank.to_data() == {**record.to_data(), "text": "", "redacted": True}
    assert ChatRecord.from_data(blank.to_data()) == blank
    assert "redacted" not in record.to_data()


def test_the_redaction_record_reads_the_old_form_and_writes_chat_only_when_there_is_some():
    assert Redaction((r(2),)).to_data() == {"targets": ["main:2"]}
    assert Redaction((), (4,)).to_data() == {"targets": [], "chat": [4]}
    assert Redaction.from_data({"targets": ["main:2"]}, new_registry()) == Redaction((r(2),))
    assert Redaction((r(2),), (1, 4)).label == "Redacted 1 change and 2 messages"


# --------------------------------------------------------------------------- the store forgets the old content (D725)
def test_the_store_is_rewritten_so_no_copy_of_the_content_is_left(make_doc):
    doc = secret_doc(make_doc)
    doc.cache_snapshot()
    doc.post_chat("ben", f"it is {SECRET}")
    doc.redact(doc.plan_redaction([r(2)], chat=[1]), author="ana")
    assert "rewrite" in doc.store.calls
    assert str(SECRET) not in stored_text(doc.store)
    assert doc.store.entries[r(2)].redacted
    reopened = Document.open(ListModel, doc.log)
    assert reopened.model.serialize() == doc.model.serialize()


def test_a_store_that_cannot_rewrite_leaves_the_document_as_it_was(make_doc):
    class Failing(MemoryStore):
        def rewrite(self, log, chat):
            raise OSError("disk full")

    doc = secret_doc(lambda: make_doc(store=Failing()))
    doc.post_chat("ben", "hunter2")
    with pytest.raises(OSError):
        doc.redact(doc.plan_redaction([r(2)], chat=[1]), author="ana")
    assert not doc.log.get(r(2)).redacted and doc.chat[0].text == "hunter2"
    assert doc.model.items == [5, SECRET, 9]


# --------------------------------------------------------------------------- an import (D723)
def imported_doc(make_doc, kept=True):
    doc = make_doc()
    doc.execute(Import("salaries.xlsx", "xlsx", {"items": [1, SECRET, 3]}, "ab" * 32, kept), author="ana")
    doc.execute(Insert(3, 4), author="ana")
    return doc


def test_an_import_is_blanked_in_full(make_doc):
    doc = imported_doc(make_doc)
    plan = doc.plan_redaction([r(1)])
    assert plan.after.items == [0, 0, 0, 4] and plan.imports == (r(1),)
    doc.redact(plan, author="ana")
    command = doc.log.get(r(1)).command
    assert command == Import("", "xlsx", {"items": [0, 0, 0]}, None, False)
    assert doc.model.items == [0, 0, 0, 4]


def test_an_import_is_blanked_in_parts(make_doc):
    doc = imported_doc(make_doc)
    plan = doc.plan_redaction([r(1)], parts={r(1): ["1"]})
    assert plan.after.items == [1, 0, 3, 4]
    doc.redact(plan, author="ana")
    command = doc.log.get(r(1)).command
    assert command == Import("salaries.xlsx", "xlsx", {"items": [1, 0, 3]}, None, False)


def test_parts_are_only_for_an_import(make_doc):
    doc = secret_doc(make_doc)
    with pytest.raises(RedactionError) as caught:
        doc.plan_redaction([r(2)], parts={r(2): ["0"]})
    assert "import" in str(caught.value)


def test_an_app_that_cannot_blank_says_so(naive_doc):
    class Plain(NaiveModel):
        app: ClassVar[str] = "test-plain"

        def blank(self, parts):
            return super(ListModel, self).blank(parts)  # the kernel's default

    clock = FakeClock()
    doc = Document(Plain(), clock=clock.time)
    doc.execute(Import("a.csv", "csv", {"items": [SECRET]}), author="ana")
    with pytest.raises(RedactionError) as caught:
        doc.plan_redaction([r(1)])
    assert "test-plain" in str(caught.value)
