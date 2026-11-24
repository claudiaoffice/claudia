"""File ▸ Manage ▸ Export… as Claudia's unencrypted zip, the record of what left and the import of the zip: steps of
``claudiaoffice-log/specs/document-file/export-and-record.feature`` (D1270, D1271, D1272, E2.9).

Scenarios tagged ``@unit`` are run by the unit tests they name, not here. The saved file is opened as a person
would: as a zip, looking at its names and its bytes."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from playwright.sync_api import expect
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../../../claudiaoffice-log/specs/document-file/export-and-record.feature")

DIALOG = ".modal"
UNPROTECTED_FORMAT = "claudia-unencrypted"


class Saved:
    """What the browser was given by the last export: the file's name and bytes, or nothing."""

    def __init__(self) -> None:
        self.name: str | None = None
        self.data: bytes | None = None


def _saved(world) -> Saved:
    if not hasattr(world, "saved"):
        world.saved = Saved()
    return world.saved


def _rows(person) -> list[str]:
    return [t.strip() for t in person.page.locator("[data-testid=audit-row] .what").all_inner_texts()]


# -- the document -------------------------------------------------------------------------------------------------
@given('a new composes document "plan" in which I am Ann, an owner')
def _new_document(world):
    world.join("Ann").create()


@given(parsers.parse('the text has the paragraph "{words}"'))
def _paragraph(world, words):
    page = world.ann.page
    page.click("[data-testid=text]")
    page.keyboard.type(words)
    page.wait_for_function("document.querySelector('.health.open')")


@given("Ben is an editor of the document")
def _ben_is_an_editor(world):
    world.ann.share(world.join("Ben"), "editor")


@given("I exported the document without protection")
def _exported_before(world, tmp_path):
    _open_export(world.ann)
    _choose_unprotected(world.ann)
    _press_export(world.ann)
    _confirm(world.ann, tmp_path, world)


# -- the export dialog ---------------------------------------------------------------------------------------------
def _open_export(person) -> None:
    person.menu("File", "Manage")
    person.page.click('.menus [role=menuitem]:has-text("Export…")')
    person.page.wait_for_selector("[data-testid=export-format]")


def _choose_unprotected(person) -> None:
    person.page.select_option("[data-testid=export-format]", UNPROTECTED_FORMAT)


def _press_export(person) -> None:
    person.page.click(f'{DIALOG} button:text-is("Export")')


def _confirm(person, tmp_path: Path, world) -> None:
    """Press the second button ("Export unprotected") and take the file the browser is given."""
    person.page.wait_for_selector("[data-testid=export-unprotected-confirm]")
    saved = _saved(world)
    with person.page.expect_download(timeout=10000) as taken:
        person.page.click("[data-testid=export-unprotected]")
    download = taken.value
    saved.name = download.suggested_filename
    target = tmp_path / saved.name
    download.save_as(target)
    saved.data = target.read_bytes()


@when(parsers.parse('I choose File ▸ Manage ▸ Export… and the format "{label}"'))
def _choose_format(world, label):
    assert label.startswith("Claudia, unencrypted")
    _open_export(world.ann)
    _choose_unprotected(world.ann)


@when('I tick "Include history and chat"')
def _tick(world):
    world.ann.page.check("[data-testid=export-history]")


@when("I press Export")
def _export(world):
    _press_export(world.ann)


@when("I press Export unprotected")
def _export_unprotected(world, tmp_path):
    _confirm(world.ann, tmp_path, world)


@when("I press Cancel at the question")
def _cancel(world):
    world.ann.page.click(f'{DIALOG} .confirm ~ .buttons button:text-is("Cancel")')


@when("Ben opens the document")
def _ben_opens(world):
    world.people["Ben"].open()
    world.people["Ben"].wait_until_open()


@when(parsers.parse('Ben chooses File ▸ Manage ▸ Export… and the format "{label}"'))
def _ben_chooses(world, label):
    ben = world.people["Ben"]
    _open_export(ben)
    _choose_unprotected(ben)


# -- what is asked and what is saved ---------------------------------------------------------------------------
@then(parsers.parse('I am asked "{question}" and told that anyone who gets the file can read it'))
def _asked(world, question):
    box = world.ann.page.locator("[data-testid=export-unprotected-confirm]")
    expect(box).to_contain_text(question)
    expect(box).to_contain_text("Anyone who gets the file can read it.")


@then('a file ending in ".claudia-export.zip" is saved')
def _file_saved(world):
    saved = _saved(world)
    assert saved.name is not None and saved.name.endswith(".claudia-export.zip"), f"saved: {saved.name}"
    assert saved.data


