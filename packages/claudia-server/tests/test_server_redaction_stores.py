"""A redaction leaves no copy of the content in either store (D725, SEC-05): the plain journal and the sealed file."""

import zipfile

from claudia_core import Import, Revision
from claudia_core.testing import Insert, ListModel
from claudia_document_file import (
    KdfParams,
    journal_path,
    read_journal,
    read_manifest,
    read_original,
    read_state,
    unlock,
)
from claudia_server.auth import Credentials
from claudia_server.filestore import FileProvider
from claudia_server.sealed import SealedDocuments

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN_PW = "Correct-Horse-9"
SECRET = 424242


def fill(doc):
    doc.execute(Insert(0, 1), author="ann")
    doc.execute(Insert(1, SECRET), author="ann")  # main:2
    doc.post_chat("ann", f"the code is {SECRET}")


def test_the_plain_journal_is_written_anew(tmp_path):
    provider = FileProvider(tmp_path, ListModel)
    doc = provider.create("plan")
    fill(doc)
    doc.save_checkpoint("ann", "mark")
    doc.execute(Insert(0, 7), author="ann")
    doc.restore_checkpoint(1, "ann")  # a line, so the rewrite has to keep the lines too
    doc.redact(doc.plan_redaction([Revision("main", 2)], chat=[1]), author="ann")
    journal = (tmp_path / "docs" / "plan" / "journal.jsonl").read_bytes()
    assert str(SECRET).encode() not in journal
    doc.execute(Insert(0, 3), author="ann")  # the store goes on writing after the rewrite

    back = FileProvider(tmp_path, ListModel).open("plan")
    assert back.model.items == doc.model.items and back.branch == doc.branch
    assert back.log.get(Revision("main", 2)).redacted and back.chat[0].redacted
    assert back.side_revisions() == doc.side_revisions()


def sealed(tmp_path):
    return SealedDocuments(tmp_path, ListModel, kdf=CHEAP)


def opened(tmp_path):
    store = sealed(tmp_path)
    assert store.verify("plan", Credentials("Annabelle", ANN_PW)) is not None
    return store, store.open("plan")


def everything(tmp_path) -> bytes:
    path = tmp_path / "docs" / "plan.claudia"
    keys = unlock(path, "Annabelle", ANN_PW).keys
    state = read_state(path, keys)
    records = read_journal(journal_path(path), read_manifest(path).binding, keys)
    raw = b"".join(p.read_bytes() for p in path.parent.iterdir() if p.is_file())
    return raw + b"".join([*state.history, *state.chat, state.snapshot or b"", *(r.payload for r in records)])


def test_the_sealed_file_is_sealed_anew(tmp_path):
    store = sealed(tmp_path)
    store.add_user("plan", "Annabelle", ANN_PW, "owner")
    doc = store.create("plan")
    fill(doc)
    store.release("plan")  # into the blocks, with a snapshot
    store, doc = opened(tmp_path)
    doc.execute(Insert(0, 5), author="Annabelle")  # and something in the journal
    assert str(SECRET).encode() in everything(tmp_path)
    doc.redact(doc.plan_redaction([Revision("main", 2)], chat=[1]), author="Annabelle")
    assert str(SECRET).encode() not in everything(tmp_path)
    doc.execute(Insert(0, 6), author="Annabelle")
    expected = doc.model.items
    store.release("plan")

    _, back = opened(tmp_path)
    assert back.model.items == expected and back.log.get(Revision("main", 2)).redacted and back.chat[0].redacted
    assert str(SECRET).encode() not in everything(tmp_path)


def test_a_redacted_import_takes_the_kept_original_with_it(tmp_path):
    store = sealed(tmp_path)
    store.add_user("plan", "Annabelle", ANN_PW, "owner")
    doc = store.create("plan")
    doc.execute(Import("pay.csv", "csv", {"items": [SECRET]}, "ab" * 32, True), author="Annabelle")
    store.keep_original("plan", f"pay,{SECRET}".encode())
    path = tmp_path / "docs" / "plan.claudia"
    keys = unlock(path, "Annabelle", ANN_PW).keys
    assert read_original(path, keys) is not None
    doc.redact(doc.plan_redaction([Revision("main", 1)]), author="Annabelle")
    assert read_original(path, keys) is None
    with zipfile.ZipFile(path) as z:
        assert "content/original.bin" not in z.namelist()
    assert str(SECRET).encode() not in everything(tmp_path)
