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
* the **web capture** (``menu_capture.py``): what a person sees in the browser, per role and in German.

Each difference becomes one row (a finding): its kind, what the workbook says, what web and desktop do today, the next
step, and whether it needs the owner's decision or is only work to do.
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
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "claudiaoffice-log" / "notes" / "claudia-menus.xlsx"
WEB = ROOT / ".claudia" / "menu-audit" / "web.json"
SHEET = "Diagnosis"
APPS = ("computes", "composes", "creates")
PLATFORMS = ("Web", "Linux", "Windows", "macOS")
ARROW = " ▸ "

#: Kinds of finding, in the order the sheet lists them, and whether each needs the owner's decision.
KINDS: dict[str, bool] = {
    "Open in the workbook": True,
    "Workbook: capitalisation rule": True,
    "Workbook: key clash": True,
    "Workbook: row out of menu order": True,
    "Not in the workbook": True,
    "Only in the web menu": True,
    "Context menu: not in the workbook": True,
    "Key per platform": True,
    "Wrong menu": False,
    "Label": False,
    "Label: capitalisation only": False,
    "Key": False,
    "Order or separators": False,
    "Not in this app yet": False,
    "Not built yet": False,
    "To remove (the workbook drops it in this app)": False,
    "Web and desktop differ": False,
    "Context menu: missing entries": False,
    "Not translated": False,
    "Greyed for a role": False,
    "Not checked": False,
}


@dataclass(frozen=True)
class Entry:
    """One menu entry where it is today: its top menu, the labels down to it, its separator group and its key.

    ``submenu`` marks the entry that opens a submenu; ``sealed`` one whose submenu could not be read (it is greyed)."""

    menu: str
    path: tuple[str, ...]
    group: int
    position: int
    key: str | None = None
    id: str | None = None
    disabled: bool = False
    submenu: bool = False
    sealed: bool = False

    @property
    def place(self) -> str:
        return ARROW.join((self.menu, *self.path[:-1]))

    @property
    def label(self) -> str:
        return self.path[-1]

    def shown(self) -> str:
        key = f" [{self.key}]" if self.key else ""
        return ARROW.join((self.menu, *self.path)) + key


@dataclass(frozen=True)
class Row:
    """One row of the workbook's "Menus" sheet."""

    number: int
    menu: str
    path: tuple[str, ...]
    groups: dict[str, int]
    keys: dict[str, str | None]
    today_labels: dict[str, str]
    today_id: str | None

    @property
    def target(self) -> str:
        return ARROW.join((self.menu, *self.path))

    @property
    def place(self) -> str:
        return ARROW.join((self.menu, *self.path[:-1]))

    @property
    def label(self) -> str:
        return clean_label(self.path[-1])


@dataclass
class Finding:
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


def normal_key(key: object) -> str | None:
    """A key as the web menus show it, so the workbook's ``Shift+Alt+Up`` and the menu's ``Shift+Alt+↑`` agree."""
    text = str(key).strip() if key is not None else ""
    if text in {"", "None", "n/a"}:
        return None
    return "+".join(_KEY_WORDS.get(part, part) for part in text.replace(" ", "").split("+"))


def clean_label(label: str) -> str:
    """The words of a workbook entry without its notes: ``Dark mode (switch)`` is the entry ``Dark mode``."""
    return re.sub(r"\s*\((switch|one entry per language)\)\s*$", "", label).strip()


def same_words(a: str, b: str) -> bool:
    """Two labels for the same entry, whatever their capitalisation and their closing ``…``: Table and Table…"""

    def bare(label: str) -> str:
        return re.sub(r"[\s…?.▸]+$", "", clean_label(label)).casefold()

    return bare(a) == bare(b)


def compare_labels(want: str, have: str) -> str | None:
    """``None`` when they agree, ``"case"`` when only the capitalisation differs, ``"words"`` otherwise."""
    want, have = clean_label(want), clean_label(have)
    if want == have:
        return None
    return "case" if want.casefold() == have.casefold() else "words"


