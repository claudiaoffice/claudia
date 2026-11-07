"""The i18n extractor (E5.7, D31): collecting ``_("...")``/``t("...")`` calls into one POT template, and refusing
to silently drop a call it cannot read as a plain string.
"""

import importlib.util
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "extract_i18n", Path(__file__).parent.parent / "scripts" / "extract_i18n.py"
)
extract_i18n = importlib.util.module_from_spec(SPEC)
sys.modules["extract_i18n"] = extract_i18n
SPEC.loader.exec_module(extract_i18n)


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------------------------------------------- Python
def test_extract_python_finds_one_plain_call(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    path = write(tmp_path, "a.py", 'greet = _("Hello")\n')
    found, problems = extract_i18n.extract_python(path)
    assert found == {"Hello": ["a.py:1"]}
    assert problems == []


def test_extract_python_merges_occurrences_of_the_same_msgid(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    path = write(tmp_path, "a.py", '_("Save")\n_("Save")\n')
    found, _ = extract_i18n.extract_python(path)
    assert found == {"Save": ["a.py:1", "a.py:2"]}


def test_extract_python_ignores_calls_that_are_not_the_gettext_underscore(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    path = write(tmp_path, "a.py", 'foo("not this")\nobj._("not an attribute call")\n')
    found, problems = extract_i18n.extract_python(path)
    assert found == {} and problems == []


def test_extract_python_reports_a_call_it_cannot_read_as_one_plain_string(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    for bad in ('_(f"Hello {name}")\n', '_("a" + "b")\n', "_()\n", '_("a", "b")\n', '_("a", key="b")\n'):
        path = write(tmp_path, "a.py", bad)
        found, problems = extract_i18n.extract_python(path)
        assert found == {}, bad
        assert len(problems) == 1 and problems[0].line == 1, bad


# ------------------------------------------------------------------------------------------------------------ web
def test_extract_web_finds_single_and_double_quoted_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    path = write(tmp_path, "a.ts", "t('Save')\nt(\"Cancel\")\n")
    found, problems = extract_i18n.extract_web(path)
    assert found == {"Save": ["a.ts:1"], "Cancel": ["a.ts:2"]}
    assert problems == []


def test_extract_web_accepts_a_second_vars_argument(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    path = write(tmp_path, "a.ts", "t('Hello {name}', { name })\n")
    found, problems = extract_i18n.extract_web(path)
    assert found == {"Hello {name}": ["a.ts:1"]} and problems == []


def test_extract_web_does_not_match_an_unrelated_call_ending_in_t(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    path = write(tmp_path, "a.ts", "format('x')\nobj.t('x')\n")
    found, problems = extract_i18n.extract_web(path)
    assert found == {} and problems == []


def test_extract_web_ignores_an_example_call_written_inside_a_comment(tmp_path, monkeypatch):
    """The bug this guards against: `web/app/lib/i18n.ts`'s own doc comment shows `t('Save')` as an example, which
    must not be mistaken for a real call (nor must a `//` or `/*` inside an ordinary string start a comment)."""
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    path = write(
        tmp_path,
        "a.ts",
        "/** e.g. `t('Save')` or `t(\"Cancel\")` */\n"
        "// also t('Skip')\n"
        "const url = 'https://example.com' // not a comment starter inside the string above\n"
        "t('Real')\n"
        "<!-- t('Ignored too') -->\n",
    )
    found, problems = extract_i18n.extract_web(path)
    assert found == {"Real": ["a.ts:4"]}
    assert problems == []


def test_extract_web_reports_a_call_it_cannot_read_as_one_plain_string(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    path = write(tmp_path, "a.ts", "t(`Hello ${name}`)\nt(msgid)\n")
    found, problems = extract_i18n.extract_web(path)
    assert found == {}
    assert [p.line for p in problems] == [1, 2]


# --------------------------------------------------------------------------------------------------------- the POT
def test_render_pot_is_sorted_and_deterministic():
    catalog = {"Save": ["b.py:1"], "Cancel": ["a.py:3", "a.py:1"]}
    rendered = extract_i18n.render_pot(catalog)
    assert rendered == extract_i18n.render_pot(catalog)  # same input, same bytes
    assert rendered.index('msgid "Cancel"') < rendered.index('msgid "Save"')  # sorted by msgid
    assert "#: a.py:1 a.py:3" in rendered  # occurrences sorted too
    assert rendered.startswith(extract_i18n.HEADER)


def test_po_string_escapes_backslashes_quotes_and_newlines():
    assert extract_i18n._po_string('say "hi"\\now') == '"say \\"hi\\"\\\\now"'


def test_render_pot_of_an_empty_catalog_is_just_the_header():
    assert extract_i18n.render_pot({}) == extract_i18n.HEADER


# --------------------------------------------------------------------------------------------------------- --check
def test_check_passes_when_the_pot_on_disk_already_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    monkeypatch.setattr(extract_i18n, "POT_PATH", tmp_path / "po" / "claudia.pot")
    monkeypatch.setattr(extract_i18n, "PY_DIRS", ())
    monkeypatch.setattr(extract_i18n, "WEB_DIRS", ())
    extract_i18n.POT_PATH.parent.mkdir(parents=True)
    extract_i18n.POT_PATH.write_text(extract_i18n.HEADER, encoding="utf-8")
    assert extract_i18n.main(["--check"]) == 0


def test_check_fails_when_the_pot_on_disk_is_stale(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    monkeypatch.setattr(extract_i18n, "POT_PATH", tmp_path / "po" / "claudia.pot")
    monkeypatch.setattr(extract_i18n, "PY_DIRS", ())
    monkeypatch.setattr(extract_i18n, "WEB_DIRS", ())
    extract_i18n.POT_PATH.parent.mkdir(parents=True)
    extract_i18n.POT_PATH.write_text("stale\n", encoding="utf-8")
    assert extract_i18n.main(["--check"]) == 1
    assert "out of date" in capsys.readouterr().err


def test_check_fails_when_the_pot_does_not_exist_yet(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    monkeypatch.setattr(extract_i18n, "POT_PATH", tmp_path / "po" / "claudia.pot")
    monkeypatch.setattr(extract_i18n, "PY_DIRS", ())
    monkeypatch.setattr(extract_i18n, "WEB_DIRS", ())
    assert extract_i18n.main(["--check"]) == 1


def test_main_writes_the_pot_and_exits_nonzero_on_an_unreadable_call(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_i18n, "ROOT", tmp_path)
    monkeypatch.setattr(extract_i18n, "POT_PATH", tmp_path / "po" / "claudia.pot")
    src = tmp_path / "pkg"
    src.mkdir()
    monkeypatch.setattr(extract_i18n, "PY_DIRS", ("pkg",))
    monkeypatch.setattr(extract_i18n, "WEB_DIRS", ())
    write(src, "a.py", '_("Save")\n_(f"bad {1}")\n')
    assert extract_i18n.main([]) == 1  # a problem was found: exits non-zero even though it wrote the file
    assert 'msgid "Save"' in extract_i18n.POT_PATH.read_text(encoding="utf-8")
