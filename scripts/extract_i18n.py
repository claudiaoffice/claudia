"""Collect every translatable string into one POT template (E5.7, D31): the groundwork for a single source of
translations, before any string has actually moved into it.

``uv run python scripts/extract_i18n.py``          regenerate ``po/claudia.pot``
``uv run python scripts/extract_i18n.py --check``  fail if the checked-in file would change (the CI gate)

Two call shapes are collected, by two different techniques:

* Python: ``_("...")`` (the GNU gettext convention; ``install_translation`` in ``clients/shell/i18n.py`` binds
  ``_`` process-wide). Found with the ``ast`` module, so string concatenation, f-strings and anything else that is
  not one plain string literal is reported, not silently skipped: a translator cannot work from a format that is
  built at runtime, so that is a mistake to fix in the source, not a string to lose quietly.
* Web (TypeScript/Vue): ``t("...")`` (``createTranslator`` in ``web/app/lib/i18n.ts``). Found with a regular
  expression, not a real parser (there is no TypeScript/Vue parser in this project's own dependencies to reach for);
  it accepts the one plain string literal shape actual calls use today and otherwise reports the call so it is
  fixed by hand rather than silently dropped, the same stance as the Python side.

Nothing in the tree calls either one yet (D31's groundwork precedes moving any string), so an (almost) header-only
``claudia.pot`` is the expected, correct output today — the mechanism is what this proves, not a catalogue.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POT_PATH = ROOT / "po" / "claudia.pot"

# Where each extractor looks. claudia-core is deliberately absent: the kernel stays dependency-free and
# catalog-agnostic (test_purity.py), so it must never grow a call this script would find.
PY_DIRS = (
    "packages/claudia-server/src",
    "packages/claudia-computes/src",
    "packages/claudia-composes/src",
    "packages/claudia-creates/src",
    "clients/linux/src",
)
WEB_DIRS = ("web/app",)
WEB_SUFFIXES = {".ts", ".vue"}

HEADER = """\
msgid ""
msgstr ""
"Project-Id-Version: claudia\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"""


@dataclass(frozen=True)
class Problem:
    """A call this script could not turn into a plain ``msgid``: reported, not silently dropped."""

    path: Path
    line: int
    reason: str

    def __str__(self) -> str:
        return f"{self.path.relative_to(ROOT)}:{self.line}: {self.reason}"


def _existing_dirs(names: tuple[str, ...]) -> list[Path]:
    return [p for p in (ROOT / name for name in names) if p.is_dir()]


def _call_arg_string(call: ast.Call) -> str | None:
    """The plain string literal of a call's one positional argument, or ``None`` if it is not that simple shape
    (no args, more than one, a keyword, or anything other than a string constant — f-strings included: an
    ``ast.JoinedStr`` is not an ``ast.Constant`` and so is correctly rejected here)."""
    if len(call.args) != 1 or call.keywords:
        return None
    (arg,) = call.args
    return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None


def extract_python(path: Path) -> tuple[dict[str, list[str]], list[Problem]]:
    """``_("...")`` calls in one file: ``{msgid: [occurrence, ...]}`` and anything that looked like a call but
    was not one plain string literal."""
    found: dict[str, list[str]] = {}
    problems: list[Problem] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_"):
            continue
        msgid = _call_arg_string(node)
        occurrence = f"{path.relative_to(ROOT)}:{node.lineno}"
        if msgid is None:
            problems.append(Problem(path, node.lineno, "_(...) is not a single plain string literal"))
        else:
            found.setdefault(msgid, []).append(occurrence)
    return found, problems


# A call to `t(` not preceded by a letter, digit, underscore or dot (so not `format(` or `obj.t(`), whose one
# argument is a single-quoted or double-quoted string with no unescaped quote of its own kind inside it.
_T_CALL = re.compile(r"(?<![\w.])t\(\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')\s*[,)]")