@then("no file is saved")
def _no_file(world):
    assert _saved(world).data is None
    expect(world.ann.page.locator("[data-testid=export-unprotected-confirm]")).to_have_count(0)


def _zip(world) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(_saved(world).data))


@then(parsers.parse('the file is a zip with a readable "content.json" that holds "{words}"'))
def _readable(world, words):
    with _zip(world) as archive:
        assert words in archive.read("content.json").decode("utf-8")


@then("the file has no key slots, no list of people and no password hashes")
def _no_keys(world):
    with _zip(world) as archive:
        names = archive.namelist()
        assert not any(n.startswith(("slots", "people", "keys")) or "slot" in n for n in names), names
        text = b"".join(archive.read(n) for n in names)
    for word in (b"salt", b"argon", b"wrapped", b"recovery"):
        assert word not in text.lower(), word


@then(parsers.parse('the file holds a "{part}" and a "{other}"'))
def _holds(world, part, other):
    with _zip(world) as archive:
        assert part in archive.namelist() and other in archive.namelist(), archive.namelist()


# -- the record -------------------------------------------------------------------------------------------------
@then(parsers.parse('the History & Chat panel has the muted line "{line}"'))
def _has_line(world, line):
    page = world.ann.page
    expect(page.locator("[data-testid=audit-row] .what", has_text=line).first).to_be_visible(timeout=10000)


@then("the History & Chat panel has no muted line about an export")
def _no_line(world):
    assert not [r for r in _rows(world.ann) if "export" in r]


@then(parsers.parse('the History & Chat panel has a muted line beginning "{start}"'))
def _line_begins(world, start):
    page = world.ann.page
    page.wait_for_function(
        "s => [...document.querySelectorAll('[data-testid=audit-row] .what')]"
        ".some(e => e.textContent.trim().startsWith(s))",
        arg=start,
        timeout=10000,
    )


# -- an editor ----------------------------------------------------------------------------------------------------
@then("Ben sees no box to include history and chat")
def _ben_no_box(world):
    expect(world.people["Ben"].page.locator("[data-testid=export-history]")).to_have_count(0)


@then("Ben is told that history and chat can only be exported by owners")
def _ben_told(world):
    hint = world.people["Ben"].page.locator("[data-testid=export-owners-only]")
    expect(hint).to_contain_text("only be exported by owners")


# -- the PDF ---------------------------------------------------------------------------------------------------------
@when("I choose File ▸ Print… and press Download PDF")
def _pdf(world):
    page = world.ann.page
    world.ann.menu("File", "Print…")
    button = page.locator("[data-testid=print-download]")
    expect(button).to_be_enabled(timeout=30000)
    with page.expect_download(timeout=30000):
        button.click()


# -- the way back in -------------------------------------------------------------------------------------------
@when("I give that file to the Open page")
def _give(world, tmp_path):
    saved = _saved(world)
    target = tmp_path / saved.name
    target.write_bytes(saved.data)
    page = world.ann.page
    page.goto(world.ann.url + "/", wait_until="domcontentloaded")
    page.set_input_files("input[type=file]", str(target))
    page.wait_for_selector("[data-testid=export-made]", timeout=15000)


@then(parsers.parse('the dialog says "{words}"'))
def _dialog_says(world, words):
    expect(world.ann.page.locator("[data-testid=export-made]")).to_contain_text(words)


@then("the dialog has no box to keep the original")
def _no_keep(world):
    expect(world.ann.page.locator("input[name=keep-original]")).to_have_count(0)


@when(parsers.parse('I name the new document "{name}" and give a password and press Open'))
def _name_and_open(world, name):
    world.ann.finish_import(name)
    page = world.ann.page
    page.wait_for_selector("[data-testid=text]", timeout=20000)
    page.wait_for_function("document.querySelector('.health.open')", timeout=20000)


@then(parsers.parse('the new document has the paragraph "{words}"'))
def _new_has(world, words):
    assert any(words in p for p in world.ann.paragraphs())


@then("I am its only owner")
def _only_owner(world):
    ann = world.ann
    ann.menu("File", "Manage")
    ann.page.click('.menus [role=menuitem]:has-text("Share…")')
    expect(ann.page.locator(DIALOG)).to_contain_text("Share this document")
    expect(ann.page.locator(f"{DIALOG} .added li")).to_have_count(0)  # nobody was given access
    ann.page.click(f'{DIALOG} button:text-is("Done")')
    expect(ann.page.get_by_label("people in this document").locator("li")).to_have_count(2)  # ann (you), and the AI
