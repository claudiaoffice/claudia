import pytest

from claudia_core import MAIN, CommandLog, Entry, Revision, RevisionMismatch
from claudia_core.testing import Insert, ListModel


def entry(rev, parent, value=1):
    return Entry(rev, parent, "ana", "2026-11-01T12:00:00.000Z", Insert(0, value))


def test_revision_text_roundtrip():
    r = Revision("main", 12)
    assert str(r) == "main:12" and Revision.parse("main:12") == r
    assert Revision.parse("what-if_1:3") == Revision("what-if_1", 3)


@pytest.mark.parametrize("bad", ["main", "main:", ":3", "Main:3", "main:x"])
def test_bad_revision_text(bad):
    with pytest.raises(ValueError):
        Revision.parse(bad)


def test_revision_numbers_start_at_one():
    with pytest.raises(ValueError):
        Revision("main", 0)


def test_append_must_be_next():
    log = CommandLog()
    log.append(entry(Revision(MAIN, 1), None))
    with pytest.raises(RevisionMismatch):
        log.append(entry(Revision(MAIN, 3), Revision(MAIN, 1)))
    with pytest.raises(RevisionMismatch):
        log.append(entry(Revision(MAIN, 2), None))  # wrong parent


def test_fork_numbers_continue_and_path_follows_fork():
    log = CommandLog()
    prev = None
    for i in range(1, 5):
        rev = Revision(MAIN, i)
        log.append(entry(rev, prev, i))
        prev = rev
    branch = log.fork("alt", Revision(MAIN, 2))
    assert branch.fork_point == Revision(MAIN, 2)
    assert log.head("alt") == Revision(MAIN, 2)  # no own entries yet
    assert log.next_revision("alt") == Revision("alt", 3)
    log.append(entry(Revision("alt", 3), Revision(MAIN, 2), 30))
    log.append(entry(Revision("alt", 4), Revision("alt", 3), 40))
    assert [str(e.rev) for e in log.path(Revision("alt", 4))] == ["main:1", "main:2", "alt:3", "alt:4"]
    assert [str(e.rev) for e in log.path(Revision(MAIN, 4))] == ["main:1", "main:2", "main:3", "main:4"]
    assert [str(e.rev) for e in log.since(Revision(MAIN, 1), "alt")] == ["main:2", "alt:3", "alt:4"]


def test_log_roundtrips_through_data():
    log = CommandLog()
    log.append(entry(Revision(MAIN, 1), None, 7))
    log.fork("alt", Revision(MAIN, 1))
    log.append(entry(Revision("alt", 2), Revision(MAIN, 1), 8))
    again = CommandLog.from_data(log.to_data(), ListModel.registry)
    assert again.to_data() == log.to_data()


def test_unknown_revision():
    log = CommandLog()
    with pytest.raises(KeyError):
        log.get(Revision(MAIN, 1))
    with pytest.raises(KeyError):
        log.fork("x", Revision(MAIN, 1))


def test_since_equals_the_naive_slice_of_the_path_on_every_line(make_doc):
    from claudia_core.testing import Insert

    doc = make_doc()
    for i in range(4):
        doc.execute(Insert(0, i), author="ana")
    doc.save_checkpoint("ana", "a")
    doc.execute(Insert(0, 9), author="ben")
    doc.restore_checkpoint(1, author="ana")
    doc.execute(Insert(0, 8), author="ben")
    for name in doc.log.branches:
        path = doc.log.path(doc.log.head(name))
        assert doc.log.since(None, name) == path
        for index, entry in enumerate(path):
            assert doc.log.since(entry.rev, name) == path[index + 1 :]
    with pytest.raises(KeyError):
        doc.log.since(Revision("main", 6), "restore-1")  # exists, but not on that line's path
