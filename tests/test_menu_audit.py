"""The menu audit's comparison (``scripts/menu_audit.py``): small menus made up here, no browser, no workbook file."""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import menu_audit as audit  # noqa: E402
from menu_audit import App, Entry, Row  # noqa: E402


def row(number: int, menu: str, entry: str, *, groups=None, shortcut="Ctrl+K", action=None, today=None) -> Row:
    return Row(
        number=number,
        menu=menu,
        path=tuple(p.strip() for p in entry.split("▸")),
        groups=groups or {"composes": 1},
        shortcuts=dict.fromkeys(audit.PLATFORMS, shortcut) | {"macOS": audit.mac_shortcut(shortcut)},
        today_labels=audit.today_labels(today),
        today_action=action,
    )


def entry(menu: str, path: str, *, group=1, position=0, shortcut=None, action=None, **flags) -> Entry:
    return Entry(menu, tuple(path.split(" ▸ ")), group, position, shortcut, action, **flags)


def app(desktop: list[Entry], web: list[Entry], viewer: list[Entry] | None = None) -> App:
    return App("composes", desktop, web, {"editor": web, "viewer": web if viewer is None else viewer})


def kinds(found) -> list[str]:
    return [f.kind for f in found]


class TestNormalising:
    def test_shortcuts_are_written_as_the_web_menus_show_them(self):
        assert audit.normal_shortcut("Shift+Alt+Up") == "Shift+Alt+↑"
        assert audit.normal_shortcut("n/a") is None
        assert audit.normal_shortcut(None) is None

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

    def test_the_macos_form_of_a_ctrl_alt_shortcut(self):
        assert audit.mac_shortcut("Ctrl+Alt+N") == "Cmd+Option+N"


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
        assert [(e.path, e.group, e.sealed) for e in audit.web_entries(captured)] == [
            (("Undo",), 1, False),
            (("Row",), 2, True),
            (("Paste As",), 2, False),
            (("Paste As", "Plain Text"), 1, False),
        ]

    def test_style_names_are_left_out_but_an_entry_with_a_shortcut_stays(self):
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
        desktop = [entry("Help", "About Claudia Composes", shortcut="Ctrl+Shift+F1", action="help.about")]
        web = [entry("Help", "About claudia", shortcut="Ctrl+Shift+F1")]
        assert app(desktop, web).twin[0] is web[0]

    def test_an_entry_inside_a_greyed_submenu_pairs_with_the_submenu(self):
        desktop = [entry("Tools", "Row ▸ Delete", action="edit.row-delete")]
        web = [entry("Tools", "Row", disabled=True, submenu=True, sealed=True)]
        assert app(desktop, web).twin[0] is web[0]


class TestOneRow:
    def test_an_entry_in_another_menu_with_other_words_and_another_shortcut(self):
        desktop = [entry("Edit", "Search & Replace…", shortcut="Ctrl+F", action="edit.search-replace")]
        web = [entry("Edit", "Search & Replace…", shortcut="Ctrl+F")]
        wanted = row(70, "Tools", "Search and replace…", shortcut="Ctrl+H", action="edit.search-replace")
        assert kinds(audit.compare_row(app(desktop, web), wanted)) == ["Wrong menu", "Label", "Shortcut"]

    def test_capitalisation_only(self):
        both = [entry("Edit", "Rename Sheet…", shortcut="Ctrl+K", action="edit.rename-sheet")]
        wanted = row(20, "Edit", "Rename sheet…", action="edit.rename-sheet")
        assert kinds(audit.compare_row(app(both, list(both)), wanted)) == ["Label: capitalisation only"]

    def test_a_new_entry_that_exists_nowhere_is_not_built_yet(self):
        found = list(audit.compare_row(app([], []), row(59, "View", "Quiet mode (switch)")))
        assert kinds(found) == ["Not built yet"]
        assert not found[0].decide

    def test_a_new_entry_found_by_its_words_is_not_new(self):
        web = [entry("Insert", "Table…", shortcut="Ctrl+Shift+F")]
        found = audit.compare_row(app([], web), row(27, "Insert", "Table", shortcut="Ctrl+Shift+Alt+T"))
        assert kinds(found) == ["Label", "Shortcut"]  # the dialog's "…" is part of the words

    def test_another_shortcut_on_one_platform_asks_for_a_decision(self):
        wanted = row(1, "File", "New")
        wanted.shortcuts["Windows"] = "Ctrl+N"
        both = [entry("File", "New", shortcut="Ctrl+K", action="file.new")]
        found = [f for f in audit.compare_row(app(both, list(both)), wanted) if f.kind == "Shortcut per platform"]
        assert found and found[0].decide