def mac_key(key: str | None) -> str | None:
    """The macOS form of a key as the one-key manifest gives it there: Ctrl is Cmd, Alt is Option."""
    if key is None:
        return None
    return "+".join({"Ctrl": "Cmd", "Alt": "Option"}.get(part, part) for part in key.split("+"))


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


def columns(sheet) -> dict[str, int]:
    """Column index by header, so a column the owner inserts does not shift the others."""
    return {cell.value: n for n, cell in enumerate(sheet[1]) if cell.value}


def workbook_rows(sheet) -> list[Row]:
    """The "Menus" sheet as rows."""
    col = columns(sheet)
    rows = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if not values[col["#"]] or not values[col["Menu"]]:
            continue
        rows.append(
            Row(
                number=int(values[col["#"]]),
                menu=str(values[col["Menu"]]),
                path=tuple(part.strip() for part in str(values[col["Entry"]]).split("▸")),
                groups={app: int(values[col[app]]) for app in APPS if values[col[app]] not in (None, "")},
                keys={platform: normal_key(values[col[platform]]) for platform in PLATFORMS},
                today_labels=today_labels(values[col["Today's label"]]),
                today_id=values[col["Today's action id"]] or None,
            )
        )
    return rows


def workbook_texts(workbook) -> list[tuple[str, str]]:
    """Every text of the workbook's sheets but the diagnosis, as (sheet, text): where a removal may be written down."""
    return [
        (sheet.title, value)
        for sheet in workbook
        if sheet.title != SHEET
        for row in sheet.iter_rows(values_only=True)
        for value in row
        if isinstance(value, str) and not value.startswith("=") and len(value) > 30
    ]


def manifest_entries(app: str) -> list[Entry]:
    """The desktop clients' menus of ``app``, from the manifest."""
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    from generate_keys import _manifest_module, shown  # the web menus' own key notation

    manifest = _manifest_module()
    entries: list[Entry] = []
    for menu in manifest.for_app(app).menus:
        for group, section in enumerate(menu.sections, start=1):
            for item in section:
                if isinstance(item, manifest.Submenu):
                    entries.extend(
                        Entry(
                            menu.label,
                            (item.label, child.label),
                            1,
                            len(entries) + n,
                            shown(child.accelerators[0]) if child.accelerators else None,
                            child.id,
                        )
                        for n, child in enumerate(item.items)
                    )
                else:
                    key = shown(item.accelerators[0]) if item.accelerators else None
                    entries.append(Entry(menu.label, (item.label,), group, len(entries), key, item.id))
    return entries


#: Submenus whose entries are the document's (style names), not the app's: only entries with a key are kept from them
_DOCUMENT_SUBMENUS = {"Apply Style", "Stil anwenden"}


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
        path = (*above, item["label"])
        children = item.get("items")
        submenu = bool(item.get("sub"))
        yield Entry(
            menu,
            path,
            group,
            at + n * 100 if not above else at + n,
            item.get("hint"),
            None,
            bool(item.get("disabled")),
            submenu,
            submenu and not isinstance(children, list),
        )
        if isinstance(children, list):
            kept = [c for c in children if c.get("sep") or c.get("hint") or item["label"] not in _DOCUMENT_SUBMENUS]
            yield from _web_items(menu, path, kept, at + n * 100 + 1)


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

    @staticmethod
    def _same_words_anywhere(entry: Entry, free: list[Entry]) -> Entry | None:
        found = [w for w in free if same_words(w.label, entry.label) and not w.submenu]
        return found[0] if len(found) == 1 else None

    @staticmethod
    def _sealed_parent(entry: Entry, free: list[Entry]) -> Entry | None:
        return next((w for w in free if w.sealed and (w.menu, *w.path) == (entry.menu, *entry.path[:-1])), None)

    def by_id(self, action_id: str | None) -> tuple[Entry | None, Entry | None]:
        """(desktop, web) of an action id."""
        for n, entry in enumerate(self.desktop):
            if action_id and entry.id == action_id:
                return entry, self.twin.get(n)
        return None, None

    def web_named(self, label: str | None) -> Entry | None:
        """The one web entry anywhere with these words, or None when there is none or several."""
        found = [w for w in self.web if label and same_words(w.label, label) and not w.submenu]
        return found[0] if len(found) == 1 else None

    def desktop_of(self, web: Entry | None) -> Entry | None:
        """The desktop entry paired with a web entry."""
        return next((self.desktop[n] for n, w in self.twin.items() if web is not None and w is web), None)

    def paired_web(self) -> set[int]:
        return {id(w) for w in self.twin.values()}


