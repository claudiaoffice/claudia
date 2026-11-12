"""The bracket part of a structured reference: ``[Amount]``, ``[@[Unit price]]``, ``[[#Headers],[Amount]]``.

Excel's grammar, as far as tables need it: a column is a name in brackets (the inner brackets may be left out when
the whole part is one column), a part of the table is ``#Headers``, ``#Data``, ``#All`` or ``#This Row`` (``@`` for
short), a span of columns is ``[[A]:[B]]`` and a bracket, ``#`` or ``'`` inside a column name is written with a
``'`` in front. ``parse_spec`` reads that into the tree's form and ``print_spec`` writes it one canonical way, so
that a document means the same however a formula was typed (E6.5)."""

from __future__ import annotations

import re

ITEMS = {"#headers": "#Headers", "#data": "#Data", "#all": "#All", "#this row": "#This Row"}
THIS_ROW = "#This Row"
_PLAIN = re.compile(r"[^\W]+(?:[.][^\W]+)*", re.UNICODE)  # a column name that needs no brackets after an "@"
_SPECIAL = re.compile(r"""(['\[\]#])""")


class SpecError(ValueError):
    """The bracket part is not one a table understands; the message says what is wrong with it."""


def _unescape(text: str) -> str:
    return re.sub(r"'(.)", r"\1", text, flags=re.DOTALL)


def _escape(name: str) -> str:
    return _SPECIAL.sub(r"'\1", name)


def _atom(text: str) -> tuple[str, str]:
    """``("item", "#Headers")`` or ``("column", "Amount")`` for the text of one bracketed (or bare) part."""
    text = text.strip()
    if text.startswith("#"):
        item = ITEMS.get(text.casefold())
        if item is None:
            raise SpecError(f"a table has no part called {text!r}")
        return "item", item
    name = _unescape(text)
    if not name:
        raise SpecError("a column needs a name")
    return "column", name


def _bracketed(inner: str) -> list[tuple[str, str, str]]:
    """The ``[..]`` parts of ``inner`` with the ``,`` or ``:`` in front of each: ``(separator, kind, text)``."""
    found: list[tuple[str, str, str]] = []
    at, separator = 0, ""
    while at < len(inner):
        if inner[at].isspace():
            at += 1
            continue
        if inner[at] != "[":
            raise SpecError(f"unexpected {inner[at]!r} between the brackets")
        end = at + 1
        while end < len(inner) and inner[end] != "]":
            end += 2 if inner[end] == "'" else 1
        if end >= len(inner):
            raise SpecError("a bracket is not closed")
        kind, text = _atom(inner[at + 1 : end])
        found.append((separator, kind, text))
        at = end + 1
        while at < len(inner) and inner[at].isspace():
            at += 1
        if at < len(inner):
            if inner[at] not in ",:":
                raise SpecError(f"unexpected {inner[at]!r} between the brackets")
            separator = inner[at]
            at += 1
            if at >= len(inner):
                raise SpecError("a part is missing after the last separator")
    return found


def parse_spec(body: str) -> tuple[tuple[str, ...], str | None, str | None]:
    """``(items, first column, last column)`` for ``body``, the brackets included (``"[@Amount]"``)."""
    inner = body[1:-1]
    items: list[str] = []
    if inner.startswith("@"):
        items.append(THIS_ROW)
        inner = inner[1:]
        if not inner.strip():
            raise SpecError("a column needs a name after @")
        if not inner.lstrip().startswith("["):
            kind, text = _atom(inner)
            if kind != "column":
                raise SpecError("@ is followed by the name of a column")
            return (THIS_ROW,), text, None
    if inner.lstrip().startswith("["):
        parts = _bracketed(inner)
    elif inner.strip():
        parts = [("", *_atom(inner))]
    else:
        raise SpecError("a table reference needs a column or a part of the table")
    columns, span = _columns(parts, items)
    return tuple(dict.fromkeys(items)), (columns[0] if columns else None), (columns[1] if span else None)


def _columns(parts: list[tuple[str, str, str]], items: list[str]) -> tuple[list[str], bool]:
    """The columns of the parts (the parts of the table go to ``items``), and whether they are a span."""
    columns: list[str] = []
    span = False
    for separator, kind, text in parts:
        if kind == "item":
            if separator == ":":
                raise SpecError("a span runs between columns, not parts of the table")
            items.append(text)
            continue
        if columns and separator != ":":
            raise SpecError("name one column, or a span of columns with a colon")
        if len(columns) == 2:
            raise SpecError("a span has two ends")
        span = span or separator == ":"
        columns.append(text)
    if span and len(columns) != 2:
        raise SpecError("a span has two ends")
    return columns, span


def print_spec(items: tuple[str, ...], first: str | None, last: str | None) -> str:
    """The bracket part of a reference in its canonical spelling."""
    if items == (THIS_ROW,) and first is not None and last is None:
        return f"[@{_escape(first)}]" if _PLAIN.fullmatch(first) else f"[@[{_escape(first)}]]"
    if not items and first is not None and last is None:
        return f"[{_escape(first)}]"
    parts = [f"[{item}]" for item in items]
    if first is not None:
        parts.append(f"[{_escape(first)}]" + (f":[{_escape(last)}]" if last is not None else ""))
    if len(parts) == 1 and not items[1:] and first is None:
        return parts[0]
    if len(parts) == 1:
        return f"[{parts[0]}]"
    return "[" + ",".join(parts) + "]"
