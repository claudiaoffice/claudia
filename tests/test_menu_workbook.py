"""The menu definition is what the workbook says (D1605): every app's menus, in the workbook's order and groups, with
the workbook's words, its keys on every platform and its "Fits when" rule, word for word (D1646).

The workbook (``claudiaoffice-log/notes/claudia-menus.xlsx``) is the owner's; the definition
(``clients/contract/src/claudia_menus/manifest.py``, D1643) is what every client builds its menus from. Words are
compared as D1609 and D1618 say: the capitalisation and a dialog's "…" are the definition's, the words are the
workbook's.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "clients" / "contract" / "src"))

from claudia_menus import manifest  # noqa: E402
from generate_menus import shown  # noqa: E402
from menu_audit import APPS, WORKBOOK, Row, clean_label, mac_shortcut, normal_shortcut, workbook_rows  # noqa: E402

PLATFORMS = ("Web", "Linux", "Windows", "macOS")
MENUS = ("File", "Edit", "Insert", "Format", "View", "Tools", "Preferences", "Help")
#: Built by the macOS client from the other menus (D1616, ``clients/neutralino/src/platform/macos-menu.ts``) and
#: checked by its tests: no entry of the definition of its own.
MAC_APP_MENU = "App menu (macOS)"
#: Quit leaves File on macOS for the app menu, so the workbook gives it no key there (D1616).
MAC_LEAVES_FILE = {"file.quit"}
#: Entries the workbook has and the app cannot do yet: they come with their feature (the Diagnosis sheet, "Not built
#: yet" and "Not in this app yet"). Only ever shrinks: the test below fails when one of them is in the definition.
NOT_BUILT_YET = {
    *((app, f"Edit ▸ Select {which} object") for app in APPS for which in ("next", "previous")),
    *(("computes", f"Insert ▸ Shape ▸ {shape}") for shape in ("Circle", "Rectangle", "Triangle")),
    ("computes", "Insert ▸ Text box"),
    ("composes", "Insert ▸ New page"),
    ("composes", "Insert ▸ Citation…"),
    *((app, f"View ▸ {view}") for app in APPS for view in ("Quiet mode (switch)", "Corkboard", "Scrapbook")),
    ("composes", "Tools ▸ Bibliography…"),
    ("composes", "Tools ▸ Names…"),
    ("creates", "Tools ▸ Names…"),
}


@dataclass(frozen=True)
class Place:
    """An entry as the workbook and the definition can both say it: ``menu`` is a menu, or a thing's context menu."""

    menu: str
    words: tuple[str, ...]
    group: int
    keys: tuple[str | None, ...]
    fits: str

    def __str__(self) -> str:
        keys = " ".join(f"{p}={k}" for p, k in zip(PLATFORMS, self.keys, strict=True))
        return f"{self.menu} ▸ {' ▸ '.join(self.words)} (group {self.group}) [{keys}] fits: {self.fits}"


def words(label: str) -> str:
    """The words of a label: not its capitalisation (D1609), not a dialog's "…" or "?" (D1618), not "(switch)"."""
    return re.sub(r"[\s…?]+$", "", clean_label(label).replace("…", "")).casefold()


def _ranked(places: list[tuple[str, tuple[str, ...], int, tuple[str | None, ...], str]]) -> list[Place]:
    """Groups as their rank inside their menu: the workbook numbers them with gaps where an entry is not built yet."""
    ranks = {menu: sorted({group for m, _, group, _, _ in places if m == menu}) for menu, *_ in places}
    return [Place(menu, path, ranks[menu].index(group) + 1, keys, fits) for menu, path, group, keys, fits in places]