def locate(app: App, row: Row) -> tuple[Entry | None, Entry | None]:
    """Where a workbook row's entry is today in ``app``: (desktop, web)."""
    desktop, web = app.by_id(row.today_id)
    if desktop is None and web is None:
        web = app.web_named(row.today_labels.get(app.name)) or app.web_named(row.path[-1])
        desktop = app.desktop_of(web)
    return desktop, web


def compare_row(app: App, row: Row) -> Iterator[Finding]:
    """What differs between one workbook row and the app."""
    if row.menu == "App menu (macOS)":
        yield Finding(
            "Not checked", app.name, row.target, row.target, next_step="needs the macOS client", row=row.number
        )
        return
    desktop, web = locate(app, row)
    if desktop is None and web is None:
        if row.today_id:
            yield Finding(
                "Not in this app yet",
                app.name,
                row.target,
                row.target,
                "—",
                "—",
                row=row.number,
                next_step=f"add {row.today_id} to {app.name}",
            )
        else:
            yield Finding(
                "Not built yet",
                app.name,
                row.target,
                row.target,
                "—",
                "—",
                row=row.number,
                next_step="build the feature, then the entry",
            )
        return
    readable_web = web if web is not None and not web.sealed else None
    common = {
        "app": app.name,
        "where": row.target,
        "workbook": row.target,
        "row": row.number,
        "web": _shown(web),
        "desktop": _shown(desktop),
    }
    yield from _place(row, desktop, readable_web, common)
    yield from _label(row, desktop, readable_web, common)
    yield from _keys(app, row, desktop, readable_web)


def _shown(entry: Entry | None) -> str:
    if entry is None:
        return "—"
    return entry.shown() + (" (greyed submenu, not opened)" if entry.sealed else "")


def _place(row: Row, desktop: Entry | None, web: Entry | None, common: dict[str, Any]) -> Iterator[Finding]:
    places = {e.place for e in (desktop, web) if e}
    if any(p.casefold() != row.place.casefold() for p in places):
        yield Finding("Wrong menu", next_step=f"move to {row.place}", **common)
    elif any(p != row.place for p in places):
        yield Finding("Label: capitalisation only", next_step=f"submenu written {row.place}", **common)


def _label(row: Row, desktop: Entry | None, web: Entry | None, common: dict[str, Any]) -> Iterator[Finding]:
    if "(one entry per language)" in row.path[-1]:
        return
    verdicts = {compare_labels(row.path[-1], e.label) for e in (desktop, web) if e}
    if "words" in verdicts:
        yield Finding("Label", next_step=f"rename to “{row.label}” (and in the .po files)", **common)
    elif "case" in verdicts:
        yield Finding("Label: capitalisation only", next_step=f"write it “{row.label}”", **common)