# A JS/TS string, template or comment, or an HTML/Vue comment — in that preference order, so a `//` or `/*` inside
# a string is never mistaken for the start of a comment.
_STRING_OR_COMMENT = re.compile(
    r'"(?:[^"\\]|\\.)*"' r"|'(?:[^'\\]|\\.)*'" r"|`(?:[^`\\]|\\.)*`" r"|/\*.*?\*/" r"|//[^\n]*" r"|<!--.*?-->",
    re.DOTALL,
)


def _without_comments(text: str) -> str:
    """``text`` with every comment blanked out to same-length whitespace (so line numbers do not shift) and every
    string literal left untouched. Without this, a ``t(...)`` written as an *example* in a docstring or a doc
    comment — exactly what this module's own docstring and ``web/app/lib/i18n.ts`` have — would be extracted as
    if it were a real call."""

    def blank(match: re.Match[str]) -> str:
        found = match.group()
        return found if found[0] in "\"'`" else re.sub(r"[^\n]", " ", found)

    return _STRING_OR_COMMENT.sub(blank, text)


def extract_web(path: Path) -> tuple[dict[str, list[str]], list[Problem]]:
    """``t("...")`` calls in one ``.ts``/``.vue`` file, by regular expression (see the module docstring)."""
    found: dict[str, list[str]] = {}
    problems: list[Problem] = []
    text = _without_comments(path.read_text(encoding="utf-8"))
    for match in re.finditer(r"(?<![\w.])t\(", text):
        line = text.count("\n", 0, match.start()) + 1
        literal_match = _T_CALL.match(text, match.start())
        if literal_match is None:
            problems.append(Problem(path, line, "t(...) is not a single plain string literal"))
            continue
        msgid = ast.literal_eval(literal_match.group(1))
        found.setdefault(msgid, []).append(f"{path.relative_to(ROOT)}:{line}")
    return found, problems


def collect() -> tuple[dict[str, list[str]], list[Problem]]:
    """Every ``msgid`` found anywhere, with every place it occurs, and every call that could not be read."""
    catalog: dict[str, list[str]] = {}
    problems: list[Problem] = []

    def merge(found: dict[str, list[str]]) -> None:
        for msgid, occurrences in found.items():
            catalog.setdefault(msgid, []).extend(occurrences)

    for base in _existing_dirs(PY_DIRS):
        for path in sorted(base.rglob("*.py")):
            found, found_problems = extract_python(path)
            merge(found)
            problems.extend(found_problems)
    for base in _existing_dirs(WEB_DIRS):
        for path in sorted(base.rglob("*")):
            if path.suffix in WEB_SUFFIXES and path.is_file():
                found, found_problems = extract_web(path)
                merge(found)
                problems.extend(found_problems)
    return catalog, problems


def _po_string(value: str) -> str:
    """A Python string as one double-quoted ``.po`` string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def render_pot(catalog: dict[str, list[str]]) -> str:
    """The ``.pot`` text: the header, then one entry per ``msgid``, sorted so the output is deterministic."""
    parts = [HEADER]
    for msgid in sorted(catalog):
        occurrences = " ".join(sorted(catalog[msgid]))
        parts.append(f'\n#: {occurrences}\nmsgid {_po_string(msgid)}\nmsgstr ""\n')
    return "".join(parts)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="fail if po/claudia.pot would change, instead of writing it"
    )
    args = parser.parse_args(argv)

    catalog, problems = collect()
    for problem in problems:
        print(f"cannot extract: {problem}", file=sys.stderr)
    rendered = render_pot(catalog)

    if args.check:
        current = POT_PATH.read_text(encoding="utf-8") if POT_PATH.is_file() else None
        if current != rendered:
            print(
                f"{POT_PATH.relative_to(ROOT)} is out of date — run scripts/extract_i18n.py and commit it",
                file=sys.stderr,
            )
            return 1
    else:
        POT_PATH.parent.mkdir(parents=True, exist_ok=True)
        POT_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {POT_PATH.relative_to(ROOT)} ({len(catalog)} msgid(s))")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
