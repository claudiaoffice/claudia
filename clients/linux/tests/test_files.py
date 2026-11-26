"""The shell's side of the page's files (D501, D502), without GTK: the dialogs are fakes, the files are real, in a
temporary folder. The twin of ``clients/neutralino/tests/files.test.ts``."""

from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from claudia_shell_gtk import contract
from claudia_shell_gtk.files import Files


class FakeDialogs:
    def __init__(self, *, open_: Path | None = None, save: Path | None = None, fails: bool = False) -> None:
        self.answers = {"open": open_, "save": save}
        self.fails = fails
        self.asked: list[tuple[object, ...]] = []
        self.shown: list[Path] = []

    def open(self, title: str, extensions: list[str], folder: Path | None, chosen, failed) -> None:
        self.asked.append(("open", title, extensions, folder))
        failed("no dialog") if self.fails else chosen(self.answers["open"])

    def save(self, title: str, name: str, extensions: list[str], folder: Path | None, chosen, failed) -> None:
        self.asked.append(("save", title, name, extensions, folder))
        failed("no dialog") if self.fails else chosen(self.answers["save"])

    def show(self, path: Path, done: Callable[[], None], failed) -> None:
        self.shown.append(path)
        done()


class Reply:
    def __init__(self) -> None:
        self.sent: list[tuple[Any, ...]] = []

    def send_file_result(self, request: str, outcome: str, **details: object) -> bool:
        self.sent.append(("result", request, outcome, details))
        return True

    def send_file_chunk(self, request: str, index: int, data: str) -> bool:
        self.sent.append(("chunk", request, index, data))
        return True

    def send_file_done(self, request: str, chunks: int) -> bool:
        self.sent.append(("done", request, chunks))
        return True

    def send_file_offer(self, request: str, name: str, size: int) -> bool:
        self.sent.append(("offer", request, name, size))
        return True


def desk(tmp_path: Path, dialogs: FakeDialogs) -> tuple[Files, Reply]:
    reply = Reply()
    return Files(dialogs, reply, documents=tmp_path / "Documents", print_folder=tmp_path / "print"), reply


def hand_over(files: Files, request: str, name: str, data: bytes, purpose: str = "save") -> None:
    files.begin(request, name, len(data), purpose)
    step = contract.FILE_CHUNK_BYTES
    pieces = range(0, len(data), step)
    for index, at in enumerate(pieces):
        files.chunk(request, index, base64.b64encode(data[at : at + step]).decode())
    files.done(request, len(pieces))


