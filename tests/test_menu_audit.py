"""The menu audit's comparison (``scripts/menu_audit.py``): small menus made up here, no browser, no workbook file."""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import menu_audit as audit  # noqa: E402
from menu_audit import App, Entry, Row  # noqa: E402


def row(number: int, menu: str, entry: str, *, groups=None, key="Ctrl+K", today_id=None, today_label=None) -> Row:
    return Row(
        number=number,
        menu=menu,
        path=tuple(p.strip() for p in entry.split("▸")),
        groups=groups or {"composes": 1},
        keys=dict.fromkeys(audit.PLATFORMS, key) | {"macOS": audit.mac_key(key)},
        today_labels=audit.today_labels(today_label),
        today_id=today_id,
    )


def app(desktop: list[Entry], web: list[Entry]) -> App:
    return App("composes", desktop, web, {"editor": web, "viewer": web})


class TestNormalising:
    def test_keys_are_written_as_the_web_menus_show_them(self):
        assert audit.normal_key("Shift+Alt+Up") == "Shift+Alt+↑"
        assert audit.normal_key("n/a") is None
        assert audit.normal_key(None) is None

    def test_a_switch_note_is_not_part_of_the_label(self):
        assert audit.clean_label("Dark mode (switch)") == "Dark mode"

    def test_capitalisation_alone_is_told_apart_from_other_words(self):
        assert audit.compare_labels("Rename sheet…", "Rename Sheet…") == "case"
        assert audit.compare_labels("Palette", "Colours…") == "words"
        assert audit.compare_labels("Copy", "Copy") is None

    def test_same_words_ignores_case_the_ellipsis_and_the_submenu_arrow(self):
        assert audit.same_words("Table", "Table…")
        assert audit.same_words("Sort ▸", "Sort")
        assert not audit.same_words("Table", "Table of contents")

    def test_todays_label_per_app_or_for_all(self):
        assert audit.today_labels("computes: A / creates: B") == {"computes": "A", "creates": "B"}
        assert audit.today_labels("Copy") == dict.fromkeys(audit.APPS, "Copy")

    def test_the_macos_key_of_a_ctrl_alt_key(self):
        assert audit.mac_key("Ctrl+Alt+N") == "Cmd+Option+N"


class TestWebCapture:
    def test_separators_make_groups_and_a_greyed_submenu_is_sealed(self):
        captured = {
            "Edit": [
                {"label": "Undo", "disabled": True, "hint": "Ctrl+Z"},
                {"sep": True},
                {"label": "Row", "disabled": True, "hint": None, "sub": True},
                {
                    "label": "Paste As",
                    "disabled": False,
                    "hint": None,
                    "sub": True,
                    "items": [{"label": "Plain Text", "disabled": False, "hint": "Ctrl+Shift+V"}],
                },
            ]
        }
        entries = audit.web_entries(captured)
        assert [(e.path, e.group, e.sealed) for e in entries] == [
            (("Undo",), 1, False),
            (("Row",), 2, True),
            (("Paste As",), 2, False),
            (("Paste As", "Plain Text"), 1, False),
        ]

    def test_style_names_are_left_out_but_an_entry_with_a_key_stays(self):
        captured = {
            "Format": [
                {
                    "label": "Apply Style",
                    "disabled": False,
                    "hint": "Ctrl+Alt+A",
                    "sub": True,
                    "items": [
                        {"label": "Body text", "disabled": False, "hint": None},
                        {"label": "Clear Cell Style", "disabled": False, "hint": "Ctrl+Shift+Alt+K"},
                    ],
                }
            ]
        }
        assert [e.path for e in audit.web_entries(captured)] == [("Apply Style",), ("Apply Style", "Clear Cell Style")]


class TestPairing:
    def test_the_one_entry_left_in_a_menu_pairs_even_with_other_words(self):
        desktop = [Entry("Help", ("About Claudia Composes",), 1, 0, "Ctrl+Shift+F1", "help.about")]
        web = [Entry("Help", ("About claudia",), 1, 0, "Ctrl+Shift+F1")]
        assert app(desktop, web).twin[0] is web[0]

    def test_an_entry_inside_a_greyed_submenu_pairs_with_the_submenu(self):
        desktop = [Entry("Tools", ("Row", "Delete"), 1, 0, None, "edit.row-delete")]
        web = [Entry("Tools", ("Row",), 1, 0, None, None, True, True, True)]
        assert app(desktop, web).twin[0] is web[0]


