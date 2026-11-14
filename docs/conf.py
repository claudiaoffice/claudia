"""Sphinx configuration: the API reference is generated from the docstrings of the code."""

import builtins
import sys
from pathlib import Path

from docutils import nodes
from sphinx.addnodes import pending_xref

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
    (r"py:.*", r"(typing|collections|collections\.abc|abc|builtins|enum|datetime|re)\..*"),
    # TypeVars and type parameters: M (DocumentModel), A (the anchor of VisualObject/ObjectModel)
    (r"py:class", r"abc\.ABC|M|A"),
    (r"py:class", r"'Mapping\[str"),  # (Sphinx cannot split the quoted Mapping[str, int])
    # (nor generics with several arguments in a signature: it cuts them at the first comma)
    (r"py:class", r"(Callable|dict|list|tuple)\[.*"),
    # standard library and FastAPI types in signatures (no network for intersphinx)
    (r"py:class", r"(os|pathlib|ssl)\.\w+|(fastapi|starlette)\..*"),
    # lxml's element type in the signatures of claudia-odf-io (no network for intersphinx)
    (r"py:class", r"lxml\..*"),
    # the `regex` package's compiled pattern in claudia-search, and the clock its deadlines are read on
    (r"py:class", r"_?regex\..*"),
    (r"py:func", r"time\.monotonic"),
    # the Linux client's connector: the TypeVar of its worker alias
    (r"py:class", r"claudia_shell_gtk\.connector\.T"),
    # WorkerPool.submit's own TypeVar/ParamSpec (P, R): not a class to link to
    (r"py:class", r"claudia_server\.workers\.[PR]"),
    # `type` aliases (PEP 695) for the per-app object types and a rendering's setting values: an alias is not a class
    (r"py:class", r"claudia_(creates|computes|composes)\.model\.(Slide|Sheet|Text)Object"),
    (r"py:class", r"claudia_core\.renderings\.Scalar"),
]
html_theme = "alabaster"
myst_heading_anchors = 3


# ------------------------------------------------------------------------------- built-in names are not linked
_BUILTIN_NAMES = frozenset(name for name in dir(builtins) if not name.startswith("_"))


def _leave_builtins_unlinked(app, doctree) -> None:
    """A signature's ``type[...]`` or ``str`` is a built-in, never one of ours: left as plain text before Sphinx
    resolves it. Otherwise a bare built-in name is looked up loosely and links to (or, when there are several, warns
    about) any documented attribute of the same name, such as a dataclass field called ``type``."""
    for xref in list(doctree.findall(pending_xref)):
        if xref.get("refdomain") == "py" and xref.get("reftarget") in _BUILTIN_NAMES:
            xref.replace_self(nodes.inline("", "", *xref.children))


def setup(app):
    app.connect("doctree-read", _leave_builtins_unlinked)