def test_the_chosen_file_goes_to_the_page_in_pieces_after_its_name_size_and_path(tmp_path: Path) -> None:
    path = tmp_path / "Budget.docx"
    data = bytes(range(256)) * (contract.FILE_CHUNK_BYTES // 256 + 1)
    path.write_bytes(data)
    dialogs = FakeDialogs(open_=path)
    files, reply = desk(tmp_path, dialogs)
    files.pick("f1", ["docx", "odt"], None)
    assert dialogs.asked == [("open", "Open a File", ["docx", "odt"], None)]
    # the path, for Insert ▸ Image's "Don't save the path" (SEC-27)
    assert reply.sent[0] == ("result", "f1", "picked", {"name": "Budget.docx", "size": len(data), "path": str(path)})
    chunks = [m for m in reply.sent if m[0] == "chunk"]
    assert [m[2] for m in chunks] == [0, 1]
    assert b"".join(base64.b64decode(m[3]) for m in chunks) == data
    assert reply.sent[-1] == ("done", "f1", 2)


@pytest.mark.parametrize(("fails", "outcome"), [(False, "cancelled"), (True, "failed")])
def test_a_cancelled_dialog_and_one_that_could_not_be_shown(tmp_path: Path, fails: bool, outcome: str) -> None:
    files, reply = desk(tmp_path, FakeDialogs(fails=fails))
    files.pick("f1", [], None)
    assert [(m[0], m[2]) for m in reply.sent] == [("result", outcome)]


def test_a_chosen_file_that_cannot_be_read_is_explained(tmp_path: Path) -> None:
    files, reply = desk(tmp_path, FakeDialogs(open_=tmp_path / "gone.docx"))
    files.pick("f1", [], None)
    assert reply.sent[0][2] == "failed" and "gone.docx" in reply.sent[0][3]["message"]


def test_a_file_is_saved_where_the_person_chose_starting_in_documents(tmp_path: Path) -> None:
    target = tmp_path / "Budget 2027.xlsx"
    dialogs = FakeDialogs(save=target)
    files, reply = desk(tmp_path, dialogs)
    data = bytes(i % 256 for i in range(contract.FILE_CHUNK_BYTES * 2 + 3))
    hand_over(files, "f2", "Budget 2027.xlsx", data)
    assert dialogs.asked == [("save", "Save", "Budget 2027.xlsx", ["xlsx"], tmp_path / "Documents")]
    assert target.read_bytes() == data
    assert reply.sent == [("result", "f2", "saved", {"path": str(target)})]
    hand_over(files, "f3", "b.txt", b"b")
    assert dialogs.asked[-1][-1] == tmp_path  # the next dialog starts where the last file went


def test_nothing_is_written_when_the_save_dialog_was_cancelled(tmp_path: Path) -> None:
    files, reply = desk(tmp_path, FakeDialogs(save=None))
    hand_over(files, "f2", "a.txt", b"abc")
    assert reply.sent == [("result", "f2", "cancelled", {})]


def test_a_file_that_lost_a_piece_or_came_incomplete_is_refused_without_asking(tmp_path: Path) -> None:
    dialogs = FakeDialogs(save=tmp_path / "a.txt")
    files, reply = desk(tmp_path, dialogs)
    files.begin("f2", "a.txt", 6, "save")
    files.chunk("f2", 1, base64.b64encode(b"abc").decode())
    files.done("f2", 1)
    files.begin("f3", "a.txt", 6, "save")
    files.chunk("f3", 0, base64.b64encode(b"abc").decode())
    files.done("f3", 1)
    assert dialogs.asked == []
    assert [m[2] for m in reply.sent] == ["failed", "failed"]


def test_a_pdf_to_print_opens_in_the_viewer_from_a_folder_of_its_own(tmp_path: Path) -> None:
    dialogs = FakeDialogs()
    files, reply = desk(tmp_path, dialogs)
    hand_over(files, "f4", "../../Quarterly.pdf", b"%PDF-1.7", purpose="print")
    printed = tmp_path / "print" / "Quarterly.pdf"
    assert dialogs.asked == []  # nothing to ask: it is printed from the viewer (D502)
    assert dialogs.shown == [printed]
    assert printed.read_bytes() == b"%PDF-1.7"
    assert reply.sent == [("result", "f4", "opened", {"path": str(printed)})]
    assert not (tmp_path / "Quarterly.pdf").exists()  # the name could not climb out of its folder


def test_a_dropped_file_goes_to_the_page_as_an_offer_in_pieces(tmp_path: Path) -> None:
    """D505: WebKitGTK does not hand a file dropped from the file manager to the page; the window does."""
    path = tmp_path / "Budget.xlsx"
    data = bytes(range(256)) * (contract.FILE_CHUNK_BYTES // 256 + 1)
    path.write_bytes(data)
    reply = Reply()
    files = Files(FakeDialogs(), reply, documents=tmp_path)
    assert files.offer(path)
    assert reply.sent[0] == ("offer", "drop-1", "Budget.xlsx", len(data))
    chunks = [m for m in reply.sent if m[0] == "chunk"]
    assert b"".join(base64.b64decode(m[3]) for m in chunks) == data
    assert reply.sent[-1] == ("done", "drop-1", len(chunks))
    assert files.offer(path)
    assert reply.sent[-1][1] == "drop-2"  # every drop is a transfer of its own


def test_a_dropped_folder_or_a_missing_file_is_not_offered(tmp_path: Path) -> None:
    reply = Reply()
    files = Files(FakeDialogs(), reply, documents=tmp_path)
    assert not files.offer(tmp_path)
    assert not files.offer(tmp_path / "gone.docx")
    assert reply.sent == []
