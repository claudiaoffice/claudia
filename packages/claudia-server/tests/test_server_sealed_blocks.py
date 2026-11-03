"""The sealed store packs its journal into blocks, keeps a snapshot, and brings documents up from both (E2.1, E2.5)."""

import zipfile

import pytest

from claudia_container import KdfParams, journal_path, read_snapshot, read_state, unlock
from claudia_core.testing import Insert, ListModel
from claudia_server.auth import Credentials
from claudia_server.sealed import SealedDocuments

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN_PW = "Correct-Horse-9"


def store_in(tmp_path, **options):
    return SealedDocuments(tmp_path, ListModel, kdf=CHEAP, **options)


def start(store, doc_id="plan"):
    store.add_user(doc_id, "Annabelle", ANN_PW, "owner")
    return store.create(doc_id)


def type_values(doc, values):
    for value in values:
        doc.execute(Insert(0, value), author="Annabelle")


def reopen(tmp_path, **options):
    store = store_in(tmp_path, **options)
    assert store.verify("plan", Credentials("Annabelle", ANN_PW)) is not None
    return store, store.open("plan")


def archive(tmp_path):
    return tmp_path / "docs" / "plan.claudia"


def names(tmp_path):
    with zipfile.ZipFile(archive(tmp_path)) as z:
        return set(z.namelist())


def keys_of(tmp_path):
    return unlock(archive(tmp_path), "Annabelle", ANN_PW).keys


# --- letting go of a document packs it ------------------------------------------------------------------------------


def test_releasing_a_document_folds_its_journal_into_blocks_and_leaves_a_snapshot(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [5, 6, 7])
    doc.post_chat("Annabelle", "hello")
    store.release("plan")
    assert {"head.bin", "history/000001.blk", "chat/000001.blk", "content/snapshot.bin"} <= names(tmp_path)
    state = read_state(archive(tmp_path), keys_of(tmp_path))
    assert state.pending == 0 and len(state.history) == 3 and len(state.chat) == 1
    assert read_snapshot(archive(tmp_path), keys_of(tmp_path)) is not None


def test_a_document_comes_back_from_blocks_with_its_snapshot(tmp_path, monkeypatch):
    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [5, 6, 7])
    doc.save_checkpoint("Annabelle", "mark")
    doc.post_chat("Annabelle", "hello")
    expected, revision = doc.model.items, doc.revision
    store.release("plan")

    restored = []
    original = ListModel.restore.__func__
    monkeypatch.setattr(
        ListModel, "restore", classmethod(lambda cls, state: restored.append(state) or original(cls, state))
    )
    _, back = reopen(tmp_path)
    assert restored, "the snapshot was not used"
    assert (back.model.items, back.revision) == (expected, revision)
    assert [c.label for c in back.checkpoints] == ["mark"]
    assert [r.text for r in back.chat] == ["hello"]
    # Undo steps are not part of a snapshot: they start again when a document is opened from one (documented).
    assert not back.history_for("Annabelle").can_undo
    back.execute(Insert(0, 8), author="Annabelle")
    back.undo("Annabelle")
    assert back.model.items == expected


def test_work_after_the_snapshot_is_replayed_on_top_of_it(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [5, 6])
    store.release("plan")
    again, doc = reopen(tmp_path)
    type_values(doc, [7])  # after the snapshot
    expected = doc.model.items
    again.release("plan")
    assert reopen(tmp_path)[1].model.items == expected == [7, 6, 5]


def test_a_snapshot_that_is_of_another_time_is_ignored_and_the_history_wins(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [5, 6])
    store.release("plan")
    again, doc = reopen(tmp_path)
    type_values(doc, [7, 8])
    expected = doc.model.items
    # the process dies: no release, so the file still holds the old snapshot and the journal holds the newer work
    assert reopen(tmp_path)[1].model.items == expected


def test_a_snapshot_that_cannot_be_read_is_not_a_problem(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [5, 6])
    expected = doc.model.items
    store.release("plan")
    with zipfile.ZipFile(archive(tmp_path)) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    entries["content/snapshot.bin"] = b"rubbish" * 10
    with zipfile.ZipFile(archive(tmp_path), "w") as z:
        z.writestr("format", entries.pop("format"), compress_type=zipfile.ZIP_STORED)
        for name, data in entries.items():
            z.writestr(name, data)
    assert reopen(tmp_path)[1].model.items == expected


