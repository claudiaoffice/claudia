"""The formulas of a spreadsheet, as Excel writes them and as OpenFormula does (D413).

The model's formulas are Excel's language (D12): ``=SUM(A1:A3,'My Sheet'!B2)``. An ods file holds them in
OpenFormula, the language of ODF part 2: ``of:=SUM([.A1:.A3];[$'My Sheet'.B2])``. The two are the same expressions
with other punctuation, and a few functions have another name. What a program that is not this one writes was
checked by having LibreOffice 24.2 convert a workbook with every function the model implements, so this is the
dialect it reads and writes, not only the one the standard describes.

* :func:`to_openformula` turns the model's text into the text of a ``table:formula`` attribute.
* :func:`from_openformula` turns that attribute into the model's text, for the functions the model implements.

Both raise :class:`Untranslatable` for what the other language cannot say, with a reason a person can read as a
code (``function``, ``reference``, ``operator``, ``dialect``, ``syntax``): the converter then writes or keeps the
cell's *value* and counts a loss, so a cell is never wrong, only less live (D408). Nothing is guessed: a function
the model does not have, a reference to another file, a union or an intersection of ranges, a name defined in the
file, and a function that means something else in OpenFormula (``CEILING`` without a prefix has a mode argument
and other rounding of negatives) are all untranslatable.

The conversion works on tokens, not on a syntax tree: it changes punctuation and names and does not need to
understand a formula the model could not read.
"""

from __future__ import annotations

import re
from collections.abc import Container

#: The functions Excel added after ODF 1.2 and ``CEILING``/``FLOOR``, which ODF has with another meaning. A
#: program writes these in OpenFormula with the prefix, and so does this one.
EXCEL_ONLY = frozenset(
    {
        "CEILING",
        "CONCAT",
        "FLOOR",
        "IFS",
        "MAXIFS",
        "MINIFS",
        "STDEV.P",
        "SWITCH",
        "TEXTJOIN",
        "VAR.P",
        "XLOOKUP",
        "XMATCH",
    }
)
_PREFIX = "COM.MICROSOFT."
#: Names that Excel files carry for functions newer than the file format (``_xlfn.CONCAT``): not part of the name.
_EXCEL_PREFIXES = ("_xlfn.", "_xlws.")
#: Functions that mean something else in OpenFormula without the prefix: not translatable that way.
_OTHER_MEANING = frozenset({"CEILING", "FLOOR"})


