"""Fonts added in Server settings ▸ Fonts reach the LaTeX container without a restart (CODE-50).

The real chain: the font service of a running server, the page's own way of adding a collection, and a formula set by
the real XeLaTeX. Skips where TeX Live is not installed (CI has it)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from claudia_fonts import builtin_folder
from claudia_fonts.adding import add_collection
from claudia_render import RenderFailed, RenderService, ToolRegistry, builtin_registry
from claudia_server.fonts import FontService

pytestmark = pytest.mark.skipif(
    not all(shutil.which(p) for p in ("xelatex", "pdftocairo", "kpsewhich")), reason="TeX Live is not installed"
)


def _tex_font(name: str) -> tuple[str, bytes]:
    found = subprocess.run(["kpsewhich", name], capture_output=True, text=True, check=False).stdout.strip()
    if not found:
        pytest.skip(f"TeX Live has no {name}")
    return name, Path(found).read_bytes()


def test_a_formula_is_set_with_the_latin_modern_fonts_added_while_the_server_runs(tmp_path):
    import asyncio

    fonts = FontService.from_folders(
        [], tmp_path / "webfonts", shipped=[builtin_folder()], added_root=tmp_path / "fonts"
    )
    service = RenderService(
        builtin_registry(lambda: fonts.catalogue, tmp_path / "plugins"),
        ToolRegistry({"xelatex": shutil.which("xelatex"), "pdftocairo": shutil.which("pdftocairo")}),
        tmp_path / "service",
    )

    async def scenario() -> None:
        with pytest.raises(RenderFailed, match="'Latin Modern Roman' is not available"):
            await service.render("latex", "x^2", {})
        add_collection(
            tmp_path / "fonts",
            [_tex_font("lmroman10-regular.otf"), _tex_font("latinmodern-math.otf")],
            fonts.catalogue,
            name="Latin Modern",
            licence="GUST Font License",
            redistributable=True,
            added_by="anna",
            added="2026-11-17",
        )
        fonts.reload()  # what the page does after adding
        done = await service.render("latex", r"x^2 + \frac{1}{2}", {})
        assert "<svg" in done.svg[:300]

    asyncio.run(scenario())


def test_a_formula_that_could_not_be_drawn_is_drawn_when_the_document_is_opened_after_the_fonts_were_added(
    tmp_path, monkeypatch
):
    """The owner's case (CODE-50, CODE-51, CODE-52): fonts missing, the picture fails, the fonts are added, the document
    is opened again: the formula is drawn, and until then a window that joins is told why not."""
    import asyncio
    import json

    from test_server_rendering_jobs import Client

    from claudia_creates import SlideModel
    from claudia_server import hub as hub_module
    from claudia_server.auth import Account
    from claudia_server.containers import RenderDesk
    from claudia_server.creates import creates_methods
    from claudia_server.hub import Hub, MemoryProvider

    fonts = FontService.from_folders(
        [], tmp_path / "webfonts", shipped=[builtin_folder()], added_root=tmp_path / "fonts"
    )
    service = RenderService(
        builtin_registry(lambda: fonts.catalogue, tmp_path / "plugins"),
        ToolRegistry({"xelatex": shutil.which("xelatex"), "pdftocairo": shutil.which("pdftocairo")}),
        tmp_path / "service",
    )
    monkeypatch.setattr(hub_module, "RENDER_DELAY", 0.02)
    ann = Account("ann", "owner")
    add = {"slide": "s1", "x": 10, "y": 10, "w": 300, "h": 120, "type": "latex", "source": r"x^2 + \frac{1}{2}"}

    async def scenario() -> None:
        hub = Hub(MemoryProvider(SlideModel), methods=creates_methods, renderings=RenderDesk(service))
        first = await hub.open("deck", create=True)
        container = Client(first, ann).request("add_container", add)["result"]["container"]
        await asyncio.sleep(1.0)
        late = Client(first, Account("bob", "editor"))
        (entry,) = late.request("containers")["result"]
        assert entry["image"] is None and entry["outcome"]["ok"] is False
        assert "Latin Modern Roman" in entry["outcome"]["message"]
        add_collection(
            tmp_path / "fonts",
            [_tex_font("lmroman10-regular.otf"), _tex_font("latinmodern-math.otf")],
            fonts.catalogue,
            name="Latin Modern",
            licence="GUST Font License",
            redistributable=True,
            added_by="anna",
            added="2026-11-17",
        )
        fonts.reload()
        first.stop_rendering()
        hub._documents.clear()
        again = await hub.open("deck")
        for _ in range(100):  # real TeX takes a moment
            await asyncio.sleep(0.1)
            if again.document.model.containers[container].image is not None:
                break
        assert again.document.model.containers[container].image is not None
        json.dumps(Client(again, ann).request("containers")["result"])

    asyncio.run(scenario())
