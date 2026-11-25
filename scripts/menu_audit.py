"""Compare the menu workbook with the menus the apps have today, and write what differs into the workbook (menu audit).

``uv run python scripts/menu_capture.py``  first: what the web client shows (``.claudia/menu-audit/web.json``)
``uv run python scripts/menu_audit.py``    then: the comparison, written to the "Diagnosis" sheet of
                                           ``claudiaoffice-log/notes/claudia-menus.xlsx`` (the sheet is replaced)
``uv run python scripts/menu_audit.py --dry-run``  the counts only; the workbook is not touched

Three sources, per app (coding standards §12: menus come from the workbook):

* the **workbook** (sheets "Menus" and "Context menus"): the target. A row names the action it replaces by today's id
  ("Today's action id"), or none for an entry that does not exist yet.
* the **manifest** (``clients/linux/src/claudia_shell_gtk/manifest.py``): what the desktop clients show. The Linux
  client builds its menus from it, the Windows and macOS clients from the menus generated from it.
* the **web capture** (``menu_capture.py``): what a person sees in the browser, per role and in German. Its keys:
  ``owner``, ``editor``, ``viewer`` and ``owner (de)`` hold the menu bars, ``contexts (<role>)`` and
  ``contexts (owner, de)`` the context menus by place.

Each difference becomes one row (a finding): its kind, what the workbook says, what web and desktop do today, the next
step, and whether it needs the owner's decision or is only work to do. "Shortcut" is the glossary's word for what the
workbook's columns call a key.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openpyxl.workbook.workbook import Workbook
    from openpyxl.worksheet.worksheet import Worksheet

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "claudiaoffice-log" / "notes" / "claudia-menus.xlsx"
WEB = ROOT / ".claudia" / "menu-audit" / "web.json"
SHAPES = ROOT / "packages" / "claudia-creates" / "src" / "claudia_creates" / "builtin_shapes"
SHEET = "Diagnosis"
APPS = ("computes", "composes", "creates")
ROLES = ("editor", "viewer")
PLATFORMS = ("Web", "Linux", "Windows", "macOS")
ARROW = " ▸ "

#: Kinds of finding, in the order the sheet lists them, and whether each needs the owner's decision.
KINDS: dict[str, bool] = {
    "Open in the workbook": True,
    "Question": True,
    "Workbook: capitalisation rule": True,
    "Workbook: shortcut clash": True,
    "Workbook: row out of menu order": True,
    "Not in the workbook": True,
    "Only in the web menu": True,
    "Context menu: not in the workbook": True,
    "Shortcut per platform": True,
    "Wrong menu": False,
    "Label": False,
    "Label: capitalisation only": False,
    "Shortcut": False,
    "Order or separators": False,
    "Not in this app yet": False,
    "Not built yet": False,
    "To remove (the workbook drops it in this app)": False,
    "Moves to a context menu": False,
    "Web and desktop differ": False,
    "Context menu: missing entries": False,
    "Not translated": False,
    "Greyed for a role": False,
    "Usable by a viewer: check": False,
    "Not checked": False,
}

#: Entries that are app-wide settings rather than actions of a document (one per language)
LANGUAGE_IDS = "config.language."
#: Differences between web and desktop that a decision made on purpose, by action id
BY_DESIGN = {
    "file.quit": "by design: a browser tab has no Quit",
    "format.apply-style": "by design: a flyout of the styles on the web, the page's popover in a shell (D301)",
}
#: Submenus whose entries are the document's (style names), not the app's: only entries with a shortcut are kept
DOCUMENT_SUBMENUS = {"Apply Style", "Format anwenden"}
#: Entries a viewer may use because they change nothing (anything else in Edit, Insert, Format is checked)
READ_ONLY = {"Copy", "Search & Replace…", "Go to Target", "Reference in Chat"}


def _join(menu: str, path: tuple[str, ...]) -> str:
    return ARROW.join((menu, *path))


@dataclass(frozen=True)
class Entry:
    """One menu entry where it is today: its top menu, the labels down to it, its separator group and its shortcut.

    ``submenu`` marks the entry that opens a submenu; ``sealed`` one whose submenu could not be read (it is greyed)."""

    menu: str
    path: tuple[str, ...]
    group: int
    position: int
    shortcut: str | None = None
    action: str | None = None
    disabled: bool = False
    submenu: bool = False
    sealed: bool = False

    @property
    def place(self) -> str:
        """The menu and submenu it is in: ``Edit ▸ Paste As``."""
        return _join(self.menu, self.path[:-1])

    @property
    def label(self) -> str:
        """Its own words."""
        return self.path[-1]

    def shown(self) -> str:
        """Where it is and its shortcut, for a person: ``Edit ▸ Copy [Ctrl+C]``."""
        shortcut = f" [{self.shortcut}]" if self.shortcut else ""
        return _join(self.menu, self.path) + shortcut


@dataclass(frozen=True)
class Row:
    """One row of the workbook's "Menus" sheet."""

    number: int
    menu: str
    path: tuple[str, ...]
    groups: dict[str, int]
    shortcuts: dict[str, str | None]
    today_labels: dict[str, str]
    today_action: str | None
    absent: frozenset[str] = frozenset()
    """The platforms the workbook marks n/a: the entry is not there at all (Quit on the web)."""

    @property
    def target(self) -> str:
        """Where the workbook puts it: ``Insert ▸ Image…``."""
        return _join(self.menu, self.path)

    @property
    def place(self) -> str:
        """The menu and submenu the workbook puts it in."""
        return _join(self.menu, self.path[:-1])

    @property
    def label(self) -> str:
        """Its words in the workbook, without notes such as "(switch)"."""
        return clean_label(self.path[-1])


@dataclass
class Finding:
    """One difference: a row of the Diagnosis sheet."""

    kind: str
    app: str
    where: str
    workbook: str = ""
    web: str = ""
    desktop: str = ""
    next_step: str = ""
    row: int | None = None
    decide: bool = field(init=False)

    def __post_init__(self) -> None:
        self.decide = KINDS[self.kind]