def _keys(app: App, row: Row, desktop: Entry | None, web: Entry | None) -> Iterator[Finding]:
    want = row.keys["Web"]
    sides = {"web": web, "desktop": desktop}
    if any(entry is not None and entry.key != want for entry in sides.values()):

        def now(entry: Entry | None) -> str:
            return "—" if entry is None else entry.key or "no key"

        yield Finding(
            "Key",
            app.name,
            row.target,
            want or "no key",
            now(web),
            now(desktop),
            row=row.number,
            next_step=f"bind {want}" if want else "drop the key",
        )
    linux, windows, mac = row.keys["Linux"], row.keys["Windows"], row.keys["macOS"]
    if windows != linux or mac not in (mac_key(linux), linux):
        yield Finding(
            "Key per platform",
            app.name,
            row.target,
            f"Linux {linux} · Windows {windows} · macOS {mac}",
            row=row.number,
            next_step="the manifest gives an entry one key on every platform: allow more?",
        )


def misplaced_rows(rows: list[Row]) -> set[int]:
    """Rows written after their menu's block had ended ("rows are in menu order", says Read me): rows 95 and 96."""
    seen: list[str] = []
    late = set()
    for row in rows:
        if seen and row.menu != seen[-1] and row.menu in seen:
            late.add(row.number)
        elif not seen or row.menu != seen[-1]:
            seen.append(row.menu)
    return late


def compare_order(app: App, rows: list[Row], late: set[int]) -> Iterator[Finding]:
    """Per menu and submenu: are the entries already in their place in the workbook's order and separator groups?
    (Inside a submenu only the order counts: the workbook's group number is the submenu's own group.)"""
    containers: dict[str, list[tuple[Row, Entry]]] = {}
    for row in rows:
        _desktop, web = locate(app, row)
        if (
            app.name in row.groups
            and row.number not in late
            and web
            and not web.sealed
            and web.place.casefold() == row.place.casefold()
        ):
            containers.setdefault(row.place, []).append((row, web))
    for place, pairs in containers.items():
        in_order = [w.position for _r, w in pairs] == sorted(w.position for _r, w in pairs)
        top = ARROW not in place
        grouped = not top or all(
            (a.groups[app.name] == b.groups[app.name]) == (x.group == y.group)
            for (a, x), (b, y) in zip(pairs, pairs[1:], strict=False)
        )
        if not (in_order and grouped):
            want = " | ".join((f"{r.groups[app.name]}:" if top else "") + r.label for r, _w in pairs)
            have = " | ".join(
                (f"{w.group}:" if top else "") + w.label for _r, w in sorted(pairs, key=lambda p: p[1].position)
            )
            yield Finding(
                "Order or separators",
                app.name,
                place,
                want,
                have,
                next_step="reorder" + (" / regroup (n: = separator group)" if top else ""),
            )


def compare_extras(app: App, rows: list[Row], texts: list[tuple[str, str]]) -> Iterator[Finding]:
    """What the app has that no workbook row places in it."""
    rows_here = [r for r in rows if app.name in r.groups]
    covered = {id(e) for r in rows_here for e in locate(app, r) if e}
    ids_anywhere = {r.today_id for r in rows if r.today_id}
    for n, entry in enumerate(app.desktop):
        web = app.twin.get(n)
        if id(entry) in covered or (web and id(web) in covered) or (entry.id or "").startswith("config.language."):
            continue
        if entry.id in ids_anywhere:
            yield Finding(
                "To remove (the workbook drops it in this app)",
                app.name,
                entry.shown(),
                "—",
                _shown(web),
                f"{entry.shown()} ({entry.id})",
                next_step=f"remove from {app.name}",
            )
        elif entry.id == "file.quit":
            continue  # desktop only by design: a browser tab has no Quit (To decide #15)
        else:
            note = mention(texts, entry)
            yield Finding(
                "Not in the workbook",
                app.name,
                entry.shown(),
                note or "—",
                _shown(web),
                f"{entry.shown()} ({entry.id})",
                next_step="the workbook's notes drop it: confirm" if note else "add a row, or remove",
            )
    paired = app.paired_web()
    for entry in app.web:
        if id(entry) in paired or id(entry) in covered or entry.submenu or entry.path[0] == "App Language":
            continue
        yield Finding(
            "Only in the web menu",
            app.name,
            entry.shown(),
            "—",
            entry.shown(),
            "—",
            next_step="an id in the manifest and a workbook row, or remove",
        )


