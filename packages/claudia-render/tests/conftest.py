"""Helpers: fake tools that behave like a renderer, and the real ones where this machine has them."""

import asyncio
import functools
import os
import shutil
import stat
import sys
import textwrap
from pathlib import Path

import pytest

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="the fake tools are POSIX scripts")


def runs_in_a_loop(test):
    """The repository has no async test plugin: each test drives its coroutine with asyncio.run."""

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        return asyncio.run(test(*args, **kwargs))

    return wrapper


def fake_tool(directory: Path, name: str, body: str) -> Path:
    """An executable script ``name`` in ``directory``: Python, run with the interpreter of the tests."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body))
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


#: A tool that answers ``--version`` and otherwise draws one rectangle of the size in its first line of input.
BOXER = """
    import sys
    if "--version" in sys.argv:
        print("boxer 2.5.1")
        raise SystemExit(0)
    text = open(sys.argv[1], encoding="utf-8").read()
    if "FAIL" in text:
        print("input.txt:2:5: error: no such box")
        raise SystemExit(1)
    width = len(text.strip().splitlines()[0]) * 10
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 20"><rect width="{width}" height="20"/></svg>'
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(svg)
    else:
        print(svg)
"""


def real_tool(env_name: str, *names: str) -> str | None:
    """The path of a real tool: ``$env_name`` if set, else the first of ``names`` on the PATH."""
    if configured := os.environ.get(env_name):
        return configured
    return next((found for name in names if (found := shutil.which(name))), None)


TYPST_FALLBACK = "/tmp/claude-0/typst-dl/typst-x86_64-unknown-linux-musl/typst"  # where this session's copy lives


def typst_path() -> str | None:
    found = real_tool("CLAUDIA_TEST_TYPST", "typst")
    return found or (TYPST_FALLBACK if os.path.exists(TYPST_FALLBACK) else None)


def mermaid_settings() -> dict | None:
    """The tool entry for mmdc and the Chrome behind it, or ``None`` where either is not installed."""
    mmdc = real_tool("CLAUDIA_TEST_MMDC", "mmdc") or (
        "/home/claude/.npm-global/bin/mmdc" if os.path.exists("/home/claude/.npm-global/bin/mmdc") else None
    )
    chrome = real_tool("CLAUDIA_TEST_CHROME", "google-chrome", "chromium", "chromium-browser")
    if not mmdc or not chrome:
        return None
    return {"path": mmdc, "chrome": chrome, "browser_args": ["--no-sandbox", "--disable-gpu"]}


@pytest.fixture
def tex_catalogue(tmp_path):
    """The Latin Modern fonts of the installed TeX Live, as a collection of their own (links, so nothing is copied)."""
    import subprocess

    from claudia_fonts import Catalogue, Collection, CollectionRecord

    missing = [p for p in ("xelatex", "pdftocairo", "kpsewhich") if not shutil.which(p)]
    if missing:
        pytest.skip(f"not installed: {', '.join(missing)}")
    folder = tmp_path / "tex-fonts"
    folder.mkdir()
    for name in ("latinmodern-math.otf", "lmroman10-regular.otf", "lmroman10-bold.otf", "lmroman10-italic.otf"):
        found = subprocess.run(["kpsewhich", name], capture_output=True, text=True, check=False).stdout.strip()
        if not found:
            pytest.skip(f"TeX Live has no {name}")
        (folder / name).symlink_to(Path(found))
    record = CollectionRecord(name="tex-live", licence="GUST Font License", redistributable=True)
    return Catalogue.from_collections([Collection(folder, record)])


@pytest.fixture
def real_service(tmp_path, tex_catalogue):
    """The built-in plugins with whatever real tools this machine has: tests skip for the ones it lacks."""
    from claudia_render import RenderService, ToolRegistry, builtin_registry

    settings: dict = {}
    if typst := typst_path():
        settings["typst"] = typst
    if mermaid := mermaid_settings():
        settings["mmdc"] = mermaid
    return RenderService(
        builtin_registry(tex_catalogue, tmp_path / "plugins"), ToolRegistry(settings), tmp_path / "service"
    )


def needs(tool: str):
    available = {"typst": typst_path(), "mermaid": mermaid_settings()}
    return pytest.mark.skipif(available[tool] is None, reason=f"{tool} is not installed here")