# --- normalising -------------------------------------------------------------------------------------------------

_KEY_WORDS = {"Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "Delete": "Del", "Return": "Enter"}


def normal_shortcut(shortcut: object) -> str | None:
    """A shortcut as the web menus show it, so the workbook's ``Shift+Alt+Up`` and the menu's ``Shift+Alt+↑`` agree."""
    text = str(shortcut).strip() if shortcut is not None else ""
    if text in {"", "None", "n/a"}:
        return None
    return "+".join(_KEY_WORDS.get(part, part) for part in text.replace(" ", "").split("+"))


def clean_label(label: str) -> str:
    """The words of a workbook entry without its notes: ``Dark mode (switch)`` is the entry ``Dark mode``."""
    return re.sub(r"\s*\((switch|one entry per language)\)\s*$", "", label).strip()


def same_words(a: str, b: str) -> bool:
    """Two labels for the same entry, whatever their capitalisation, closing ``…`` and submenu arrow: Table, Table…"""

    def bare(label: str) -> str:
        return re.sub(r"[\s…?.▸]+$", "", clean_label(label)).casefold()

    return bare(a) == bare(b)


def compare_labels(want: str, have: str) -> str | None:
    """``None`` when they agree, ``"case"`` when only the capitalisation differs, ``"words"`` otherwise."""
    want, have = clean_label(want), clean_label(have)
    if want == have:
        return None
    return "case" if want.casefold() == have.casefold() else "words"


def mac_shortcut(shortcut: str | None) -> str | None:
    """The macOS form of a shortcut as the one-shortcut manifest gives it there: Ctrl is Cmd, Alt is Option."""
    if shortcut is None:
        return None
    return "+".join({"Ctrl": "Cmd", "Alt": "Option"}.get(part, part) for part in shortcut.split("+"))


def today_labels(cell: object) -> dict[str, str]:
    """``computes: X / creates: Y`` per app, or the one label for every app."""
    if not cell:
        return {}
    parts = [part.strip() for part in str(cell).split(" / ")]
    if all(re.match(r"^(computes|composes|creates): ", part) for part in parts):
        pairs = (part.split(": ", 1) for part in parts)
        return {pair[0]: pair[1] for pair in pairs}
    return dict.fromkeys(APPS, str(cell).strip())


# --- reading -------------------------------------------------------------------------------------------------------


def columns(sheet: Worksheet) -> dict[str, int]:
    """Column index by header, so a column the owner inserts does not shift the others."""
    return {str(cell.value): n for n, cell in enumerate(sheet[1]) if cell.value}


def _marked(value: object) -> bool:
    """An app column of the workbook says the entry is in that app."""
    return value not in (None, "")


def workbook_rows(sheet: Worksheet) -> list[Row]:
    """The "Menus" sheet as rows."""
    col = columns(sheet)
    rows = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if not values[col["#"]] or not values[col["Menu"]]:
            continue
        rows.append(
            Row(
                number=int(str(values[col["#"]])),
                menu=str(values[col["Menu"]]),
                path=tuple(part.strip() for part in str(values[col["Entry"]]).split("▸")),
                groups={app: int(str(values[col[app]])) for app in APPS if _marked(values[col[app]])},
                shortcuts={platform: normal_shortcut(values[col[platform]]) for platform in PLATFORMS},
                absent=frozenset(p for p in PLATFORMS if str(values[col[p]]).strip() == "n/a"),
                today_labels=today_labels(values[col["Today's label"]]),
                today_action=str(values[col["Today's action id"]] or "") or None,
            )
        )
    return rows


def workbook_texts(workbook: Workbook) -> list[tuple[str, str]]:
    """Every longer text of the workbook's sheets but the diagnosis, as (sheet, text): where a removal is explained."""
    return [
        (sheet.title, value)
        for sheet in workbook
        if sheet.title != SHEET
        for row in sheet.iter_rows(values_only=True)
        for value in row
        if isinstance(value, str) and not value.startswith("=") and len(value) > 30
    ]


def manifest_entries(app: str) -> list[Entry]:
    """The desktop clients' menus of ``app``, from the manifest, with shortcuts as the web menus write them."""
    for folder in (ROOT / "scripts", ROOT / "clients" / "linux" / "src"):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    from claudia_shell_gtk import manifest  # pure data, no GTK (its own docstring says so)
    from generate_keys import shown  # the web menus' own notation of a GTK accelerator

    entries: list[Entry] = []
    for menu in manifest.for_app(app).menus:
        for group, section in enumerate(menu.sections, start=1):
            for item in section:
                inside = item.items if isinstance(item, manifest.Submenu) else (item,)
                above = (item.label,) if isinstance(item, manifest.Submenu) else ()
                for action in inside:
                    entries.append(
                        Entry(
                            menu=menu.label,
                            path=(*above, action.label),
                            group=1 if above else group,
                            position=len(entries),
                            shortcut=shown(action.accelerators[0]) if action.accelerators else None,
                            action=action.id,
                        )
                    )
    return entries


def web_entries(menus: dict[str, list[dict[str, Any]]]) -> list[Entry]:
    """The menus of a capture of the web client, as entries: a submenu as an entry of its own, then its entries."""
    entries: list[Entry] = []
    for menu, items in menus.items():
        entries.extend(_web_items(menu, (), items, len(entries) * 100))
    return entries


def _web_items(menu: str, above: tuple[str, ...], items: list[dict[str, Any]], at: int) -> Iterator[Entry]:
    group = 1
    for n, item in enumerate(items):
        if item.get("sep"):
            group += 1
            continue
        children = item.get("items")
        submenu = bool(item.get("sub"))
        yield Entry(
            menu=menu,
            path=(*above, item["label"]),
            group=group,
            position=at + n if above else at + n * 100,
            shortcut=item.get("hint"),
            disabled=bool(item.get("disabled")),
            submenu=submenu,
            sealed=submenu and not isinstance(children, list),
        )
        if isinstance(children, list):
            kept = [c for c in children if c.get("sep") or c.get("hint") or item["label"] not in DOCUMENT_SUBMENUS]
            yield from _web_items(menu, (*above, item["label"]), kept, at + n * 100 + 1)


def builtin_shape_names() -> set[str]:
    """The names of the shapes every new document's library starts with: document data, like style names."""
    return {json.loads(path.read_text(encoding="utf-8"))["name"] for path in SHAPES.glob("*.json")}


# --- one app -------------------------------------------------------------------------------------------------------


@dataclass
class App:
    """One app's menus today, on the desktop (manifest) and on the web, with each desktop entry paired with its web
    twin: the same place and words, else the one entry left in the same (sub)menu, else the one entry anywhere with the
    same words. A desktop entry inside a web submenu that is greyed (and so could not be read) pairs with that submenu.
    """

    name: str
    desktop: list[Entry]
    web: list[Entry]
    web_by_role: dict[str, list[Entry]]
    twin: dict[int, Entry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        taken: set[int] = set()
        for rule in (self._same_place_and_words, self._last_in_place, self._same_words_anywhere, self._sealed_parent):
            for n, entry in enumerate(self.desktop):
                if n not in self.twin:
                    found = rule(entry, [w for w in self.web if id(w) not in taken])
                    if found is not None:
                        self.twin[n] = found
                        if not found.sealed:  # a sealed submenu stands in for all the entries inside it
                            taken.add(id(found))

    @staticmethod
    def _same_place_and_words(entry: Entry, free: list[Entry]) -> Entry | None:
        here = entry.place.casefold()
        return next((w for w in free if w.place.casefold() == here and same_words(w.label, entry.label)), None)

    def _last_in_place(self, entry: Entry, free: list[Entry]) -> Entry | None:
        place = entry.place.casefold()
        here = [w for w in free if w.place.casefold() == place and not w.submenu]
        unpaired = [d for n, d in enumerate(self.desktop) if n not in self.twin and d.place.casefold() == place]
        return here[0] if len(here) == 1 and len(unpaired) == 1 else None

    def _same_words_anywhere(self, entry: Entry, free: list[Entry]) -> Entry | None:
        return self._only_one(free, entry.label)

    @staticmethod
    def _sealed_parent(entry: Entry, free: list[Entry]) -> Entry | None:
        return next((w for w in free if w.sealed and (w.menu, *w.path) == (entry.menu, *entry.path[:-1])), None)

    @staticmethod
    def _only_one(entries: list[Entry], label: str | None) -> Entry | None:
        """The one entry (not a submenu) with these words, or None when there is none or several."""
        found = [w for w in entries if label and same_words(w.label, label) and not w.submenu]
        return found[0] if len(found) == 1 else None

    def locate(self, row: Row) -> tuple[Entry | None, Entry | None]:
        """Where a workbook row's entry is today: (desktop, web). By its action id; a row without one (a new entry) by
        its words, so that an entry which exists under another name or in another menu is not called new."""
        for n, entry in enumerate(self.desktop):
            if row.today_action and entry.action == row.today_action:
                return entry, self.twin.get(n)
        web = self._only_one(self.web, row.today_labels.get(self.name)) or self._only_one(self.web, row.path[-1])
        desktop = next((self.desktop[n] for n, w in self.twin.items() if web is not None and w is web), None)
        return desktop, web

    def covered(self, rows: list[Row]) -> set[int]:
        """The ids (``id()``) of the entries, desktop and web, that a workbook row of this app places."""
        located = {id(e) for row in rows if self.name in row.groups for e in self.locate(row) if e}
        twins = {id(self.desktop[n]) for n, w in self.twin.items() if id(w) in located}
        return (
            located
            | twins
            | {id(self.twin[n]) for n, d in enumerate(self.desktop) if id(d) in located and n in self.twin}
        )


# --- one workbook row ------------------------------------------------------------------------------------------------


def compare_row(app: App, row: Row) -> Iterator[Finding]:
    """What differs between one workbook row and the app."""
    if row.menu == "App menu (macOS)":
        yield Finding(
            "Not checked", app.name, row.target, row.target, next_step="needs the macOS client", row=row.number
        )
        return
    desktop, web = app.locate(row)
    if desktop is None and web is None:
        if row.today_action:
            yield Finding(
                "Not in this app yet",
                app.name,
                row.target,
                workbook=row.target,
                web="—",
                desktop="—",
                row=row.number,
                next_step=f"add {row.today_action} to {app.name}",
            )
        else:
            yield Finding(
                "Not built yet",
                app.name,
                row.target,
                workbook=row.target,
                web="—",
                desktop="—",
                row=row.number,
                next_step="build the feature, then the entry",
            )
        return
    readable = web if web is not None and not web.sealed else None
    yield from _place(app, row, desktop, readable, web)
    yield from _label(app, row, desktop, readable, web)
    yield from _shortcuts(app, row, desktop, readable)


def _shown(entry: Entry | None) -> str:
    if entry is None:
        return "—"
    return entry.shown() + (" (greyed submenu, not opened)" if entry.sealed else "")


def _finding(kind: str, app: App, row: Row, desktop: Entry | None, web: Entry | None, next_step: str) -> Finding:
    return Finding(
        kind,
        app.name,
        row.target,
        workbook=row.target,
        web=_shown(web),
        desktop=_shown(desktop),
        next_step=next_step,
        row=row.number,
    )


def _place(app: App, row: Row, desktop: Entry | None, web: Entry | None, raw: Entry | None) -> Iterator[Finding]:
    places = {e.place for e in (desktop, web) if e}
    if any(p.casefold() != row.place.casefold() for p in places):
        yield _finding("Wrong menu", app, row, desktop, raw, f"move to {row.place}")
    elif any(p != row.place for p in places):
        yield _finding("Label: capitalisation only", app, row, desktop, raw, f"submenu written {row.place}")


def _label(app: App, row: Row, desktop: Entry | None, web: Entry | None, raw: Entry | None) -> Iterator[Finding]:
    if "(one entry per language)" in row.path[-1]:
        return
    verdicts = {compare_labels(row.path[-1], e.label) for e in (desktop, web) if e}
    if "words" in verdicts:
        yield _finding("Label", app, row, desktop, raw, f"rename to “{row.label}” (and in the .po files)")
    elif "case" in verdicts:
        yield _finding("Label: capitalisation only", app, row, desktop, raw, f"write it “{row.label}”")


def _shortcuts(app: App, row: Row, desktop: Entry | None, web: Entry | None) -> Iterator[Finding]:
    """The web entry against the workbook's Web column, the desktop entry against its Linux column (the manifest is
    the Linux client's, and the other desktops follow it); a platform marked n/a is not compared."""

    def now(entry: Entry | None) -> str:
        return "—" if entry is None else entry.shortcut or "no shortcut"

    sides = {"Web": web, "Linux": desktop}
    wrong = [p for p, e in sides.items() if e is not None and p not in row.absent and e.shortcut != row.shortcuts[p]]
    if wrong:
        want = " / ".join(f"{p}: {row.shortcuts[p] or 'no shortcut'}" for p in wrong)
        yield Finding(
            "Shortcut",
            app.name,
            row.target,
            workbook=want,
            web=now(web),
            desktop=now(desktop),
            row=row.number,
            next_step="bind the workbook's shortcut"
            if any(row.shortcuts[p] for p in wrong)
            else "none in the workbook (yet)",
        )
    linux, windows, mac = (row.shortcuts[p] for p in ("Linux", "Windows", "macOS"))
    differs = windows != linux and "Windows" not in row.absent
    differs = differs or (mac not in (mac_shortcut(linux), linux) and "macOS" not in row.absent)
    if differs:
        yield Finding(
            "Shortcut per platform",
            app.name,
            row.target,
            workbook=f"Linux {linux} · Windows {windows} · macOS {mac}",
            row=row.number,
            next_step="the manifest gives an entry one shortcut on every platform: allow more?",
        )


# --- one app as a whole ----------------------------------------------------------------------------------------------


def rows_out_of_order(rows: list[Row]) -> set[int]:
    """Rows written after their menu's block had ended (the Read me says rows are in menu order)."""
    seen: list[str] = []
    late = set()
    for row in rows:
        if seen and row.menu != seen[-1] and row.menu in seen:
            late.add(row.number)
        elif not seen or row.menu != seen[-1]:
            seen.append(row.menu)
    return late


def _order_breaks(pairs: list[tuple[int, int, int, int]], top: bool) -> bool:
    """Pairs of (wanted position, wanted group, position, group): out of order, or (in a top menu) other groups."""
    in_order = [p[2] for p in sorted(pairs)] == sorted(p[2] for p in pairs)
    ordered = sorted(pairs)
    grouped = not top or all((a[1] == b[1]) == (a[3] == b[3]) for a, b in zip(ordered, ordered[1:], strict=False))
    return not (in_order and grouped)


def compare_order(app: App, rows: list[Row], late: set[int]) -> Iterator[Finding]:
    """Per menu and submenu: are the entries already in their place in the workbook's order and separator groups?
    (Inside a submenu only the order counts: the workbook's group number is the submenu's own group.)"""
    containers: dict[str, list[tuple[Row, Entry]]] = {}
    for row in rows:
        _desktop, web = app.locate(row)
        if web is None or web.sealed or app.name not in row.groups or row.number in late:
            continue
        if web.place.casefold() == row.place.casefold():
            containers.setdefault(row.place, []).append((row, web))
    for place, pairs in containers.items():
        top = ARROW not in place
        numbers = [(r.number, r.groups[app.name], w.position, w.group) for r, w in pairs]
        if _order_breaks(numbers, top):
            want = " | ".join((f"{r.groups[app.name]}:" if top else "") + r.label for r, _w in pairs)
            have = " | ".join(
                (f"{w.group}:" if top else "") + w.label for _r, w in sorted(pairs, key=lambda p: p[1].position)
            )
            yield Finding(
                "Order or separators",
                app.name,
                place,
                workbook=want,
                web=have,
                next_step="reorder" + (" / regroup (n: = separator group)" if top else ""),
            )


def compare_extras(
    app: App, rows: list[Row], texts: list[tuple[str, str]], in_context: dict[str, list[str]] | None = None
) -> Iterator[Finding]:
    """What the app has that no row of the Menus sheet places in it: moving to a context menu (``in_context``: the
    entries the Context menus sheet gives this app, with their context), dropped, or not in the workbook at all."""
    covered = app.covered(rows)
    actions_anywhere = {r.today_action for r in rows if r.today_action}
    for n, entry in enumerate(app.desktop):
        web = app.twin.get(n)
        if id(entry) in covered or (entry.action or "").startswith(LANGUAGE_IDS) or entry.action in BY_DESIGN:
            continue
        today = f"{entry.shown()} ({entry.action})"
        context = next((c for words, c in (in_context or {}).items() if same_words(words, entry.label)), None)
        if context is not None:
            yield Finding(
                "Moves to a context menu",
                app.name,
                entry.shown(),
                workbook=f"context menu: {context}",
                web=_shown(web),
                desktop=today,
                next_step=f"move into the context menu of: {context}",
            )
            continue
        if entry.action in actions_anywhere:
            yield Finding(
                "To remove (the workbook drops it in this app)",
                app.name,
                entry.shown(),
                workbook="—",
                web=_shown(web),
                desktop=today,
                next_step=f"remove from {app.name}",
            )
            continue
        note = mention(texts, entry)
        yield Finding(
            "Not in the workbook",
            app.name,
            entry.shown(),
            workbook=note or "—",
            web=_shown(web),
            desktop=today,
            next_step="the workbook's notes drop it: confirm" if note else "add a row, or remove",
        )
    paired = {id(w) for w in app.twin.values()}
    for entry in app.web:
        if id(entry) in paired | covered or entry.submenu or entry.path[0] == "App Language":
            continue
        yield Finding(
            "Only in the web menu",
            app.name,
            entry.shown(),
            workbook="—",
            web=entry.shown(),
            desktop="—",
            next_step="an id in the manifest and a workbook row, or remove",
        )


#: Where a note about a removal is most likely the owner's decision, first
_NOTE_ORDER = ("To decide", "Menus", "Context menus", "Keys without entry", "Read me")


def mention(texts: list[tuple[str, str]], entry: Entry) -> str:
    """Where the workbook's notes speak of a removed entry (by its action id or its words), shortened; or ''."""
    words = re.sub(r"[…]+$", "", entry.label)
    by_action = re.compile(rf"(?<![\w.-]){re.escape(entry.action)}(?![\w.-])") if entry.action else None
    by_words = re.compile(rf"(?<!\w){re.escape(words)}(?!\w)", re.IGNORECASE) if len(words) > 4 else None
    ranked = sorted(texts, key=lambda t: _NOTE_ORDER.index(t[0]) if t[0] in _NOTE_ORDER else len(_NOTE_ORDER))
    for sheet, text in ranked:
        hit = (by_action and by_action.search(text)) or (by_words and by_words.search(text))
        if hit:
            start = max(0, hit.start() - 60)
            return f"{sheet}: …{text[start : hit.end() + 80].strip()}…"
    return ""


def compare_clients(app: App) -> Iterator[Finding]:
    """Where the web menu and the desktop menus (the manifest) disagree: an entry only one of them has, or the same
    action at another place, with other words or another shortcut, or in another order."""
    for n, entry in enumerate(app.desktop):
        web = app.twin.get(n)
        if (entry.action or "").startswith(LANGUAGE_IDS) or (web is not None and web.sealed):
            continue
        desktop = f"{entry.shown()} ({entry.action})"
        next_step = BY_DESIGN.get(entry.action or "", "one menu definition")
        if web is None:
            yield Finding(
                "Web and desktop differ",
                app.name,
                entry.shown(),
                web="not in the web menu",
                desktop=desktop,
                next_step=next_step,
            )
        elif (web.place, web.label, web.shortcut) != (entry.place, entry.label, entry.shortcut):
            yield Finding(
                "Web and desktop differ", app.name, entry.shown(), web=web.shown(), desktop=desktop, next_step=next_step
            )
    paired = {id(w) for w in app.twin.values()}
    for entry in app.web:
        if id(entry) not in paired and not entry.submenu and entry.path[0] != "App Language":
            yield Finding(
                "Web and desktop differ",
                app.name,
                entry.shown(),
                web=entry.shown(),
                desktop="not in the desktop menus",
                next_step="one menu definition",
            )
    yield from _client_order(app)


def _client_order(app: App) -> Iterator[Finding]:
    """Per (sub)menu: the paired entries in the same order, and (in a top menu) between the same separators?"""
    containers: dict[str, list[tuple[Entry, Entry]]] = {}
    for n, entry in enumerate(app.desktop):
        web = app.twin.get(n)
        if web is not None and not web.sealed and web.place == entry.place:
            containers.setdefault(entry.place, []).append((entry, web))
    for place, pairs in containers.items():
        numbers = [(d.position, d.group, w.position, w.group) for d, w in pairs]
        if _order_breaks(numbers, ARROW not in place):
            on_desktop = " | ".join(f"{d.group}:{d.label}" for d, _w in pairs)
            on_web = " | ".join(f"{w.group}:{w.label}" for _d, w in sorted(pairs, key=lambda p: p[1].position))
            yield Finding(
                "Web and desktop differ",
                app.name,
                f"{place} (order or separators)",
                web=on_web,
                desktop=on_desktop,
                next_step="one menu definition",
            )


#: Words that are the same in German, or names
_SAME_IN_GERMAN = {"Format", "LaTeX", "Mermaid", "Typst", "English", "Deutsch", "Container", "AI…", "Agenda", "Export…"}


def compare_german(app: str, english: dict[str, Any], german: dict[str, Any], data: set[str]) -> Iterator[Finding]:
    """Entries whose German label is the English one: not translated. The two captures are of the same window, so their
    menus have the same shape and are walked side by side. ``data`` holds the document's names (built-in shapes)."""
    for (title, items), (_german_title, items_de) in zip(english.items(), german.items(), strict=False):
        yield from _german_items(app, (title,), items, items_de, data)


def _german_items(
    app: str, above: tuple[str, ...], items: list[Any], items_de: list[Any], data: set[str]
) -> Iterator[Finding]:
    for item, item_de in zip(items, items_de, strict=False):
        if item.get("sep") or item_de.get("sep"):
            continue
        label, label_de = item["label"], item_de["label"]
        if (above[-1] in DOCUMENT_SUBMENUS and not item.get("hint")) or label in data:
            continue  # a style's or a shape's name is the document's
        if label == label_de and label not in _SAME_IN_GERMAN and re.search("[a-z]", label):
            yield Finding(
                "Not translated",
                app,
                _join(above[0], (*above[1:], label)),
                web=f"the German menu shows “{label_de}”",
                next_step="translate (po/de.po)",
            )
        if isinstance(item.get("items"), list) and isinstance(item_de.get("items"), list):
            yield from _german_items(app, (*above, label), item["items"], item_de["items"], data)


def compare_roles(app: App) -> Iterator[Finding]:
    """Entries the owner can use and an editor or a viewer sees greyed: the input for menus that hide (phase 3).
    Matched by place, not position: a greyed submenu could not be opened for that role, so its entries count as greyed
    with it."""
    for owner in app.web:
        if owner.disabled:
            continue
        greyed = [role for role, entries in app.web_by_role.items() if _greyed_for(owner, entries)]
        if greyed:
            yield Finding(
                "Greyed for a role",
                app.name,
                owner.shown(),
                web=f"greyed for: {', '.join(greyed)}",
                next_step="phase 3: hide, or keep greyed?",
            )


def _greyed_for(owner: Entry, entries: list[Entry]) -> bool:
    places = {(e.menu, e.path): e for e in entries}
    for depth in range(len(owner.path), 0, -1):
        found = places.get((owner.menu, owner.path[:depth]))
        if found is not None:
            return found.disabled
    return False


def viewer_can_use(app: App) -> Iterator[Finding]:
    """Entries of Edit, Insert and Format that a viewer can use, apart from those that only read: does each change
    nothing (a dialog that only shows), or should it be greyed or hidden for her? The reverse of "Greyed for a role"."""
    for entry in app.web_by_role["viewer"]:
        if (
            entry.menu in {"Edit", "Insert", "Format"}
            and not entry.disabled
            and not entry.submenu
            and entry.label not in READ_ONLY
            and entry.path[0] not in DOCUMENT_SUBMENUS
        ):
            yield Finding(
                "Usable by a viewer: check",
                app.name,
                entry.shown(),
                web="enabled for a viewer",
                next_step="does it change the document? then grey or hide it for a viewer",
            )


def sealed_submenus(app: App) -> Iterator[Finding]:
    """Submenus that are greyed for the owner with nothing selected: their entries were not seen on the web."""
    for entry in app.web:
        if entry.sealed:
            yield Finding(
                "Not checked",
                app.name,
                entry.shown(),
                web="greyed submenu, its entries not opened",
                next_step="the capture needs a selection that enables it",
            )


# --- context menus -------------------------------------------------------------------------------------------------

#: Workbook context (column "Context") → the places the capture right-clicked, per app
CONTEXTS: dict[str, dict[str, tuple[str, ...]]] = {
    "Object (image, text box, shape, container, chart)": dict.fromkeys(APPS, ("object",)),
    "Cell (range)": {"computes": ("cell",)},
    "Paragraph (in composes, or in a text box)": {"composes": ("paragraph",)},
    "Table": {"composes": ("table",)},
    "Row header (computes, and tables in composes)": {"computes": ("row header",)},
    "Column header (computes, and tables in composes)": {"computes": ("column header",)},
}


def context_items(got: Any) -> list[str] | None:
    """The labels of a captured context menu; a popover of buttons that calls itself a menu counts as one."""
    if isinstance(got, dict):
        return [i["label"] for i in got["items"] if not i.get("sep")]
    found = re.match(r"no menu; opened instead: [^:]*men(u|ü): (.*)$", str(got))
    return found.group(2).split(" / ") if found else None


def context_entries(sheet: Worksheet) -> dict[str, dict[str, str]]:
    """Per app, the entries the Context menus sheet gives it, by their words and by the words they had where they
    were before ("How it is today": ``Tools ▸ Pivot Fields``), each with its context."""
    col = columns(sheet)
    found: dict[str, dict[str, str]] = {app: {} for app in APPS}
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if not values[col["#"]]:
            continue
        before = str(values[col["How it is today"]] or "")
        words = [str(values[col["Entry"]])] + ([before.split("▸")[-1].strip()] if "▸" in before else [])
        for app in APPS:
            if _marked(values[col[app]]):
                found[app].update(dict.fromkeys(words, str(values[col["Context"]])))
    return found


def compare_contexts(sheet: Worksheet, captured: dict[str, Any]) -> Iterator[Finding]:
    """The workbook's context menus against what a right press opens, as the owner; and the places the capture reached
    that the workbook has no rows for."""
    col = columns(sheet)
    wanted: dict[tuple[str, str], list[str]] = {}
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if values[col["#"]]:
            for app in APPS:
                if _marked(values[col[app]]):
                    wanted.setdefault((str(values[col["Context"]]), app), []).append(str(values[col["Entry"]]))
    checked = set()
    for (context, app), entries in wanted.items():
        places = CONTEXTS.get(context, {}).get(app)
        if places is None:
            yield Finding(
                "Not checked",
                app,
                f"context menu: {context}",
                workbook=", ".join(entries),
                next_step="the capture does not reach this place yet",
            )
            continue
        for place in places:
            checked.add((app, place))
            got = captured[app]["contexts (owner)"].get(place)
            yield from _compare_context(app, f"context menu: {context} ({place})", entries, got)
    for app in APPS:
        for place, got in captured[app]["contexts (owner)"].items():
            items = context_items(got)
            if (app, place) not in checked and items:
                yield Finding(
                    "Context menu: not in the workbook",
                    app,
                    f"context menu: {place}",
                    workbook="—",
                    web=", ".join(items),
                    next_step="add rows to the Context menus sheet, or drop the menu",
                )


def _compare_context(app: str, where: str, entries: list[str], got: Any) -> Iterator[Finding]:
    have = context_items(got)
    if have is None:
        yield Finding(
            "Context menu: missing entries",
            app,
            where,
            workbook=", ".join(entries),
            web=str(got),
            next_step="build this context menu",
        )
        return
    missing = [e for e in entries if not any(same_words(e, h) for h in have)]
    extra = [h for h in have if not any(same_words(e, h) for e in entries)]
    renames = _pair_renames(missing, extra)
    missing = [e for e in missing if e not in renames.values()]
    extra = [h for h in extra if h not in renames]
    if missing or renames:
        steps = [f"rename {old} → {new}" for old, new in renames.items()] + (
            ["add " + ", ".join(missing)] if missing else []
        )
        yield Finding(
            "Context menu: missing entries",
            app,
            where,
            workbook=", ".join(entries),
            web=", ".join(have),
            next_step="; ".join(steps),
        )
    if extra:
        yield Finding(
            "Context menu: not in the workbook",
            app,
            where,
            workbook=", ".join(entries),
            web=", ".join(have),
            next_step="add rows for " + ", ".join(extra) + ", or drop them",
        )


def _pair_renames(missing: list[str], extra: list[str]) -> dict[str, str]:
    """Today's entries (``extra``) that are the workbook's entries (``missing``) under other words: Insert Row Above is
    Row above. Paired by the most similar words, each at most once, and only when they are similar enough."""
    from difflib import SequenceMatcher

    pairs: dict[str, str] = {}
    for old in extra:
        scores = [(SequenceMatcher(None, old.casefold(), new.casefold()).ratio(), new) for new in missing]
        score, best = max(((sc, n) for sc, n in scores if n not in pairs.values()), default=(0.0, ""))
        if score >= 0.45:
            pairs[old] = best
    return pairs


def context_roles_and_german(captured: dict[str, Any], data: set[str]) -> Iterator[Finding]:
    """Context-menu entries greyed for an editor or a viewer but not for the owner, and context menus in German."""
    for app in APPS:
        owner = captured[app]["contexts (owner)"]
        for place, got in owner.items():
            if not isinstance(got, dict):
                continue
            for n, item in enumerate(i for i in got["items"] if not i.get("sep")):
                greyed = [
                    role for role in ROLES if _context_disabled(captured[app][f"contexts ({role})"].get(place), n)
                ]
                if greyed and not item["disabled"]:
                    yield Finding(
                        "Greyed for a role",
                        app,
                        f"context menu: {place} ▸ {item['label']}",
                        web=f"greyed for: {', '.join(greyed)}",
                        next_step="phase 3: hide, or keep greyed?",
                    )
            german = captured[app]["contexts (owner, de)"].get(place)
            if isinstance(german, dict):
                yield from _german_items(app, (f"context menu: {place}",), got["items"], german["items"], data)


def _context_disabled(got: Any, n: int) -> bool:
    if not isinstance(got, dict):
        return False
    items = [i for i in got["items"] if not i.get("sep")]
    return n < len(items) and bool(items[n]["disabled"])


# --- the workbook itself -------------------------------------------------------------------------------------------


def workbook_clashes(
    rows: list[Row], apps: list[App], loose: dict[str, dict[str, str]], texts: list[tuple[str, str]]
) -> Iterator[Finding]:
    """Two different entries of one app with the same shortcut in the workbook; or a workbook shortcut that an entry
    the workbook does not list (and its notes do not drop) or a key without an entry already uses. Ask ai in Tools and
    in Help is one function with one shortcut, not a clash."""
    for app in apps:
        by_shortcut: dict[str, set[str]] = {}
        for row in rows:
            if app.name in row.groups and row.shortcuts["Web"]:
                by_shortcut.setdefault(row.shortcuts["Web"], set()).add(row.label)
        covered = app.covered(rows)
        for entry in app.desktop:
            if entry.shortcut in by_shortcut and id(entry) not in covered and not mention(texts, entry):
                by_shortcut[entry.shortcut].add(f"{entry.label} (today, not in the workbook)")
        for shortcut, apps_doing in loose.items():
            if app.name in apps_doing and shortcut in by_shortcut:
                by_shortcut[shortcut].add(f"{apps_doing[app.name]} (Keys without entry)")
        for shortcut, labels in sorted(by_shortcut.items()):
            if len(labels) > 1:
                yield Finding(
                    "Workbook: shortcut clash",
                    app.name,
                    shortcut,
                    workbook=" / ".join(sorted(labels)),
                    next_step="give one of them another shortcut",
                )


def keys_without_entry(sheet: Worksheet) -> dict[str, dict[str, str]]:
    """The sheet "Keys without entry": {shortcut: {app: what it does}}."""
    col = columns(sheet)
    found: dict[str, dict[str, str]] = {}
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if values[col["#"]]:
            for written in str(values[col["Key"]]).split(" / "):
                shortcut = normal_shortcut(written)
                if shortcut:
                    found[shortcut] = {
                        app: str(values[col["What it does"]]) for app in APPS if _marked(values[col[app]])
                    }
    return found


def open_decisions(sheet: Worksheet) -> Iterator[Finding]:
    """The rows of the "To decide" sheet that have no decision yet."""
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if values[0] and not values[5]:
            yield Finding(
                "Open in the workbook",
                "all",
                f"To decide #{values[0]}: {values[1]}",
                workbook=str(values[4] or ""),
                next_step="decide (sheet To decide)",
            )


def capitalisation_rule(found: list[Finding]) -> Iterator[Finding]:
    """One question for all the labels that differ only in their capitalisation: the workbook writes sentence case,
    the manifest header capitalisation, which the GNOME HIG asks for in menu items (pages Menus and Writing Style)."""
    cases = [f for f in found if f.kind == "Label: capitalisation only"]
    if cases:
        yield Finding(
            "Workbook: capitalisation rule",
            "all",
            "labels that differ only in capitalisation",
            workbook=f"{len(cases)} labels in sentence case (“Rename sheet…”)",
            web="header capitalisation (“Rename Sheet…”)",
            desktop="header capitalisation (manifest: “in the capitalisation of the GNOME HIG”)",
            next_step="choose one rule: the GNOME HIG asks for header capitalisation in menu items",
        )


def questions() -> Iterator[Finding]:
    """Questions the comparison raised that no single row answers."""
    yield Finding(
        "Question",
        "all",
        "built-in names in German",
        workbook="—",
        web="the built-in styles (Title, Heading 1, …) and shapes (Circle, …) show in English in German",
        next_step="they are document data, like any style name: translate the built-in ones when a document is made?",
    )


def late_rows(rows: list[Row], late: set[int]) -> Iterator[Finding]:
    """One finding per workbook row written after its menu's block had ended."""
    for row in rows:
        if row.number in late:
            yield Finding(
                "Workbook: row out of menu order",
                "all",
                row.target,
                workbook=f"row {row.number}",
                row=row.number,
                next_step=f"move the row to where it goes in {row.menu}",
            )


# --- everything ----------------------------------------------------------------------------------------------------


def apps_from(captured: dict[str, Any]) -> list[App]:
    """The three apps from the manifest and a capture of the web client."""
    return [
        App(
            name=name,
            desktop=manifest_entries(name),
            web=web_entries(captured[name]["owner"]),
            web_by_role={role: web_entries(captured[name][role]) for role in ROLES},
        )
        for name in APPS
    ]


def findings(workbook: Workbook, captured: dict[str, Any]) -> list[Finding]:
    """Every difference between the workbook and the apps, sorted by kind as ``KINDS`` lists them."""
    rows = workbook_rows(workbook["Menus"])
    late = rows_out_of_order(rows)
    texts = workbook_texts(workbook)
    data = builtin_shape_names()
    apps = apps_from(captured)
    in_context = context_entries(workbook["Context menus"])
    found: list[Finding] = [
        *open_decisions(workbook["To decide"]),
        *questions(),
        *workbook_clashes(rows, apps, keys_without_entry(workbook["Keys without entry"]), texts),
        *late_rows(rows, late),
    ]
    for app in apps:
        found.extend(f for row in rows if app.name in row.groups for f in compare_row(app, row))
        found.extend(compare_order(app, rows, late))
        found.extend(compare_extras(app, rows, texts, in_context[app.name]))
        found.extend(compare_clients(app))
        found.extend(compare_german(app.name, captured[app.name]["owner"], captured[app.name]["owner (de)"], data))
        found.extend(compare_roles(app))
        found.extend(viewer_can_use(app))
        found.extend(sealed_submenus(app))
    found.extend(compare_contexts(workbook["Context menus"], captured))
    found.extend(context_roles_and_german(captured, data))
    found.extend(capitalisation_rule(found))
    order = list(KINDS)
    return sorted(found, key=lambda f: (order.index(f.kind), f.row or 0, f.where, f.app))


# --- writing -------------------------------------------------------------------------------------------------------

COLUMNS = (
    ("#", 5),
    ("Finding", 24),
    ("Needs your decision", 10),
    ("App", 10),
    ("Where", 38),
    ("Workbook row", 9),
    ("Workbook says", 40),
    ("Web today", 38),
    ("Desktop today (manifest)", 38),
    ("Next step", 34),
    ("Decision", 11),
    ("Your comment", 36),
)


def answers(workbook: Workbook) -> dict[tuple[str, str, str], tuple[Any, Any]]:
    """The owner's Decision and comment on the Diagnosis sheet as it is, by finding (kind, app, where): what a rerun
    keeps for a finding that is still there."""
    if SHEET not in workbook.sheetnames:
        return {}
    col = columns(workbook[SHEET])
    kept = {}
    for values in workbook[SHEET].iter_rows(min_row=2, values_only=True):
        decision, comment = values[col["Decision"]], values[col["Your comment"]]
        if values[col["Finding"]] and (decision or comment):
            kept[(values[col["Finding"]], values[col["App"]], values[col["Where"]])] = (decision, comment)
    return kept


def write_sheet(workbook: Workbook, found: Iterable[Finding], source: str) -> None:
    """Replace the "Diagnosis" sheet, in the look of the workbook's other sheets (ink header, yellow for the owner),
    keeping the owner's Decision and comment of every finding that is still there."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    kept = answers(workbook)
    if SHEET in workbook.sheetnames:
        del workbook[SHEET]
    sheet = workbook.create_sheet(SHEET, index=1)
    thin = Side(style="thin", color="FFBFBFBF")
    plain = Font(name="Arial", size=10)
    for n, (title, width) in enumerate(COLUMNS, start=1):
        cell = sheet.cell(1, n, title)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFFFF")
        cell.fill = PatternFill("solid", fgColor="FF1F1A33")
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        sheet.column_dimensions[cell.column_letter].width = width
    rows = list(found)
    for r, f in enumerate(rows, start=2):
        values = (
            r - 1,
            f.kind,
            "yes" if f.decide else "",
            f.app,
            f.where,
            f.row,
            f.workbook,
            f.web,
            f.desktop,
            f.next_step,
            *kept.get((f.kind, f.app, f.where), (None, None)),
        )
        for n, value in enumerate(values, start=1):
            cell = sheet.cell(r, n, value)
            cell.font, cell.border = plain, Border(top=thin, bottom=thin, left=thin, right=thin)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if n > len(COLUMNS) - 2:
                cell.fill = PatternFill("solid", fgColor="FFFFF9C4")
    choice = DataValidation(type="list", formula1='"ok,change,discuss"', allow_blank=True)
    choice.add(f"K2:K{len(rows) + 1}")
    sheet.add_data_validation(choice)
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = f"A1:L{len(rows) + 1}"
    sheet.cell(len(rows) + 3, 2, source).font = Font(name="Arial", size=9, italic=True)


def summary(found: list[Finding]) -> list[str]:
    """One line per kind: how many, in which apps."""
    lines = []
    for kind in KINDS:
        these = [f for f in found if f.kind == kind]
        if these:
            per_app = Counter(f.app for f in these)
            lines.append(f"{len(these):4}  {kind}  ({', '.join(f'{a} {n}' for a, n in sorted(per_app.items()))})")
    lines.append(f"{len(found):4}  findings, {sum(f.decide for f in found)} of them need a decision")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Compare, print the counts, and (without --dry-run) write the Diagnosis sheet."""
    import openpyxl

    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--web", type=Path, default=WEB, help="the capture of menu_capture.py")
    parser.add_argument("--workbook", type=Path, default=WORKBOOK)
    parser.add_argument("--dry-run", action="store_true", help="print the counts, leave the workbook alone")
    args = parser.parse_args(argv)
    captured = json.loads(args.web.read_text(encoding="utf-8"))
    workbook = openpyxl.load_workbook(args.workbook)
    found = findings(workbook, captured)
    print("\n".join(summary(found)))
    if not args.dry_run:
        browser = captured.get("browser", "chromium")
        write_sheet(
            workbook,
            found,
            f"Made by scripts/menu_audit.py from the manifest and a capture of the web client "
            f"in {browser}. Rerun both after a change.",
        )
        workbook.save(args.workbook)
        print(f"wrote the {SHEET} sheet of {args.workbook}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