class TestWholeApp:
    def test_an_entry_no_row_places_is_not_in_the_workbook_unless_its_notes_drop_it(self):
        desktop = [
            entry("Edit", "Go to Target", action="edit.go-to-target"),
            entry("File", "Save", position=1, action="file.save"),
        ]
        texts = [("Menus", "Next: rename, and drop the old Save action (file.save) in the manifest and the menus.")]
        found = list(audit.compare_extras(app(desktop, list(desktop)), [], texts))
        assert [(f.kind, f.next_step) for f in found] == [
            ("Not in the workbook", "add a row, or remove"),
            ("Not in the workbook", "the workbook's notes drop it: confirm"),
        ]
        assert "(file.save)" in found[1].workbook

    def test_an_entry_the_workbook_gives_another_app_is_to_remove_here(self):
        desktop = [entry("Insert", "Table of Contents", action="insert.contents")]
        rows = [row(24, "Insert", "Table of contents", groups={"computes": 1}, action="insert.contents")]
        assert kinds(audit.compare_extras(app(desktop, list(desktop)), rows, [])) == [
            "To remove (the workbook drops it in this app)"
        ]

    def test_web_and_desktop_differ_in_words_presence_and_order(self):
        desktop = [
            entry("Tools", "Pivot Fields", position=0, action="tools.pivot-fields"),
            entry("Tools", "Value Field Settings…", position=1, action="tools.pivot-value"),
        ]
        web = [
            entry("Tools", "Value Field Settings…", position=0),
            entry("Tools", "Pivot Fields", position=1),
            entry("Edit", "Circle", position=2),
        ]
        found = list(audit.compare_clients(app(desktop, web)))
        assert [f.where for f in found] == ["Edit ▸ Circle", "Tools (order or separators)"]

    def test_the_owners_entries_greyed_for_a_viewer_and_the_viewers_editing_entries_that_are_not(self):
        owner = [entry("Edit", "Cut"), entry("Format", "Colours…", position=1)]
        viewer = [entry("Edit", "Cut", disabled=True), entry("Format", "Colours…", position=1)]
        one = app([], owner, viewer)
        assert [f.where for f in audit.compare_roles(one)] == ["Edit ▸ Cut"]
        assert [f.where for f in audit.viewer_can_use(one)] == ["Format ▸ Colours…"]


class TestWorkbook:
    def test_rows_written_after_their_menu_ended_are_found(self):
        rows = [row(1, "File", "New"), row(2, "View", "Dark mode"), row(3, "Help", "About"), row(4, "View", "Back")]
        assert audit.rows_out_of_order(rows) == {4}

    def test_a_shortcut_the_workbook_gives_twice_or_that_an_unlisted_entry_has_is_a_clash(self):
        rows = [row(31, "Insert", "Shape ▸ Rectangle", shortcut="Ctrl+Shift+Alt+R")]
        desktop = [
            entry("File", "Manage ▸ Delete From Server…", shortcut="Ctrl+Shift+Alt+R", action="file.manage.delete")
        ]
        found = list(audit.workbook_clashes(rows, [app(desktop, list(desktop))], {}, []))
        assert [(f.kind, f.where) for f in found] == [("Workbook: shortcut clash", "Ctrl+Shift+Alt+R")]

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
        assert (only.path, only.groups, only.shortcuts["macOS"], only.today_action) == (
            ("Save checkpoint…",),
            {"computes": 2, "composes": 2},
            "Cmd+S",
            "file.save-as",
        )


