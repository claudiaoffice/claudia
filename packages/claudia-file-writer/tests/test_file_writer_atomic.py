"""Writing a file all at once (CODE-34, D701)."""

import os
import sys

import pytest

from claudia_file_writer import Replacer, atomic_file, fsync_directory, write_atomically, write_once

POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")


def leftovers(folder):
    return sorted(p.name for p in folder.iterdir() if p.name.endswith(".tmp"))


def test_a_file_is_written_and_replaces_the_old_one(tmp_path):
    target = tmp_path / "a.json"
    write_atomically(target, b"one")
    write_atomically(target, b"two")
    assert target.read_bytes() == b"two"
    assert leftovers(tmp_path) == []


@POSIX_ONLY
def test_a_file_is_private_unless_it_is_told_otherwise(tmp_path):
    write_atomically(tmp_path / "secret", b"x")
    write_atomically(tmp_path / "public", b"x", mode=0o644)
    assert (tmp_path / "secret").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "public").stat().st_mode & 0o777 == 0o644


@POSIX_ONLY
def test_the_mode_is_the_one_asked_for_whatever_the_umask(tmp_path):
    """The Docker image fetches as root with a strict umask, and the server reads as another user."""
    old = os.umask(0o077)
    try:
        write_atomically(tmp_path / "public", b"x", mode=0o644)
    finally:
        os.umask(old)
    assert (tmp_path / "public").stat().st_mode & 0o777 == 0o644


def test_a_file_that_cannot_be_moved_into_place_leaves_nothing_behind(tmp_path):
    def refuse(temp, path):
        raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        write_atomically(tmp_path / "a", b"x", replacer=Replacer(replace=refuse))
    assert list(tmp_path.iterdir()) == []


def test_a_writer_that_fails_halfway_leaves_the_old_file_and_nothing_else(tmp_path):
    target = tmp_path / "a"
    target.write_bytes(b"old")
    with pytest.raises(RuntimeError), atomic_file(target) as out:
        out.write(b"half of the new")
        raise RuntimeError("the writer broke")
    assert target.read_bytes() == b"old"
    assert leftovers(tmp_path) == []


def test_a_file_can_be_written_in_pieces(tmp_path):
    with atomic_file(tmp_path / "a", durable=True) as out:
        out.write(b"one ")
        out.write(b"two")
    assert (tmp_path / "a").read_bytes() == b"one two"


def test_a_durable_write_syncs_the_folder_too(tmp_path, monkeypatch):
    synced = []
    monkeypatch.setattr("claudia_file_writer.atomic.fsync_directory", synced.append)
    write_atomically(tmp_path / "a", b"x", durable=True)
    write_atomically(tmp_path / "b", b"x")
    assert synced == [tmp_path]


def test_syncing_a_folder_the_system_cannot_open_is_not_an_error(tmp_path):
    fsync_directory(tmp_path / "not there")
    fsync_directory(tmp_path)


class Flaky:
    """A replace that the system refuses ``times`` times, the way Windows does while a scanner holds the file."""

    def __init__(self, times):
        self.left = times
        self.calls = 0

    def __call__(self, temp, path):
        self.calls += 1
        if self.left:
            self.left -= 1
            raise PermissionError("[WinError 5] Access is denied")
        os.replace(temp, path)


def test_on_windows_a_refused_replace_is_tried_again_with_longer_waits(tmp_path):
    waits = []
    flaky = Flaky(3)
    write_atomically(tmp_path / "a", b"x", replacer=Replacer(windows=True, replace=flaky, sleep=waits.append))
    assert (tmp_path / "a").read_bytes() == b"x"
    assert flaky.calls == 4
    assert waits == [0.05, 0.1, 0.2]


def test_the_waits_stop_growing_at_a_second(tmp_path):
    waits = []
    replacer = Replacer(windows=True, replace=Flaky(9), sleep=waits.append)
    write_atomically(tmp_path / "a", b"x", replacer=replacer)
    assert max(waits) == 1.0
    assert sum(waits) < 10


def test_on_windows_a_replace_refused_every_time_fails_in_the_end(tmp_path):
    waits = []
    flaky = Flaky(100)
    replacer = Replacer(windows=True, attempts=4, replace=flaky, sleep=waits.append)
    with pytest.raises(PermissionError):
        write_atomically(tmp_path / "a", b"x", replacer=replacer)
    assert flaky.calls == 4
    assert len(waits) == 3
    assert leftovers(tmp_path) == []


def test_elsewhere_a_refused_replace_is_not_tried_again(tmp_path):
    flaky = Flaky(1)
    with pytest.raises(PermissionError):
        write_atomically(tmp_path / "a", b"x", replacer=Replacer(windows=False, replace=flaky, sleep=pytest.fail))
    assert flaky.calls == 1


def test_a_replace_that_fails_for_another_reason_is_not_tried_again(tmp_path):
    def missing(temp, path):
        raise FileNotFoundError(path)

    with pytest.raises(FileNotFoundError):
        write_atomically(tmp_path / "a", b"x", replacer=Replacer(windows=True, replace=missing, sleep=pytest.fail))


def test_the_last_refusal_names_a_handle_of_this_process_that_holds_the_file(tmp_path):
    """Retrying cannot help when the handle is our own; the error says so instead of leaving a guess (CODE-34)."""
    target = tmp_path / "a"
    target.write_bytes(b"old")
    with target.open("rb"):
        replacer = Replacer(windows=True, attempts=2, replace=Flaky(100), sleep=lambda _s: None)
        with pytest.raises(PermissionError, match="still open in this process"):
            write_atomically(target, b"x", replacer=replacer)


def test_write_once_writes_a_file_that_is_not_there_yet(tmp_path):
    assert write_once(tmp_path / "abc.svg", b"x") is True
    assert (tmp_path / "abc.svg").read_bytes() == b"x"


def test_write_once_leaves_a_file_that_is_there(tmp_path):
    (tmp_path / "abc.svg").write_bytes(b"first")
    assert write_once(tmp_path / "abc.svg", b"second") is False
    assert (tmp_path / "abc.svg").read_bytes() == b"first"


def test_write_once_loses_a_race_without_an_error_and_without_waiting(tmp_path):
    """On Windows a cache file another request just wrote may be held open by the one sending it: the bytes are the same
    (the name is their hash), so the file being there is enough."""
    target = tmp_path / "abc.svg"

    def the_other_writer_was_first(temp, path):
        path.write_bytes(b"theirs")
        raise PermissionError("[WinError 5] Access is denied")

    replacer = Replacer(windows=True, replace=the_other_writer_was_first, sleep=pytest.fail)
    assert write_once(target, b"ours", replacer=replacer) is False
    assert target.read_bytes() == b"theirs"
    assert leftovers(tmp_path) == []


def test_write_once_waits_like_any_write_when_the_file_is_still_not_there(tmp_path):
    waits = []
    flaky = Flaky(2)
    assert write_once(tmp_path / "a", b"x", replacer=Replacer(windows=True, replace=flaky, sleep=waits.append))
    assert (tmp_path / "a").read_bytes() == b"x"
    assert waits == [0.05]


def test_looking_for_our_handles_never_hides_the_refusal(tmp_path, monkeypatch):
    def broken():
        raise RuntimeError("the garbage collector is not available")

    monkeypatch.setattr("claudia_file_writer.atomic.gc.get_objects", broken)
    replacer = Replacer(windows=True, attempts=1, replace=Flaky(1), sleep=pytest.fail)
    with pytest.raises(PermissionError, match="Access is denied$"):
        write_atomically(tmp_path / "a", b"x", replacer=replacer)
