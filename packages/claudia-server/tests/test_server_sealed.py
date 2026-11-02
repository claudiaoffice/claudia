"""The sealed store (E2.1 to E2.3, E2.7): documents and their people in the encrypted container, behind the server's two
interfaces (``DocumentProvider`` and ``UserDirectory``)."""

import statistics
import sys
import time

import pytest

from claudia_container import JournalWriter, KdfParams, journal_path
from claudia_core import Document
from claudia_core.testing import Insert, ListModel
from claudia_server.auth import AuthRefused, Credentials
from claudia_server.sealed import SealedDocuments

CHEAP = KdfParams(iterations=1, memory_kib=64, lanes=1)
ANN_PW, BEN_PW, VERA_PW = "Correct-Horse-9", "Battery-Staple-7", "Purple-Monkey-5"
POSITIONS = [0, 0, 1]


def store_in(tmp_path, **options):
    return SealedDocuments(tmp_path, ListModel, kdf=CHEAP, **options)


def start(store, doc_id="plan"):
    """What the gateway does for a new document: its owner first, then the document."""
    store.add_user(doc_id, "Annabelle", ANN_PW, "owner")
    return store.create(doc_id)


def fill(doc, author="Annabelle"):
    for i, value in enumerate((5, 6, 7)):
        doc.execute(Insert(POSITIONS[i], value), author=author)


def sign_in(store, name, password, doc_id="plan"):
    return store.verify(doc_id, Credentials(name, password))


def reopen(tmp_path, name="Annabelle", password=ANN_PW, **options):
    """A restarted server: a new store on the same folder, a login, then the document."""
    store = store_in(tmp_path, **options)
    assert sign_in(store, name, password) is not None
    return store, store.open("plan")


# --- documents survive a restart, and only as sealed files ---------------------------------------------------------