#: Where a note about a removal is most likely the owner's decision, first
_NOTE_ORDER = ("To decide", "Menus", "Context menus", "Keys without entry", "Read me")


def mention(texts: list[tuple[str, str]], entry: Entry) -> str:
    """Where the workbook's notes speak of a removed entry (by its id or its words), shortened: or ''."""
    words = re.sub(r"[…]+$", "", entry.label)
    by_id = re.compile(rf"(?<![\w.-]){re.escape(entry.id)}(?![\w.-])") if entry.id else None
    by_words = re.compile(rf"(?<!\w){re.escape(words)}(?!\w)", re.IGNORECASE) if len(words) > 4 else None
    ranked = sorted(texts, key=lambda t: _NOTE_ORDER.index(t[0]) if t[0] in _NOTE_ORDER else len(_NOTE_ORDER))
    for sheet, text in ranked:
        hit = (by_id and by_id.search(text)) or (by_words and by_words.search(text))
        if hit:
            start = max(0, hit.start() - 60)
            return f"{sheet}: …{text[start : hit.end() + 80].strip()}…"
    return ""


#: Differences between web and desktop that a decision made on purpose
_BY_DESIGN = {
    "format.apply-style": "by design: a flyout of the styles on the web, the page's popover in a shell (D301)"
}


def compare_clients(app: App) -> Iterator[Finding]:
    """Where the web menu and the desktop menus (the manifest) disagree about the same action."""
    for n, entry in enumerate(app.desktop):
        web = app.twin.get(n)
        if (entry.id or "").startswith("config.language.") or (web is not None and web.sealed):
            continue
        if web is None:
            note = "by design: a browser tab has no Quit" if entry.id == "file.quit" else "one menu definition"
            yield Finding(
                "Web and desktop differ",
                app.name,
                entry.shown(),
                web="not in the web menu",
                desktop=f"{entry.shown()} ({entry.id})",
                next_step=note,
            )
        elif (web.place, web.label, web.key) != (entry.place, entry.label, entry.key):
            yield Finding(
                "Web and desktop differ",
                app.name,
                entry.shown(),
                web=web.shown(),
                desktop=f"{entry.shown()} ({entry.id})",
                next_step=_BY_DESIGN.get(entry.id or "", "one menu definition"),
            )


#: Words that are the same in German, or names
_SAME_IN_GERMAN = {"Format", "LaTeX", "Mermaid", "Typst", "English", "Deutsch", "Container", "AI…", "Agenda", "Export…"}


def compare_german(app: str, english: dict[str, Any], german: dict[str, Any]) -> Iterator[Finding]:
    """Entries whose German label is the English one: not translated. The two captures are of the same window, so
    their menus have the same shape and are walked side by side."""
    for (title, items), (_titel, items_de) in zip(english.items(), german.items(), strict=False):
        yield from _german_items(app, (title,), items, items_de)


def _german_items(app: str, above: tuple[str, ...], items: list, items_de: list) -> Iterator[Finding]:
    for item, item_de in zip(items, items_de, strict=False):
        if item.get("sep") or item_de.get("sep"):
            continue
        label, label_de = item["label"], item_de["label"]
        if above[-1] in _DOCUMENT_SUBMENUS and not item.get("hint"):
            continue  # a style's name is the document's
        if label == label_de and label not in _SAME_IN_GERMAN and re.search("[a-z]", label):
            yield Finding(
                "Not translated",
                app,
                ARROW.join((*above, label)),
                web=f"the German menu shows “{label_de}”",
                next_step="translate (po/de.po)",
            )
        if isinstance(item.get("items"), list) and isinstance(item_de.get("items"), list):
            yield from _german_items(app, (*above, label), item["items"], item_de["items"])


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