def test_releasing_a_document_nobody_changed_writes_nothing(tmp_path):
    store = store_in(tmp_path)
    start(store)
    store.release("plan")
    before = archive(tmp_path).read_bytes()
    again, _ = reopen(tmp_path)
    again.release("plan")
    assert archive(tmp_path).read_bytes() == before


def test_a_failing_pack_still_forgets_the_keys_and_loses_nothing(tmp_path, monkeypatch, caplog):
    from claudia_server import sealed

    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [5, 6])

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(sealed, "pack_journal", fail)
    store.release("plan")  # does not raise
    monkeypatch.undo()
    assert "disk full" in caplog.text
    with pytest.raises(ValueError, match="sealed"):
        store.open("plan")
    assert reopen(tmp_path)[1].model.items == [6, 5]  # the journal had it


# --- packing while the document is open -----------------------------------------------------------------------------


def test_a_long_session_is_packed_every_so_often_and_loses_nothing(tmp_path):
    store = store_in(tmp_path, pack_every=5)
    doc = start(store)
    type_values(doc, range(23))
    expected = doc.model.items
    assert "history/000001.blk" in names(tmp_path)
    state = read_state(archive(tmp_path), keys_of(tmp_path))
    assert 0 <= state.pending < 5 and len(state.history) == 23
    assert reopen(tmp_path)[1].model.items == expected


def test_after_a_packing_the_journal_carries_on_with_the_next_generation(tmp_path):
    from claudia_container import journal_generation

    store = store_in(tmp_path, pack_every=3)
    doc = start(store)
    type_values(doc, range(7))
    assert journal_generation(journal_path(archive(tmp_path))) == 2


def test_opening_a_document_with_unpacked_work_packs_it(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [5, 6, 7])
    expected = doc.model.items  # (the process dies: nothing is released)
    store = store_in(tmp_path)
    assert store.verify("plan", Credentials("Annabelle", ANN_PW)) is not None
    back = store.open("plan")
    assert back.model.items == expected
    state = read_state(archive(tmp_path), keys_of(tmp_path))
    assert state.pending == 0 and len(state.history) == 3
    assert read_snapshot(archive(tmp_path), keys_of(tmp_path)) is not None


def test_the_folder_still_shows_nothing_readable_after_packing(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [123456789])
    doc.save_checkpoint("Annabelle", "the-quarterly-numbers-4711")
    doc.post_chat("Annabelle", "the-forecast-is-confidential-4711")
    store.release("plan")
    data = b""
    for file in tmp_path.rglob("*"):
        if file.is_file():
            data += file.read_bytes()
    with zipfile.ZipFile(archive(tmp_path)) as z:
        data += b"".join(z.read(n) for n in z.namelist())
    for secret in (b"123456789", b"quarterly", b"confidential", b"Annabelle", b"list.Insert", ANN_PW.encode()):
        assert secret not in data


# --- damage ---------------------------------------------------------------------------------------------------------


def test_a_removed_block_is_refused_when_the_document_is_opened(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    type_values(doc, [5, 6])
    store.release("plan")
    with zipfile.ZipFile(archive(tmp_path)) as z:
        kept = {n: z.read(n) for n in z.namelist() if not n.startswith("history/")}
    with zipfile.ZipFile(archive(tmp_path), "w") as z:
        z.writestr("format", kept.pop("format"), compress_type=zipfile.ZIP_STORED)
        for name, data in kept.items():
            z.writestr(name, data)
    again = store_in(tmp_path)
    assert again.verify("plan", Credentials("Annabelle", ANN_PW)) is not None
    with pytest.raises(ValueError, match="damaged|changed"):
        again.open("plan")


def test_a_server_that_is_stopped_packs_the_documents_it_had_open(tmp_path):
    from starlette.testclient import TestClient
    from test_server_app import INSERT, Peer

    from claudia_server.app import create_app
    from claudia_server.hub import Hub

    store = store_in(tmp_path)
    with TestClient(create_app(Hub(store), store)) as client:
        ann = Peer(client, user="Annabelle", password=ANN_PW, create=True)
        assert ann.request("apply", {"command": INSERT})["ok"]
        ann.close()
    assert "head.bin" in names(tmp_path)
    assert read_state(archive(tmp_path), keys_of(tmp_path)).pending == 0