class TestContextMenus:
    def test_a_popover_that_calls_itself_a_menu_is_read_as_one(self):
        assert audit.context_items("no menu; opened instead: Row menu: Insert Row Above / Delete Rows") == [
            "Insert Row Above",
            "Delete Rows",
        ]
        assert audit.context_items("no menu; opened instead: Zeilenmenü: Zeile löschen") == ["Zeile löschen"]
        assert audit.context_items("nothing opened") is None

    def test_missing_and_extra_entries_of_a_context_menu(self):
        got = {"label": "Object menu", "items": [{"label": "Delete"}, {"sep": True}, {"label": "Edit text"}]}
        found = list(audit._compare_context("composes", "object", ["Delete", "Copy"], got))
        assert [(f.kind, f.next_step) for f in found] == [
            ("Context menu: missing entries", "add Copy"),
            ("Context menu: not in the workbook", "add rows for Edit text, or drop them"),
        ]


@pytest.mark.parametrize("label", ["Format", "Agenda"])
def test_words_that_are_the_same_in_german_are_not_untranslated(label):
    english = {"Insert": [{"label": label, "disabled": False, "hint": None}]}
    assert list(audit.compare_german("creates", english, english, set())) == []


def test_an_untranslated_entry_is_found_but_not_a_shapes_name():
    english = {"Edit": [{"label": "Circle", "hint": None}, {"label": "Image…", "hint": "Ctrl+Alt+I"}]}
    german = {"Bearbeiten": [{"label": "Circle", "hint": None}, {"label": "Image…", "hint": "Ctrl+Alt+I"}]}
    assert [f.where for f in audit.compare_german("composes", english, german, {"Circle"})] == ["Edit ▸ Image…"]


def test_the_built_in_shapes_are_read_from_the_creates_package():
    assert {"Circle", "Rectangle", "Triangle"} <= audit.builtin_shape_names()


class TestAfterTheOwnersAnswers:
    def test_renamed_context_entries_pair_up_by_their_words(self):
        renames = audit._pair_renames(
            ["Row above", "Remove row", "Name & describe…"], ["Insert Row Above", "Delete Rows"]
        )
        assert renames == {"Insert Row Above": "Row above", "Delete Rows": "Remove row"}

    def test_a_platform_marked_na_is_not_compared(self):
        quit_row = Row(
            99,
            "File",
            ("Quit",),
            {"composes": 6},
            {"Web": None, "Linux": "Ctrl+Q", "Windows": "Ctrl+Q", "macOS": None},
            {},
            "file.quit",
            frozenset({"Web", "macOS"}),
        )
        desktop = [entry("File", "Quit", shortcut="Ctrl+Q", action="file.quit")]
        assert kinds(audit.compare_row(app(desktop, []), quit_row)) == []

    def test_an_entry_the_context_menus_sheet_takes_moves_there(self):
        desktop = [entry("Tools", "Pivot Fields", action="tools.pivot-fields")]
        found = list(audit.compare_extras(app(desktop, list(desktop)), [], [], {"Pivot Fields": "Pivot table"}))
        assert [(f.kind, f.workbook) for f in found] == [("Moves to a context menu", "context menu: Pivot table")]

    def test_the_owners_answers_stay_on_a_rerun(self):
        book = openpyxl.Workbook()
        found = [audit.Finding("Question", "all", "built-in names in German")]
        audit.write_sheet(book, found, "made here")
        book[audit.SHEET]["K2"], book[audit.SHEET]["L2"] = "ok", "Q6"
        audit.write_sheet(book, [*found, audit.Finding("Label", "composes", "File ▸ New")], "made again")
        rows = list(book[audit.SHEET].iter_rows(min_row=2, max_row=3, values_only=True))
        assert [(r[1], r[10], r[11]) for r in rows] == [("Question", "ok", "Q6"), ("Label", None, None)]