class TestOneRow:
    def test_an_entry_in_another_menu_with_other_words_and_another_key(self):
        desktop = [Entry("Edit", ("Search & Replace…",), 1, 0, "Ctrl+F", "edit.search-replace")]
        web = [Entry("Edit", ("Search & Replace…",), 1, 0, "Ctrl+F")]
        wanted = row(70, "Tools", "Search and replace…", key="Ctrl+H", today_id="edit.search-replace")
        kinds = [f.kind for f in audit.compare_row(app(desktop, web), wanted)]
        assert kinds == ["Wrong menu", "Label", "Key"]

    def test_capitalisation_only(self):
        entries = [Entry("Edit", ("Rename Sheet…",), 1, 0, "Ctrl+K", "edit.rename-sheet")]
        wanted = row(20, "Edit", "Rename sheet…", today_id="edit.rename-sheet")
        assert [f.kind for f in audit.compare_row(app(entries, list(entries)), wanted)] == [
            "Label: capitalisation only"
        ]

    def test_a_new_entry_that_exists_nowhere_is_not_built_yet(self):
        found = list(audit.compare_row(app([], []), row(59, "View", "Quiet mode (switch)")))
        assert [f.kind for f in found] == ["Not built yet"]
        assert not found[0].decide

    def test_a_new_entry_found_by_its_words_is_not_new(self):
        web = [Entry("Insert", ("Table…",), 1, 0, "Ctrl+Shift+F")]
        found = list(audit.compare_row(app([], web), row(27, "Insert", "Table", key="Ctrl+Shift+Alt+T")))
        assert [f.kind for f in found] == ["Label", "Key"]  # the dialog's "…" is part of the words

    def test_a_different_key_on_one_platform_asks_for_a_decision(self):
        wanted = row(1, "File", "New")
        wanted.keys["Windows"] = "Ctrl+N"
        entries = [Entry("File", ("New",), 1, 0, "Ctrl+K", "file.new")]
        found = [f for f in audit.compare_row(app(entries, list(entries)), wanted) if f.kind == "Key per platform"]
        assert found and found[0].decide


class TestWorkbook:
    def test_rows_written_after_their_menu_ended_are_found(self):
        rows = [row(1, "File", "New"), row(2, "View", "Dark mode"), row(3, "Help", "About"), row(4, "View", "Back")]
        assert audit.misplaced_rows(rows) == {4}

    def test_a_note_that_drops_an_entry_is_found_by_its_id_first(self):
        texts = [
            ("Menus", "Next: drop the old Save action (file.save) in the manifest, web menus and the shells."),
            ("Menus", "Next: rename file.save-as to Save checkpoint… and bind it to Ctrl+S everywhere."),
        ]
        found = audit.mention(texts, Entry("File", ("Save",), 1, 0, "Ctrl+S", "file.save"))
        assert "(file.save)" in found

    def test_the_menus_sheet_is_read_by_its_headers(self):
        sheet = openpyxl.Workbook().active
        sheet.append(
            [
                "#",
                "Menu",
                "Entry",
                "computes",
                "composes",
                "creates",
                "Web",
                "Linux",
                "Windows",
                "macOS",
                "Today's label",
                "Today's action id",
            ]
        )
        sheet.append(
            [
                4,
                "File",
                "Save checkpoint…",
                2,
                2,
                None,
                "Ctrl+S",
                "Ctrl+S",
                "Ctrl+S",
                "Cmd+S",
                "Save New Checkpoint…",
                "file.save-as",
            ]
        )
        (only,) = audit.workbook_rows(sheet)
        assert (only.path, only.groups, only.keys["macOS"], only.today_id) == (
            ("Save checkpoint…",),
            {"computes": 2, "composes": 2},
            "Cmd+S",
            "file.save-as",
        )


@pytest.mark.parametrize("label", ["Format", "Agenda"])
def test_words_that_are_the_same_in_german_are_not_untranslated(label):
    english = {"Insert": [{"label": label, "disabled": False, "hint": None}]}
    assert list(audit.compare_german("creates", english, english)) == []


def test_an_untranslated_entry_is_found():
    english = {"Edit": [{"label": "Circle", "disabled": False, "hint": None}]}
    german = {"Bearbeiten": [{"label": "Circle", "disabled": False, "hint": None}]}
    assert [f.where for f in audit.compare_german("composes", english, german)] == ["Edit ▸ Circle"]