def workbook_places(rows: list[Row], app: str) -> list[Place]:
    """What the workbook asks of ``app``, in menu order and, inside a menu, in group and row order."""
    wanted = []
    for row in rows:
        target = f"{row.menu} ▸ {' ▸ '.join(row.path)}"
        if app not in row.groups or row.menu == MAC_APP_MENU or (app, target) in NOT_BUILT_YET:
            continue
        keys = tuple("n/a" if p in row.absent else row.shortcuts[p] for p in PLATFORMS)
        if row.path[-1].endswith("(one entry per language)"):
            wanted += [
                (row.menu, (*map(words, row.path[:-1]), words(name)), row.groups[app], keys, row.fits)
                for _, name in manifest.LANGUAGES
            ]
        else:
            wanted.append((row.menu, tuple(map(words, row.path)), row.groups[app], keys, row.fits))
    wanted.sort(key=lambda place: (MENUS.index(place[0]), place[2]))  # stable: rows keep their order in a group
    return _ranked(wanted)


def _mac(accelerator: str) -> str | None:
    """A macOS key of its own (``Keys.macos``), as the workbook writes it: ``<Primary>`` is Cmd, ``<Control>`` is Ctrl,
    Alt is Option, in the order Cmd, Ctrl, Shift, Option."""
    rest = mac_shortcut(normal_shortcut(shown(accelerator.replace("<Control>", ""))))
    if "<Control>" not in accelerator or rest is None:
        return rest
    if rest.startswith("Cmd+"):
        return rest.replace("Cmd+", "Cmd+Ctrl+", 1)
    return f"Ctrl+{rest}"


def _keys(action: manifest.Action) -> tuple[str | None, ...]:
    default = normal_shortcut(shown(action.keys.default)) if action.keys.default else None
    mac = _mac(action.keys.macos) if action.keys.macos else mac_shortcut(default)
    web = "n/a" if "client: desktop only" in action.fits else default
    return (web, default, default, "n/a" if action.id in MAC_LEAVES_FILE else mac)


def definition_places(app: str) -> list[Place]:
    """What the definition gives ``app``, in its order."""
    found = []
    for menu in manifest.for_app(app).menus:
        for group, section in enumerate(menu.sections, start=1):
            for entry in section:
                if isinstance(entry, manifest.Submenu):
                    for action in entry.items:
                        path = (words(entry.label), words(action.label))
                        found.append((menu.label, path, group, _keys(action), action.fits))
                else:
                    found.append((menu.label, (words(entry.label),), group, _keys(entry), entry.fits))
    return _ranked(found)


#: The workbook's contexts by the id the definition gives them (``ContextMenu.id``).
CONTEXTS = {
    "Object (image, text box, shape, container, chart)": "object",
    "Cell (range)": "cell",
    "Paragraph (in composes, or in a text box)": "paragraph",
    "Table": "table",
    "List (in a text box, or in composes)": "list",
    "Section header (composes)": "heading",
    "Sheet tab / slide tab": "tab",
    "Slide (creates)": "slide",
    "Row header (computes, and tables in composes)": "row-header",
    "Column header (computes, and tables in composes)": "column-header",
    "Object (chart, on a sheet)": "chart",
    "Pivot table (computes)": "pivot",
    "Reference (in the text or in a text box)": "reference",
}
#: Context entries of a feature that is not built yet in that app (Context menus sheet, "Status"). Only shrinks.
CONTEXT_NOT_BUILT_YET: set[tuple[str, str, str]] = set()


def workbook_contexts(app: str) -> list[Place]:
    """The Context menus sheet for ``app``, in the sheet's order of contexts and, inside one, of groups and rows. A
    submenu the workbook names by itself (``Sort ▸``) is compared by its name and rule; its items have no row."""
    sheet = openpyxl.load_workbook(WORKBOOK, read_only=True)["Context menus"]
    header = [str(cell.value) for cell in next(sheet.iter_rows(max_row=1))]
    col = {name: n for n, name in enumerate(header)}
    found = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if not values[col["#"]] or values[col[app]] in (None, ""):
            continue
        context, entry = CONTEXTS[str(values[col["Context"]])], str(values[col["Entry"]])
        if (app, context, entry) in CONTEXT_NOT_BUILT_YET:
            continue
        path = tuple(words(part) for part in entry.split("▸") if part.strip())
        whole_submenu = entry.rstrip().endswith("▸")
        keys = (None,) * 4 if whole_submenu else tuple(normal_shortcut(values[col[p]]) for p in PLATFORMS)
        found.append((context, path, int(str(values[col[app]])), keys, str(values[col["Fits when"]] or "")))
    order = list(dict.fromkeys(place[0] for place in found))
    found.sort(key=lambda place: (order.index(place[0]), place[2]))
    return _ranked(found)


