"""One searchable catalog of every cell function (E13 help system; D76, D30).

A formula can call two kinds of function (see ``functions.base`` and ``formula.forms``): a ``UserFunction`` from the
library (``SUM``, ``XLOOKUP`` is *not* one of these) already carries ``description`` and ``examples``, and
``Bound.get_tooltip``/``get_help`` turn them into text. A *form* (``IF``, ``XLOOKUP``, ``INDEX`` ...) belongs to the
core instead, because it chooses what to evaluate or needs to know where a reference points; it has no ``Example``
objects, only a docstring written in the library's own style (``"NAME(args): what it does."``) — forms have used
that convention since before this module existed, so nothing there had to change to make this catalog honest.

:func:`function_catalog` reads both halves and returns one flat, sorted list that leaves nothing out: every name a
formula can call is in it, with nothing invented — a form's entry is its real docstring, not a guess. That is what
the help system shows as "Documentation" for computes (E13.5) and what :func:`search_functions` searches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..formula.forms import FORMS
from .base import GIVES, GIVES_WITH, Example, Translate, example_lines
from .builtin import builtin_registry
from .registry import FunctionRegistry

_SIGNATURE = re.compile(r"^([A-Z][A-Z0-9_.]*\([^)]*\)):\s+", re.DOTALL)


@dataclass(frozen=True, slots=True)
class FunctionHelp:
    """One function's help, however it is implemented. ``source`` is ``"library"`` or ``"core"``, for callers that
    care which half of computes defines it; the help system itself treats every entry the same way."""

    name: str
    signature: str
    description: str
    tooltip: str
    help: str
    source: str
    examples: tuple[Example, ...] = ()  # a library function's worked examples (a form has none)

    def translated(self, translate: Translate) -> FunctionHelp:
        """The same entry with its words said by ``translate``: the description, the tooltip and the help text, whose
        examples are put together again in that language. This package carries no catalog; whoever has one (the
        server, by the language of the connection) passes it in (E13.8, D323). A tooltip or help text that was
        written by hand rather than derived (a function with its own ``get_tooltip``) is left as it is. The entry
        itself, not a copy, comes back when nothing changed, so the identity gives the same object."""
        if not self.description:
            return self
        description = translate(self.description)
        derived_tooltip = f"{self.signature}: {self.description}"
        tooltip = f"{self.signature}: {description}" if self.tooltip == derived_tooltip else self.tooltip
        if self.source == "core":
            help_text = tooltip if tooltip != self.tooltip else self.help
        else:
            derived_help = "\n".join([self.tooltip, "", *example_lines(self.examples)])
            help_text = (
                "\n".join([tooltip, "", *example_lines(self.examples, translate)])
                if self.help == derived_help
                else self.help
            )
        if (description, tooltip, help_text) == (self.description, self.tooltip, self.help):
            return self
        return FunctionHelp(self.name, self.signature, description, tooltip, help_text, self.source, self.examples)


def _collapsed(text: str) -> str:
    """A docstring's own line wrapping removed: one paragraph, one line."""
    return " ".join(text.split())


def _core_entry(name: str) -> FunctionHelp:
    """A form's :class:`FunctionHelp`, read from its docstring (forms carry no ``Example``\\ s to draw help from)."""
    doc = (FORMS[name].__doc__ or "").strip()
    match = _SIGNATURE.match(doc)
    if match is None:  # every form is documented this way today; this is a fallback, not the expected path
        return FunctionHelp(name, f"{name}(...)", "", f"{name}(...)", doc, "core")
    signature = match.group(1)
    description = _collapsed(doc[match.end() :])
    return FunctionHelp(name, signature, description, f"{signature}: {description}", doc, "core")


def function_catalog(registry: FunctionRegistry | None = None) -> list[FunctionHelp]:
    """Every function a formula can call, by name. ``registry`` defaults to the built-in one; a server with
    admin-installed functions (E4.6) would pass its own."""
    registry = builtin_registry() if registry is None else registry
    library = [
        FunctionHelp(
            bound.name,
            bound.signature,
            bound.description,
            bound.get_tooltip(),
            bound.get_help(),
            "library",
            bound.examples,
        )
        for bound in registry
    ]
    core = [_core_entry(name) for name in FORMS]
    return sorted((*library, *core), key=lambda entry: entry.name)


def _rank(entry: FunctionHelp, needle: str) -> int:
    if entry.name == needle:
        return 0
    if entry.name.startswith(needle):
        return 1
    if needle in entry.name:
        return 2
    return 3  # only the description matched


def search_functions(query: str, catalog: list[FunctionHelp] | None = None) -> list[FunctionHelp]:
    """The catalog's entries whose name or description contains ``query`` (case-insensitive), the closest name
    matches first; an empty or blank ``query`` gives the whole catalog, alphabetically."""
    catalog = function_catalog() if catalog is None else catalog
    needle = query.strip().upper()
    if not needle:
        return catalog
    found = [entry for entry in catalog if needle in entry.name or needle in entry.description.upper()]
    return sorted(found, key=lambda entry: (_rank(entry, needle), entry.name))


def get_function(name: str, catalog: list[FunctionHelp] | None = None) -> FunctionHelp | None:
    """The one entry named ``name`` (case-insensitive), or ``None`` if no function has that name."""
    catalog = function_catalog() if catalog is None else catalog
    wanted = name.strip().upper()
    return next((entry for entry in catalog if entry.name == wanted), None)


def translatable_texts(catalog: list[FunctionHelp] | None = None) -> list[str]:
    """Every text of the catalog that a translator is given, sorted: each function's description, the notes of the
    examples and the wordings of an example (the formula and what it gives are not words). ``scripts/extract_i18n.py``
    reads this, since the descriptions are data of the library and not ``_("...")`` calls (E13.8)."""
    catalog = function_catalog() if catalog is None else catalog
    texts = {GIVES, GIVES_WITH}
    for entry in catalog:
        if entry.description:
            texts.add(entry.description)
        texts.update(example.note for example in entry.examples if example.note)
    return sorted(texts)
