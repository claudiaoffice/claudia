"""The LaTeX container sets with the fonts the server has *now* (CODE-50).

Server settings ▸ Fonts adds fonts while the server runs, and ``FontService.reload`` makes a new catalogue. The
container used to keep the catalogue of the server's start, so a formula said "the font 'Latin Modern Roman' is not
available" until the server was restarted. These tests need no TeX: the fonts are checked before any program runs."""

from pathlib import Path

import pytest
from conftest import runs_in_a_loop

from claudia_fonts import Catalogue, Collection, CollectionRecord
from claudia_fonts.testing import make_font
from claudia_render import RenderFailed, builtin_registry
from claudia_render.plugin import RenderRequest
from claudia_render.tools import ResolvedTool
from claudia_typeset import Limits


def _catalogue(folder: Path, *fonts: tuple[str, bool]) -> Catalogue:
    folder.mkdir(parents=True, exist_ok=True)
    for index, (family, math) in enumerate(fonts):
        make_font(folder / f"font-{index}.ttf", family, math=math)
    record = CollectionRecord(name=folder.name, licence="OFL-1.1", redistributable=True)
    return Catalogue.from_collections([Collection(folder, record)])


def _tools() -> dict[str, ResolvedTool]:
    # never run: the fonts are refused before the engine starts
    return {name: ResolvedTool(name, Path("/nowhere") / name, "1", {}) for name in ("xelatex", "pdftocairo")}


async def _render(plugin) -> str:
    request = RenderRequest("x^2", {"mode": "math", "width_mm": 100.0})
    with pytest.raises(RenderFailed) as refused:
        await plugin.render(request, _tools(), Limits())
    return str(refused.value)


@runs_in_a_loop
async def test_a_font_added_while_the_server_runs_is_seen_by_the_next_formula(tmp_path):
    current = {"catalogue": _catalogue(tmp_path / "start", ("Other", False))}
    plugin = builtin_registry(lambda: current["catalogue"], tmp_path / "plugins").get("latex")

    assert "'Latin Modern Roman' is not available" in await _render(plugin)

    # the administrator adds the text font; the server reloads and has a new catalogue
    current["catalogue"] = _catalogue(tmp_path / "added", ("Latin Modern Roman", False))

    assert "no math font" in await _render(plugin)  # the text font is found now; the math font is the next thing


@runs_in_a_loop
async def test_a_font_that_goes_away_is_not_used_any_more(tmp_path):
    current = {"catalogue": _catalogue(tmp_path / "both", ("Latin Modern Roman", False), ("Latin Modern Math", True))}
    plugin = builtin_registry(lambda: current["catalogue"], tmp_path / "plugins").get("latex")
    current["catalogue"] = _catalogue(tmp_path / "none", ("Other", False))

    assert "'Latin Modern Roman' is not available" in await _render(plugin)


def test_the_latex_container_keys_its_pictures_by_the_fonts_it_draws_with(tmp_path):
    """CODE-54: the service keeps a picture under the plugin's cache token; a replaced font must change it."""
    current = {"catalogue": _catalogue(tmp_path / "one", ("Latin Modern Roman", False))}
    plugin = builtin_registry(lambda: current["catalogue"], tmp_path / "plugins").get("latex")
    before = plugin.cache_token()
    replaced = tmp_path / "two"  # the same family and style, a newer version of the font
    replaced.mkdir()
    make_font(replaced / "font-0.ttf", "Latin Modern Roman", version="2.0")
    record = CollectionRecord(name="two", licence="OFL-1.1", redistributable=True)
    current["catalogue"] = Catalogue.from_collections([Collection(replaced, record)])
    assert before and plugin.cache_token() != before
    assert plugin.cache_token() == current["catalogue"].digest