def definition_contexts(app: str, wanted: list[Place]) -> list[Place]:
    """The definition's context menus of ``app``, in the workbook's order of contexts (its own order is free). A
    submenu whose items the workbook does not list is one entry, with its first item's rule."""
    named = {(p.menu, p.words) for p in wanted}
    found = []
    for menu in manifest.for_app(app).context_menus:
        for group, section in enumerate(menu.sections, start=1):
            for entry in section:
                if isinstance(entry, manifest.Submenu) and (menu.id, (words(entry.label),)) in named:
                    found.append((menu.id, (words(entry.label),), group, (None,) * 4, entry.items[0].fits))
                elif isinstance(entry, manifest.Submenu):
                    for action in entry.items:
                        path = (words(entry.label), words(action.label))
                        found.append((menu.id, path, group, _keys(action), action.fits))
                else:
                    found.append((menu.id, (words(entry.label),), group, _keys(entry), entry.fits))
    order = list(dict.fromkeys([*(p.menu for p in wanted), *(place[0] for place in found)]))
    found.sort(key=lambda place: order.index(place[0]))
    return _ranked(found)


@pytest.fixture(scope="module")
def rows() -> list[Row]:
    return workbook_rows(openpyxl.load_workbook(WORKBOOK, read_only=True)["Menus"])


@pytest.mark.must_not_break("E5.23")
@pytest.mark.parametrize("app", APPS)
def test_the_menus_are_what_the_workbook_says(app: str, rows: list[Row]) -> None:
    """The key risk of the menu rebuild (E5.23): a client whose menus are not what the owner decided in the workbook."""
    wanted, have = workbook_places(rows, app), definition_places(app)
    missing = [str(p) for p in wanted if p not in have]
    extra = [str(p) for p in have if p not in wanted]
    assert not missing and not extra, (
        f"{app}: the definition differs from the workbook\n  missing or different:\n    "
        + "\n    ".join(missing)
        + "\n  not in the workbook, or different:\n    "
        + "\n    ".join(extra)
    )
    assert have == wanted, f"{app}: the same entries, in another order or grouping"


def test_what_is_not_built_yet_is_not_in_the_definition_either(rows: list[Row]) -> None:
    """The list only shrinks: an entry that comes with its feature leaves it in the same commit."""
    built = {(app, f"{p.menu} ▸ {' ▸ '.join(p.words)}") for app in APPS for p in definition_places(app)}
    listed = {(app, f"{row.menu} ▸ {' ▸ '.join(map(words, row.path))}") for row in rows for app in APPS}
    for app, target in NOT_BUILT_YET:
        menu, *path = target.split(" ▸ ")
        key = (app, f"{menu} ▸ {' ▸ '.join(map(words, path))}")
        assert key in listed, f"{target} ({app}) is not a row of the workbook"
        assert key not in built, f"{target} is built in {app} now: take it out of NOT_BUILT_YET"


@pytest.mark.parametrize("app", APPS)
def test_the_context_menus_are_what_the_workbook_says(app: str) -> None:
    """D1602, D1612, D1619: every thing's context menu, as the Context menus sheet has it."""
    wanted = workbook_contexts(app)
    have = definition_contexts(app, wanted)
    missing = [str(p) for p in wanted if p not in have]
    extra = [str(p) for p in have if p not in wanted]
    assert not missing and not extra, (
        f"{app}: the context menus differ from the workbook\n  missing or different:\n    "
        + "\n    ".join(missing)
        + "\n  not in the workbook, or different:\n    "
        + "\n    ".join(extra)
    )
    assert have == wanted, f"{app}: the same context entries, in another order or grouping"
