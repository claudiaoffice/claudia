"""File ▸ Download: the steps of ``claudiaoffice-log/specs/document-file/download.feature`` (D110, D1270, E2.12).

What is bound here is what is automated; a scenario with a step that has no code here is skipped with its words
(``conftest.py``). Steps look at the page and at the file the browser saved, as a person would: the saved file is
opened with the document file library, the way the server opens a document, and looked at as bytes."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from conftest import PASSWORD
from pytest_bdd import given, parsers, scenarios, then, when

from claudia_document_file import unlock

scenarios("../../../claudiaoffice-log/specs/document-file/download.feature")

DIALOG = ".modal"


class Saved:
    """What the browser was given by the last click on Download: the file's name and bytes, or nothing."""

    def __init__(self) -> None:
        self.name: str | None = None
        self.data: bytes | None = None


def _state(world) -> Saved:
    if not hasattr(world, "saved"):
        world.saved = Saved()
    return world.saved


@given('a new composes document "report" in which I am Ann, an owner')
def _new_document(world):
    world.join("Ann").create()


@given(parsers.parse('the text has the paragraph "{words}"'))
def _paragraph(world, words):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type(words)


def _open_dialog(world) -> None:
    world.ann.menu("File", "Download")
    world.ann.page.wait_for_selector(f"{DIALOG} input[type=password]")


def _press_download(world, password: str, tmp_path: Path) -> None:
    page = world.ann.page
    page.fill(f"{DIALOG} input[type=password]", password)
    saved = _state(world)
    try:
        with page.expect_download(timeout=5000) as taken:
            page.click(f'{DIALOG} button:text-is("Download")')
        download = taken.value
        saved.name = download.suggested_filename
        target = tmp_path / saved.name
        download.save_as(target)
        saved.data = target.read_bytes()
    except Exception:  # no download came: that is what the scenario may be about
        saved.name = saved.data = None


@when("I choose File ▸ Download")
def _choose(world):
    _open_dialog(world)


@when("I choose File ▸ Download, type my password and press Download")
def _download(world, tmp_path):
    _open_dialog(world)
    _press_download(world, PASSWORD, tmp_path)


@when("I choose File ▸ Download, type a wrong password and press Download")
def _download_wrong(world, tmp_path):
    _open_dialog(world)
    _press_download(world, "Wrong-Pass-1", tmp_path)


@then('a file ending in ".claudia" is saved')
def _file_saved(world):
    saved = _state(world)
    assert saved.name is not None and saved.name.endswith(".claudia"), f"saved: {saved.name}"
    assert saved.data


@then("no file is saved")
def _no_file(world):
    assert _state(world).data is None


@then("I am told that it is not my current password")
def _told(world):
    world.ann.page.wait_for_selector('.toast:has-text("not your current password")', timeout=5000)


@then("the file opens with Ann's name and her password")
def _opens(world, tmp_path):
    saved = _state(world)
    target = tmp_path / "opened" / "report.claudia"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(saved.data)
    unlocked = unlock(target, "ann", PASSWORD)
    assert unlocked is not None and unlocked.role == "owner"


@then(parsers.parse('"{words}" cannot be read in the file without them'))
def _sealed(world, words):
    data = _state(world).data
    assert words.encode() not in data
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert not any(name.endswith(".txt") for name in names)
    for name in names:
        assert words.encode() not in zipfile.ZipFile(io.BytesIO(data)).read(name)


@then("the dialog says the file has the history, the chat and the people, and is still protected")
def _says_what_it_holds(world):
    text = world.ann.page.inner_text(DIALOG)
    assert "history" in text and "chat" in text and "people" in text and "protected" in text


@then("it says where to find Word, Excel and PowerPoint files instead")
def _says_where(world):
    assert "File ▸ Export" in world.ann.page.inner_text(DIALOG)