# --- context menus -------------------------------------------------------------------------------------------------

#: Workbook context (column "Context") → the place the capture right-clicked, per app
CONTEXTS = {
    "Object (image, text box, shape, container, chart)": dict.fromkeys(APPS, "object"),
    "Cell (range)": {"computes": "cell"},
    "Paragraph (in composes, or in a text box)": {"composes": "paragraph"},
    "Table": {"composes": "table"},
    "Row and column headers (tables in composes, and computes)": {"computes": "column header"},
}


def context_items(got: Any) -> list[str] | None:
    """The labels of a captured context menu; a popover of buttons that calls itself a menu counts as one."""
    if isinstance(got, dict):
        return [i["label"] for i in got["items"] if not i.get("sep")]
    found = re.match(r"no menu; opened instead: [^:]*menu: (.*)$", str(got))
    return found.group(1).split(" / ") if found else None


def compare_contexts(sheet, captured: dict[str, Any]) -> Iterator[Finding]:
    col = columns(sheet)
    wanted: dict[tuple[str, str], list[str]] = {}
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if values[col["#"]]:
            for app in APPS:
                if values[col[app]] not in (None, ""):
                    wanted.setdefault((str(values[col["Context"]]), app), []).append(str(values[col["Entry"]]))
    checked = set()
    for (context, app), entries in wanted.items():
        place = CONTEXTS.get(context, {}).get(app)
        if place is None:
            yield Finding(
                "Not checked",
                app,
                f"context menu: {context}",
                ", ".join(entries),
                next_step="the capture does not reach this place yet",
            )
            continue
        checked.add((app, place))
        yield from _compare_context(app, context, entries, captured[app]["contexts"].get(place))
    for app in APPS:
        for place, got in captured[app]["contexts"].items():
            items = context_items(got)
            if (app, place) not in checked and items:
                yield Finding(
                    "Context menu: not in the workbook",
                    app,
                    f"context menu: {place}",
                    "—",
                    ", ".join(items),
                    next_step="add rows to the Context menus sheet, or drop the menu",
                )


def _compare_context(app: str, context: str, entries: list[str], got: Any) -> Iterator[Finding]:
    where = f"context menu: {context}"
    have = context_items(got)
    if have is None:
        yield Finding(
            "Context menu: missing entries",
            app,
            where,
            ", ".join(entries),
            str(got),
            next_step="build this context menu",
        )
        return
    missing = [e for e in entries if not any(same_words(e, h) for h in have)]
    extra = [h for h in have if not any(same_words(e, h) for e in entries)]
    if missing:
        yield Finding(
            "Context menu: missing entries",
            app,
            where,
            ", ".join(entries),
            ", ".join(have),
            next_step="add " + ", ".join(missing),
        )
    if extra:
        yield Finding(
            "Context menu: not in the workbook",
            app,
            where,
            ", ".join(entries),
            ", ".join(have),
            next_step="add rows for " + ", ".join(extra) + ", or drop them",
        )


# --- the workbook itself -------------------------------------------------------------------------------------------


def workbook_clashes(
    rows: list[Row], apps: list[App], loose_keys: dict[str, Any], texts: list[tuple[str, str]]
) -> Iterator[Finding]:
    """Two different entries of one app with the same key in the workbook, or a workbook key that an entry the
    workbook does not list and its notes do not drop, or a key without an entry, already uses. Ask ai in Tools and
    in Help is one function with one key, not a clash."""
    for app in apps:
        by_key: dict[str, set[str]] = {}
        for row in rows:
            if app.name in row.groups and row.keys["Web"]:
                by_key.setdefault(row.keys["Web"], set()).add(row.label)
        listed = {id(e) for r in rows for e in locate(app, r) if e}
        for n, entry in enumerate(app.desktop):
            web = app.twin.get(n)
            unlisted = id(entry) not in listed and not (web and id(web) in listed) and not mention(texts, entry)
            if entry.key and unlisted and entry.key in by_key:
                by_key[entry.key].add(f"{entry.label} (today, not in the workbook)")
        for key, labels in loose_keys.items():
            if app.name in labels and key in by_key:
                by_key[key].add(f"{labels[app.name]} (Keys without entry)")
        for key, labels in sorted(by_key.items()):
            if len(labels) > 1:
                yield Finding(
                    "Workbook: key clash",
                    app.name,
                    key,
                    " / ".join(sorted(labels)),
                    next_step="give one of them another key",
                )


