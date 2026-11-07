"""Every workspace package is actually installed by ``uv sync`` (CODE-11).

``[tool.uv.workspace].members = ["packages/*"]`` makes a package a *workspace member* — known to the
lock file — but ``uv sync`` without ``--all-packages`` only installs what the root project's own
``[project].dependencies`` pulls in. ``claudia-computes-io``, ``claudia-composes-io`` and ``claudia-creates-io``
were added as workspace members with their own correct ``pyproject.toml`` dependencies, but never added to the
root project's dependency list — so ``openpyxl``/``python-docx``/``python-pptx`` were never installed, and the
whole test suite failed to even collect (three ``ModuleNotFoundError`` collection errors) until this was caught.

This is a cheap, mechanical guard: every ``packages/*/pyproject.toml`` project name must appear in the root
``pyproject.toml``'s own ``dependencies`` list and in its ``[tool.uv.sources]`` table, exactly like every
existing package already does.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _project_name(pyproject: Path) -> str:
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["name"]


def _root_toml() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def workspace_package_names() -> list[str]:
    return sorted(_project_name(p) for p in (ROOT / "packages").glob("*/pyproject.toml"))


def test_every_workspace_package_is_a_root_dependency():
    root = _root_toml()
    declared = set(root["project"]["dependencies"])
    missing = [name for name in workspace_package_names() if name not in declared]
    assert not missing, (
        f"in packages/ but missing from the root pyproject.toml's [project].dependencies "
        f"(uv sync will never install it): {missing}"
    )


def test_every_workspace_package_has_a_workspace_source():
    root = _root_toml()
    sources = root.get("tool", {}).get("uv", {}).get("sources", {})
    missing = [name for name in workspace_package_names() if sources.get(name) != {"workspace": True}]
    assert not missing, f"missing (or wrong) [tool.uv.sources] entry pinning it to the local workspace: {missing}"