class Untranslatable(Exception):
    """What one language cannot say in the other. ``reason`` is a code (``function``, ``reference``, ``operator``,
    ``dialect``, ``syntax``) and ``detail`` says what, for example the name of the function."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


_CELL = r"\$?[A-Za-z]{1,3}\$?\d+"
_COLUMN = r"\$?[A-Za-z]{1,3}"
_ROW = r"\$?\d+"
_SHEET = r"(?:'(?:[^']|'')+'|[A-Za-z_\u0080-￿][\w.\u0080-￿]*)"
_EXCEL_REF = re.compile(
    rf"(?:(?P<sheet>{_SHEET})!)?(?:(?P<a>{_CELL})(?::(?P<b>{_CELL}))?|(?P<ca>{_COLUMN}):(?P<cb>{_COLUMN})"
    rf"|(?P<ra>{_ROW}):(?P<rb>{_ROW}))(?![\w.(])"
)
_NUMBER = re.compile(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
_STRING = re.compile(r'"(?:[^"]|"")*"')
_ERROR = re.compile(r"#(?:REF!|DIV/0!|N/A|NAME\?|NULL!|NUM!|VALUE!)")
_NAME = re.compile(r"[A-Za-z_\\\u0080-￿][\w.\u0080-￿]*")
_SPACE = re.compile(r"\s+")
_OPERATOR = re.compile(r"<>|<=|>=|[-+*/^&=<>%(),;{}:]")


def _quoted(name: str) -> bool:
    return name.startswith("'")


def _plain_sheet(name: str) -> bool:
    """Whether Excel writes the sheet ``name`` without quotes: a word that is not itself a reference."""
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)) and not re.fullmatch(r"[A-Za-z]{1,3}\d+", name)


# -- Excel to OpenFormula --------------------------------------------------------------------------------------------
def _open_reference(match: re.Match[str]) -> str:
    sheet = f"${match['sheet']}" if match["sheet"] else ""
    if match["a"]:
        second = f":.{match['b']}" if match["b"] else ""
        return f"[{sheet}.{match['a']}{second}]"
    if match["ca"]:
        return f"[{sheet}.{match['ca']}:.{match['cb']}]"
    return f"[{sheet}.{match['ra']}:.{match['rb']}]"


def _operand_end(kind: str, text: str) -> bool:
    return kind in ("ref", "number", "string", "error", "name") or text in (")", "}", "%")


def _operand_start(kind: str, text: str) -> bool:
    return kind in ("ref", "number", "string", "error", "name") or text in ("(", "{")


def to_openformula(formula: str) -> str:
    """``formula`` (the model's text, with or without its ``=``) as the value of a ``table:formula`` attribute:
    ``of:=SUM([.A1:.A3];2)``. :class:`Untranslatable` for what OpenFormula cannot say (a union or an intersection of
    ranges)."""
    text = formula.strip()
    body = text[1:] if text.startswith("=") else text
    out: list[str] = []
    stack: list[str] = []  # "call", "group" or "array", innermost last
    previous: tuple[str, str] | None = None  # the last token that is not white space: kind and text
    pending_space = False
    position = 0
    while position < len(body):
        match = _SPACE.match(body, position)
        if match:
            out.append(match.group())
            pending_space = previous is not None
            position = match.end()
            continue
        kind, token, written, end = _excel_token(body, position, stack)
        if pending_space and previous is not None and _operand_end(*previous) and _operand_start(kind, token):
            raise Untranslatable("operator", "intersection")
        pending_space = False
        out.append(written)
        previous = (kind, token)
        position = end
    if stack:
        raise Untranslatable("syntax", "a bracket is not closed")
    return "of:=" + "".join(out)


def _excel_token(body: str, position: int, stack: list[str]) -> tuple[str, str, str, int]:
    """The token at ``position``: its kind, its text, what it is in OpenFormula and where it ends. Brackets are
    kept in ``stack``, because a comma means one thing between the arguments of a function and another between
    the rows and columns of an array."""
    for pattern, kind in ((_STRING, "string"), (_ERROR, "error")):
        found = pattern.match(body, position)
        if found:
            return kind, found.group(), found.group(), found.end()
    found = _EXCEL_REF.match(body, position)
    if found:
        return "ref", found.group(), _open_reference(found), found.end()
    found = _NUMBER.match(body, position)
    if found:
        return "number", found.group(), found.group(), found.end()
    found = _NAME.match(body, position)
    if found:
        name, end = found.group(), found.end()
        if body.startswith("(", end):
            return "name", name, _open_function(name), end
        if name.upper() in ("TRUE", "FALSE"):
            if stack and stack[-1] == "array":
                raise Untranslatable("syntax", "a logical value in an inline array")
            return "name", name, f"{name.upper()}()", end
        return "name", name, name, end
    found = _OPERATOR.match(body, position)
    if not found:
        raise Untranslatable("syntax", f"{body[position]!r} is not part of a formula")
    token = found.group()
    return "op", token, _open_operator(token, body, found.end(), stack), found.end()


def _open_function(name: str) -> str:
    plain = name
    for prefix in _EXCEL_PREFIXES:
        if plain.lower().startswith(prefix):
            plain = plain[len(prefix) :]
    if plain.upper() in EXCEL_ONLY:
        return _PREFIX + plain.upper()
    return plain


def _open_operator(token: str, body: str, end: int, stack: list[str]) -> str:
    if token == "(":
        previous_char = body[: end - 1].rstrip()[-1:]
        stack.append("call" if previous_char.isalnum() or previous_char in "._" else "group")
        return token
    if token == "{":
        stack.append("array")
        return token
    if token in (")", "}"):
        if not stack:
            raise Untranslatable("syntax", "a bracket is closed that was not opened")
        stack.pop()
        return token
    inside = stack[-1] if stack else None
    if token == ",":
        if inside == "call":
            return ";"
        if inside == "array":
            return ";"
        raise Untranslatable("operator", "union")
    if token == ";":
        if inside == "array":
            return "|"
        raise Untranslatable("syntax", "a semicolon outside an array")
    return token


# -- OpenFormula to Excel --------------------------------------------------------------------------------------------
_ODF_SHEET = r"(?:'(?:[^']|'')+'|[^.$'\[\]: ]+)"
_ODF_CELL = r"\$?[A-Za-z]{1,3}\$?\d+|\$?[A-Za-z]{1,3}|\$?\d+"


def _odf_end(label: str) -> str:
    """One end of an OpenFormula range, ``$Sheet.A1`` or ``.A1``, with the groups ``<label>_sheet`` and ``_cell``."""
    return rf"(?:(?P<{label}_sheet>\$?{_ODF_SHEET}))?\.(?P<{label}_cell>{_ODF_CELL})"


_ODF_REF = re.compile(rf"^{_odf_end('first')}(?::{_odf_end('second')})?$")
_ODF_BRACKET = re.compile(r"\[(?:[^\]'\"]|'(?:[^']|'')*')*\]")
_PLAIN_CELL = re.compile(r"\$?[A-Za-z]{1,3}\$?\d+")
_COLUMN_ONLY = re.compile(r"\$?[A-Za-z]{1,3}")


def from_openformula(attribute: str, functions: Container[str] | None = None) -> str:
    """The model's text (with its ``=``) for the value of a ``table:formula`` attribute. ``functions`` holds the
    names of the functions the model implements (upper case): a formula that calls another is
    :class:`Untranslatable`, because the model would show ``#NAME?`` where the file has a number. With none given
    every function is accepted."""
    prefix, _, body = attribute.strip().partition(":=")
    if not _ or prefix != "of":
        raise Untranslatable("dialect", prefix if _ else "no language named")
    out: list[str] = []
    stack: list[str] = []
    position = 0
    while position < len(body):
        match = _SPACE.match(body, position)
        if match:
            out.append(match.group())
            position = match.end()
            continue
        written, position = _odf_token(body, position, stack, functions)
        out.append(written)
    if stack:
        raise Untranslatable("syntax", "a bracket is not closed")
    return "=" + "".join(out)


def _odf_token(body: str, position: int, stack: list[str], functions: Container[str] | None) -> tuple[str, int]:
    for pattern in (_STRING, _ERROR):
        found = pattern.match(body, position)
        if found:
            return found.group(), found.end()
    if body[position] == "[":
        found = _ODF_BRACKET.match(body, position)
        if not found:
            raise Untranslatable("syntax", "a reference is not closed")
        return _excel_reference(found.group()[1:-1]), found.end()
    found = _NUMBER.match(body, position)
    if found:
        return found.group(), found.end()
    found = _NAME.match(body, position)
    if found:
        return _excel_name(found.group(), body.startswith("(", found.end()), functions), found.end()
    return _odf_operator(body, position, stack)


def _excel_reference(inside: str) -> str:
    if "#REF!" in inside:
        return "#REF!"
    found = _ODF_REF.match(inside)
    if not found:
        raise Untranslatable("reference", "a reference of another kind (another file, or a name)")
    first, second = found["first_sheet"], found["second_sheet"]
    if second is not None and second.lstrip("$") != (first or "").lstrip("$"):
        raise Untranslatable("reference", "a range over several sheets")
    cell, other = found["first_cell"], found["second_cell"]
    sheet = _excel_sheet(first) if first else ""
    if other is None:
        if not _PLAIN_CELL.fullmatch(cell):
            raise Untranslatable("reference", "a whole row or column given alone")
        return sheet + cell
    return f"{sheet}{cell}:{other}"


def _excel_sheet(written: str) -> str:
    name = written.lstrip("$")
    inner = name[1:-1].replace("''", "'") if _quoted(name) else name
    if _plain_sheet(inner):
        return f"{inner}!"
    return "'" + inner.replace("'", "''") + "'!"


def _excel_name(name: str, is_function: bool, functions: Container[str] | None) -> str:
    if not is_function:
        if name.upper() in ("TRUE", "FALSE"):
            return name.upper()
        raise Untranslatable("reference", f"the name {name}, which the file defines")
    plain = name
    if plain.upper().startswith(_PREFIX):
        plain = plain[len(_PREFIX) :]
    else:
        for prefix in _EXCEL_PREFIXES:
            if plain.lower().startswith(prefix):
                plain = plain[len(prefix) :]
        if plain.upper() in _OTHER_MEANING:
            raise Untranslatable("function", f"{plain.upper()} (OpenFormula's own, which rounds negatives otherwise)")
        if plain.upper().split(".")[0] in ("ORG", "COM", "LIBREOFFICE", "OOO") and "." in plain:
            raise Untranslatable("function", plain)
    upper = plain.upper()
    if functions is not None and upper not in functions:
        raise Untranslatable("function", upper)
    return upper


def _odf_operator(body: str, position: int, stack: list[str]) -> tuple[str, int]:
    found = _OPERATOR.match(body, position)
    char = body[position]
    if char in "~!":
        raise Untranslatable("operator", "union" if char == "~" else "intersection")
    if char == "|":
        if not stack or stack[-1] != "array":
            raise Untranslatable("syntax", "a row separator outside an array")
        return ";", position + 1
    if not found:
        raise Untranslatable("syntax", f"{char!r} is not part of a formula")
    token = found.group()
    if token == "(":
        previous = body[:position].rstrip()[-1:]
        stack.append("call" if previous.isalnum() or previous in "._" else "group")
    elif token == "{":
        stack.append("array")
    elif token in (")", "}"):
        if not stack:
            raise Untranslatable("syntax", "a bracket is closed that was not opened")
        stack.pop()
    elif token == ";":
        inside = stack[-1] if stack else None
        if inside == "array":
            return ",", found.end()
        if inside == "call":
            return ",", found.end()
        raise Untranslatable("syntax", "a semicolon outside a function")
    elif token == ",":
        raise Untranslatable("syntax", "a comma is not a separator in OpenFormula")
    return token, found.end()
