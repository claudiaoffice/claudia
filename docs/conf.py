"""Sphinx configuration: the API reference is generated from the docstrings of the code."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for src in sorted(ROOT.glob("packages/*/src")):
    sys.path.insert(0, str(src))
sys.path.insert(0, str(ROOT / "clients" / "linux" / "src"))  # the GTK-free modules of the Linux client

from claudia_core import __version__  # noqa: E402

project = "Claudia"
author = "The Claudia contributors"
release = __version__
version = ".".join(__version__.split(".")[:2])

extensions = ["sphinx.ext.autodoc", "sphinx.ext.napoleon", "sphinx.ext.viewcode", "myst_parser"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
exclude_patterns = ["_build"]

autodoc_member_order = "bysource"
autodoc_typehints = "signature"
autodoc_default_options = {"members": True, "undoc-members": False, "show-inheritance": True}
nitpicky = True
# Standard-library types are not linked (the build needs no network); everything of ours must resolve.
nitpick_ignore_regex = [
    (r"py:.*", r"(typing|collections\.abc|abc|builtins|enum|datetime)\..*"),
    # TypeVars and type parameters: M (DocumentModel), A (the anchor of VisualObject/ObjectModel)
    (r"py:class", r"abc\.ABC|M|A"),
    (r"py:class", r"'Mapping\[str"),  # (Sphinx cannot split the quoted Mapping[str, int])
    # (nor generics with several arguments in a signature: it cuts them at the first comma)
    (r"py:class", r"(Callable|dict|list|tuple)\[.*"),
    # standard library and FastAPI types in signatures (no network for intersphinx)
    (r"py:class", r"(os|pathlib|ssl)\.\w+|(fastapi|starlette)\..*"),
    # the Linux client's connector: the TypeVar of its worker alias
    (r"py:class", r"claudia_shell_gtk\.connector\.T"),
    # WorkerPool.submit's own TypeVar/ParamSpec (P, R): not a class to link to
    (r"py:class", r"claudia_server\.workers\.[PR]"),
    # `type` aliases (PEP 695) for the per-app object types: an alias is not a class to link to
    (r"py:class", r"claudia_(creates|computes|composes)\.model\.(Slide|Sheet|Text)Object"),
]
html_theme = "alabaster"
myst_heading_anchors = 3