def test_a_document_comes_back_after_a_restart(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    fill(doc)
    doc.save_checkpoint("Annabelle", "first")
    doc.post_chat("Annabelle", "hello everybody")
    revision = doc.revision

    again, back = reopen(tmp_path)
    assert isinstance(back, Document)
    assert back.revision == revision
    assert back.model.items == doc.model.items
    assert [c.label for c in back.checkpoints] == ["first"]
    assert [r.text for r in back.chat] == ["hello everybody"]
    assert back.history_for("Annabelle").can_undo
    assert again.exists("plan") and not again.exists("other")


def test_a_restored_line_and_its_hidden_future_survive_a_restart(tmp_path):
    doc = start(store_in(tmp_path))
    fill(doc)
    doc.save_checkpoint("Annabelle", "mark")
    doc.execute(Insert(0, 99), author="Annabelle")
    doc.restore_checkpoint(1, "Annabelle")
    _, back = reopen(tmp_path)
    assert back.branch == doc.branch != "main"
    assert back.model.items == doc.model.items
    assert back.log.to_data() == doc.log.to_data()


def test_nothing_readable_is_left_on_disk(tmp_path):
    store = store_in(tmp_path)
    doc = start(store)
    store.add_user("plan", "Bertram", BEN_PW, "editor")
    store.add_user("plan", "Cornelia", VERA_PW, "viewer")
    fill(doc)
    doc.save_checkpoint("Annabelle", "the-quarterly-numbers-4711")
    doc.post_chat("Annabelle", "the-forecast-is-confidential-4711")
    on_disk = b""
    for file in tmp_path.rglob("*"):
        if file.is_file():
            on_disk += file.read_bytes()
    import zipfile

    for file in tmp_path.rglob("*.claudia"):
        with zipfile.ZipFile(file) as z:
            on_disk += b"".join(z.read(n) for n in z.namelist())
    assert on_disk
    secrets = ["Annabelle", "Bertram", "Cornelia", ANN_PW, BEN_PW, VERA_PW, "quarterly-numbers", "confidential"]
    for secret in [*secrets, "list.Insert"]:
        assert secret.encode() not in on_disk, secret


def test_a_document_is_a_sealed_file_and_its_journal(tmp_path):
    start(store_in(tmp_path))
    assert sorted(p.name for p in (tmp_path / "docs").iterdir()) == ["plan.claudia", "plan.claudia.journal"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_the_files_are_private(tmp_path):
    start(store_in(tmp_path))
    for file in (tmp_path / "docs").iterdir():
        assert file.stat().st_mode & 0o077 == 0


# --- logging in --------------------------------------------------------------------------------------------------


def test_the_account_carries_the_stored_name_and_the_role(tmp_path):
    store = store_in(tmp_path)
    start(store)
    store.add_user("plan", "Bertram", BEN_PW, "editor")
    account = sign_in(store, "  ANNABELLE ", ANN_PW)
    assert (account.user, account.role) == ("Annabelle", "owner")
    assert sign_in(store, "bertram", BEN_PW).role == "editor"


@pytest.mark.parametrize(
    ("doc", "name", "password"),
    [
        ("plan", "Annabelle", "wrong-Pass-1"),
        ("plan", "Nobody", ANN_PW),
        ("missing", "Annabelle", ANN_PW),
        ("../x", "A", ANN_PW),
    ],
)
def test_a_wrong_password_an_unknown_name_and_a_missing_document_are_the_same_answer(tmp_path, doc, name, password):
    store = store_in(tmp_path)
    start(store)
    assert sign_in(store, name, password, doc_id=doc) is None


def test_the_name_ai_cannot_log_in_and_other_rubbish_is_refused(tmp_path):
    store = store_in(tmp_path)
    start(store)
    with pytest.raises(AuthRefused, match="AI assistant"):
        sign_in(store, "AI", ANN_PW)
    assert store.verify("plan", Credentials(None, None)) is None
    assert store.verify("plan", Credentials("Annabelle", None)) is None
    assert store.verify("plan", Credentials(5, ANN_PW)) is None  # type: ignore[arg-type]


def test_a_missing_document_costs_as_much_time_as_a_wrong_password(tmp_path):
    """SEC-04: how long the answer takes must not tell whether a document exists."""
    store = SealedDocuments(tmp_path, ListModel, kdf=KdfParams(iterations=2, memory_kib=16384, lanes=1))
    start(store)

    def timed(doc_id):
        samples = []
        for _ in range(7):
            started = time.perf_counter()
            sign_in(store, "Annabelle", "wrong-Pass-1", doc_id=doc_id)
            samples.append(time.perf_counter() - started)
        return statistics.median(samples)

    existing, missing = timed("plan"), timed("nothing-here")
    assert 1 / 1.5 < existing / missing < 1.5, (existing, missing)


# --- only somebody with all the keys can bring a document up ---------------------------------------------------------


def test_a_viewer_cannot_bring_up_a_sealed_document(tmp_path):
    store = store_in(tmp_path)
    start(store)
    store.add_user("plan", "Cornelia", VERA_PW, "viewer")
    again = store_in(tmp_path)
    assert sign_in(again, "Cornelia", VERA_PW).role == "viewer"
    with pytest.raises(ValueError, match="sealed"):
        again.open("plan")


def test_an_editor_brings_it_up_and_then_the_viewer_may_come_in(tmp_path):
    store = store_in(tmp_path)
    start(store)
    store.add_user("plan", "Bertram", BEN_PW, "editor")
    again = store_in(tmp_path)
    assert sign_in(again, "Bertram", BEN_PW) is not None
    assert again.open("plan") is not None


def test_opening_without_a_login_is_refused(tmp_path):
    start(store_in(tmp_path))
    with pytest.raises(ValueError, match="sealed"):
        store_in(tmp_path).open("plan")


def test_a_login_that_is_not_followed_by_opening_does_not_keep_the_keys(tmp_path):
    start(store_in(tmp_path))
    clock = [0.0]
    again = store_in(tmp_path, key_ttl=30.0, clock=lambda: clock[0])
    assert sign_in(again, "Annabelle", ANN_PW) is not None
    clock[0] = 31.0
    with pytest.raises(ValueError, match="sealed"):
        again.open("plan")


def test_releasing_a_document_forgets_its_keys(tmp_path):
    store = store_in(tmp_path)
    start(store)
    store.add_user("plan", "Bertram", BEN_PW, "editor")  # possible while it is open
    store.release("plan")
    with pytest.raises(ValueError, match="sealed"):
        store.add_user("plan", "Cornelia", VERA_PW, "viewer")
    with pytest.raises(ValueError, match="sealed"):
        store.open("plan")


def test_releasing_a_document_that_is_not_open_is_harmless(tmp_path):
    store_in(tmp_path).release("never-opened")


# --- people ----------------------------------------------------------------------------------------------------------


def test_people_added_while_the_document_is_open_can_log_in_after_a_restart(tmp_path):
    store = store_in(tmp_path)
    start(store)
    account = store.add_user("plan", "Bertram", BEN_PW, "editor")
    assert (account.user, account.role) == ("Bertram", "editor")
    again = store_in(tmp_path)
    assert sign_in(again, "bertram", BEN_PW).role == "editor"
    assert sign_in(again, "bertram", "wrong-Pass-1") is None


def test_people_cannot_be_added_to_a_document_that_is_sealed(tmp_path):
    start(store_in(tmp_path))
    with pytest.raises(ValueError, match="sealed"):
        store_in(tmp_path).add_user("plan", "Bertram", BEN_PW, "editor")


def test_a_weak_password_is_refused_with_a_sentence_for_the_person(tmp_path):
    store = store_in(tmp_path)
    with pytest.raises(ValueError, match=r"at least 8 characters"):
        store.add_user("plan", "Annabelle", "short", "owner")
    assert not store.exists("plan")
    start(store)
    with pytest.raises(ValueError, match=r"capital letter"):
        store.add_user("plan", "Bertram", "alllowercase1", "editor")
    with pytest.raises(ValueError, match=r"digit"):
        store.add_user("plan", "Bertram", "NoDigitsHere", "editor")


@pytest.mark.parametrize("name", ["ai", "AI", " Ａｉ ", "bad\nname", "x" * 41, ""])
def test_unacceptable_names_are_refused(tmp_path, name):
    store = store_in(tmp_path)
    start(store)
    with pytest.raises(ValueError):
        store.add_user("plan", name, BEN_PW, "editor")


def test_a_name_can_be_used_once(tmp_path):
    store = store_in(tmp_path)
    start(store)
    with pytest.raises(ValueError, match="already"):
        store.add_user("plan", "ANNABELLE", BEN_PW, "editor")


def test_a_new_document_starts_with_its_owner(tmp_path):
    with pytest.raises(ValueError, match="owner"):
        store_in(tmp_path).add_user("plan", "Bertram", BEN_PW, "editor")


@pytest.mark.parametrize("doc_id", ["", "../outside", "a/b", "x" * 65, "with space"])
def test_a_document_id_cannot_leave_the_folder(tmp_path, doc_id):
    store = store_in(tmp_path)
    assert store.exists(doc_id) is False
    with pytest.raises(ValueError):
        store.add_user(doc_id, "Annabelle", ANN_PW, "owner")
    assert not any(tmp_path.parent.glob("outside*"))


def test_a_person_can_be_removed_again(tmp_path):
    store = store_in(tmp_path)
    start(store)
    store.add_user("plan", "Bertram", BEN_PW, "editor")
    store.remove_user("plan", "bertram")
    assert sign_in(store_in(tmp_path), "Bertram", BEN_PW) is None
    with pytest.raises(KeyError):
        store.remove_user("plan", "Bertram")


def test_the_only_user_of_a_brand_new_document_can_be_taken_back_with_the_document(tmp_path):
    """The gateway does this when creating the document fails after the owner was added."""
    store = store_in(tmp_path)
    store.add_user("plan", "Annabelle", ANN_PW, "owner")
    store.remove_user("plan", "Annabelle")
    assert not store.exists("plan")
    assert list((tmp_path / "docs").iterdir()) == []


def test_a_document_with_content_is_never_deleted_by_removing_its_last_user(tmp_path):
    store = store_in(tmp_path)
    fill(start(store))
    with pytest.raises(ValueError, match="owner"):
        store.remove_user("plan", "Annabelle")
    assert store.exists("plan")


# --- damage ----------------------------------------------------------------------------------------------------------


def test_a_half_written_last_change_is_ignored_and_the_journal_is_repaired(tmp_path):
    doc = start(store_in(tmp_path))
    fill(doc)
    journal = journal_path(tmp_path / "docs" / "plan.claudia")
    journal.write_bytes(journal.read_bytes()[:-6])  # the power went out while the last change was written
    _, back = reopen(tmp_path)
    assert back.model.items == [6, 5]
    back.execute(Insert(0, 1), author="Annabelle")  # and writing goes on
    assert reopen(tmp_path)[1].model.items == back.model.items


def test_a_changed_journal_is_refused_with_a_message_not_opened_wrongly(tmp_path):
    fill(start(store_in(tmp_path)))
    journal = journal_path(tmp_path / "docs" / "plan.claudia")
    data = bytearray(journal.read_bytes())
    data[len(data) // 2] ^= 1
    journal.write_bytes(bytes(data))
    again = store_in(tmp_path)
    assert sign_in(again, "Annabelle", ANN_PW) is not None
    with pytest.raises(ValueError, match="damaged|changed"):
        again.open("plan")


def test_a_file_that_is_not_a_document_does_not_break_the_list(tmp_path):
    store = store_in(tmp_path)
    start(store)
    (tmp_path / "docs" / "junk.claudia").write_bytes(b"not a zip")
    (tmp_path / "docs" / "notes.txt").write_text("hello")
    assert [info.id for info in store.documents()] == ["plan"]


def test_documents_are_listed_newest_first_with_their_app(tmp_path):
    store = store_in(tmp_path)
    start(store, "older")
    time.sleep(0.02)
    start(store, "newer")
    found = store.documents()
    assert [info.id for info in found] == ["newer", "older"]
    assert {info.app for info in found} == {ListModel.app}
    assert all(info.modified.endswith("Z") for info in found)


def test_creating_twice_is_refused(tmp_path):
    store = store_in(tmp_path)
    start(store)
    with pytest.raises(ValueError):
        store.create("plan")


def test_creating_needs_the_owner_first(tmp_path):
    with pytest.raises(ValueError, match="owner"):
        store_in(tmp_path).create("plan")


def test_a_writer_for_the_wrong_keys_cannot_continue_somebody_elses_journal(tmp_path):
    from claudia_container import Domain, random_key

    start(store_in(tmp_path))
    path = journal_path(tmp_path / "docs" / "plan.claudia")
    keys = {d: random_key() for d in Domain}
    writer = JournalWriter.open(path, "plan", keys)  # it can append, but nobody with the real keys can read it
    writer.append(Domain.HISTORY, b"x")
    writer.close()
    store = store_in(tmp_path)
    assert sign_in(store, "Annabelle", ANN_PW) is not None
    with pytest.raises(ValueError):
        store.open("plan")
