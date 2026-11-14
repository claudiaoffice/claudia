"""A document folder is used by one server at a time (D435)."""

import re
import subprocess
import sys

import pytest

from claudia_server.folder_lock import FolderLock, FolderLocked


def test_a_second_lock_on_the_same_folder_is_refused_until_the_first_is_let_go(tmp_path):
    first = FolderLock(tmp_path)
    first.acquire()
    with pytest.raises(FolderLocked, match=re.escape(str(tmp_path))):
        FolderLock(tmp_path).acquire()
    first.release()
    second = FolderLock(tmp_path)
    second.acquire()
    second.release()


def test_the_folder_is_made_if_it_does_not_exist(tmp_path):
    lock = FolderLock(tmp_path / "new" / "documents")
    lock.acquire()
    assert (tmp_path / "new" / "documents" / ".lock").is_file()
    lock.release()


def test_releasing_twice_or_without_acquiring_is_harmless(tmp_path):
    lock = FolderLock(tmp_path)
    lock.release()
    lock.acquire()
    lock.release()
    lock.release()


def test_another_process_holding_the_folder_keeps_this_one_out(tmp_path):
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys; from claudia_server.folder_lock import FolderLock; "
            "FolderLock(sys.argv[1]).acquire(); print('held', flush=True); sys.stdin.read()",
            str(tmp_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(FolderLocked):
            FolderLock(tmp_path).acquire()
    finally:
        holder.stdin.close()
        holder.wait(timeout=10)
    lock = FolderLock(tmp_path)  # the lock went away with the process
    lock.acquire()
    lock.release()