def keys_without_entry(sheet) -> dict[str, Any]:
    """The sheet "Keys without entry": {key: {app: what it does}}."""
    col = columns(sheet)
    found: dict[str, Any] = {}
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if values[col["#"]]:
            for written in str(values[col["Key"]]).split(" / "):
                key = normal_key(written)
                if key:
                    found[key] = {
                        app: str(values[col["What it does"]]) for app in APPS if values[col[app]] not in (None, "")
                    }
    return found


def open_decisions(sheet) -> Iterator[Finding]:
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if values[0] and not values[5]:
            yield Finding(
                "Open in the workbook",
                "all",
                f"To decide #{values[0]}: {values[1]}",
                str(values[4] or ""),
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
            f"{len(cases)} labels differ only in capitalisation",
            "sentence case (“Rename sheet…”)",
            "header capitalisation (“Rename Sheet…”)",
            "header capitalisation (manifest: “in the capitalisation of the GNOME HIG”)",
            next_step="choose one rule: the GNOME HIG asks for header capitalisation in menu items",
        )


def late_rows(rows: list[Row], late: set[int]) -> Iterator[Finding]:
    for row in rows:
        if row.number in late:
            yield Finding(
                "Workbook: row out of menu order",
                "all",
                row.target,
                f"row {row.number}",
                row=row.number,
                next_step=f"move the row to where it goes in {row.menu}",
            )


# --- everything ----------------------------------------------------------------------------------------------------


def apps_from(captured: dict[str, Any]) -> list[App]:
    return [
        App(
            name=name,
            desktop=manifest_entries(name),
            web=web_entries(captured[name]["owner"]),
            web_by_role={role: web_entries(captured[name][role]) for role in ("editor", "viewer")},
        )
        for name in APPS
    ]


def findings(workbook, captured: dict[str, Any]) -> list[Finding]:
    rows = workbook_rows(workbook["Menus"])
    late = misplaced_rows(rows)
    texts = workbook_texts(workbook)
    apps = apps_from(captured)
    found: list[Finding] = [
        *open_decisions(workbook["To decide"]),
        *workbook_clashes(rows, apps, keys_without_entry(workbook["Keys without entry"]), texts),
        *late_rows(rows, late),
    ]
    for app in apps:
        for row in rows:
            if app.name in row.groups:
                found.extend(compare_row(app, row))
        found.extend(compare_order(app, rows, late))
        found.extend(compare_extras(app, rows, texts))
        found.extend(compare_clients(app))
        found.extend(compare_german(app.name, captured[app.name]["owner"], captured[app.name]["owner (de)"]))
        found.extend(compare_roles(app))
    found.extend(compare_contexts(workbook["Context menus"], captured))
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


def write_sheet(workbook, found: Iterable[Finding], source: str) -> None:
    """Replace the "Diagnosis" sheet, in the look of the workbook's other sheets (ink header, yellow for the owner)."""
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

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
            None,
            None,
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
        write_sheet(
            workbook,
            found,
            f"Made by scripts/menu_audit.py from the manifest and a capture of the web client "
            f"in {captured.get('browser', 'chromium')}. Rerun both after a change.",
        )
        workbook.save(args.workbook)
        print(f"wrote the {SHEET} sheet of {args.workbook}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
