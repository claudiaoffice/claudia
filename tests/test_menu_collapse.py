"""The Linux shell draws a menu without what does not fit (slice 6 of the menu work, D1645): ``visible_only`` against
the table of cases the page and the Windows and macOS shell run too
(``clients/contract/fixtures/menu-collapse.json``)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

CONTRACT = Path(__file__).resolve().parents[1] / "clients" / "contract"
sys.path.insert(0, str(CONTRACT / "src"))

from claudia_menus import manifest  # noqa: E402
from claudia_menus.manifest import Action, Kind, Manifest, Menu, MenuEntry, Submenu  # noqa: E402

FIXTURE = CONTRACT / "fixtures" / "menu-collapse.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


def entry(spec: str | dict[str, Any]) -> MenuEntry:
    if isinstance(spec, dict):
        return Submenu(spec["submenu"], tuple(Action(f"test.{s.lstrip('~')}", s, Kind.PAGE) for s in spec["items"]))
    return Action(f"test.{spec.lstrip('~')}", spec, Kind.PAGE)


def hidden(sections: list[list[Any]]) -> set[str]:
    labels = [s for section in sections for e in section for s in (e["items"] if isinstance(e, dict) else [e])]
    return {f"test.{s[1:]}" for s in labels if s.startswith("~")}


def drawn(menu: Menu) -> list[Any]:
    """The menu as the fixture writes it: labels, '-' between sections, a submenu as a dict."""
    out: list[Any] = []
    for n, section in enumerate(menu.sections):
        if n:
            out.append("-")
        out.extend(
            {"submenu": e.label, "items": [a.label for a in e.items]} if isinstance(e, Submenu) else e.label
            for e in section
        )
    return out


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_a_menu_is_drawn_without_what_does_not_fit(case: dict[str, Any]) -> None:
    sections = tuple(tuple(entry(e) for e in section) for section in case["sections"])
    whole = Manifest("test", (Menu("Test", sections),))
    left_out = hidden(case["sections"])
    shown = manifest.visible_only(whole, lambda action_id: action_id not in left_out)
    assert [drawn(m) for m in shown.menus] == [case["drawn"]]


def test_a_menu_with_nothing_left_stays_so_that_its_title_does_not_go() -> None:
    """D1603: the titles never change; the shell puts the menu's "why" line in it."""
    whole = Manifest("test", (Menu("Insert", ((entry("a"),),)),))
    assert [m.label for m in manifest.visible_only(whole, lambda _id: False).menus] == ["Insert"]


def test_the_front_page_still_shows_only_what_works_without_a_document() -> None:
    """``for_start`` is ``visible_only`` with ``on_start``; a menu with nothing for the front page is not shown."""
    start = manifest.for_start(manifest.for_app("composes"))
    assert [m.label for m in start.menus] == ["File", "View", "Preferences", "Help"]
    assert all(manifest.on_start(a.id) for m in start.menus for a in m.all_actions())
