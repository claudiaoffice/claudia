"""Deriving the web client's JSON catalog from a ``.po`` file (E5.7, D31): the one place the two are allowed to
differ in format, never in content.
"""

import importlib.util
import json
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("po_to_json", Path(__file__).parent.parent / "scripts" / "po_to_json.py")
po_to_json = importlib.util.module_from_spec(SPEC)
sys.modules["po_to_json"] = po_to_json
SPEC.loader.exec_module(po_to_json)


def test_parse_po_reads_translated_entries():
    text = '\nmsgid "Save"\nmsgstr "Speichern"\n\nmsgid "Cancel"\nmsgstr "Abbrechen"\n'
    assert po_to_json.parse_po(text) == {"Save": "Speichern", "Cancel": "Abbrechen"}


def test_parse_po_skips_the_header_entry():
    text = 'msgid ""\nmsgstr "Project-Id-Version: claudia\\n"\n\nmsgid "Save"\nmsgstr "Speichern"\n'
    assert po_to_json.parse_po(text) == {"Save": "Speichern"}


def test_parse_po_skips_an_untranslated_entry():
    """A `.pot` (nothing translated yet) must come back as an empty catalog, not one full of msgid == msgid."""
    text = 'msgid "Save"\nmsgstr ""\n\nmsgid "Cancel"\nmsgstr "Abbrechen"\n'
    assert po_to_json.parse_po(text) == {"Cancel": "Abbrechen"}


def test_parse_po_joins_a_multiline_entry():
    text = 'msgid ""\n"Hello "\n"world"\nmsgstr ""\n"Hallo "\n"Welt"\n'
    assert po_to_json.parse_po(text) == {"Hello world": "Hallo Welt"}


def test_parse_po_ignores_comment_and_blank_lines():
    text = '# a translator comment\n#: a.py:1\n\nmsgid "Save"\nmsgstr "Speichern"\n'
    assert po_to_json.parse_po(text) == {"Save": "Speichern"}


def test_parse_po_unescapes_newlines_tabs_quotes_and_backslashes():
    text = 'msgid "a\\nb\\t\\"c\\"\\\\d"\nmsgstr "x\\ny"\n'
    assert po_to_json.parse_po(text) == {'a\nb\t"c"\\d': "x\ny"}


def test_parse_po_of_an_empty_file_is_an_empty_catalog():
    assert po_to_json.parse_po("") == {}


def test_main_writes_the_json_catalog(tmp_path):
    po_file = tmp_path / "de.po"
    po_file.write_text('msgid "Save"\nmsgstr "Speichern"\n', encoding="utf-8")
    out_dir = tmp_path / "out"
    assert po_to_json.main([str(po_file), "de", "--out-dir", str(out_dir)]) == 0
    assert json.loads((out_dir / "de.json").read_text(encoding="utf-8")) == {"Save": "Speichern"}


def test_main_fails_cleanly_on_a_missing_file(tmp_path, capsys):
    assert po_to_json.main([str(tmp_path / "nope.po"), "de", "--out-dir", str(tmp_path)]) == 1
    assert "no such file" in capsys.readouterr().err
