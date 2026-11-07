"""The pseudo-locale generator (E5.7, D31): a mechanical "translation" that makes a hard-coded string, a layout
that assumes English-length text, or a mangled placeholder all visible at a glance, without needing a real
translator yet.
"""

import importlib.util
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "make_pseudolocale", Path(__file__).parent.parent / "scripts" / "make_pseudolocale.py"
)
make_pseudolocale = importlib.util.module_from_spec(SPEC)
sys.modules["make_pseudolocale"] = make_pseudolocale
SPEC.loader.exec_module(make_pseudolocale)


def test_pseudo_accents_every_vowel():
    assert make_pseudolocale.pseudo("Save") == "[Sàvé~~]"


def test_pseudo_pads_by_about_forty_percent():
    out = make_pseudolocale.pseudo("Cancel")  # len 6 -> pad = round(6 * 0.4) = 2 tildes before the closing bracket
    assert out == "[Càncél~~]"
    assert out.count("~") == round(len("Cancel") * 0.4)


def test_pseudo_leaves_placeholders_untouched():
    assert "{name}" in make_pseudolocale.pseudo("Hello {name}")
    out = make_pseudolocale.pseudo("Hello {name}")
    assert out.startswith("[") and out.endswith("]") and "{name}" in out
    # only the English fragments around the placeholder are accented, never the placeholder's own name
    assert "{nàmé}" not in out


def test_pseudo_of_empty_string_is_just_brackets():
    assert make_pseudolocale.pseudo("") == "[]"


def test_render_pseudo_po_fills_in_every_entry_and_skips_the_header():
    pot = 'msgid ""\nmsgstr ""\n"Project-Id-Version: claudia\\n"\n\n#: a.py:1\nmsgid "Save"\nmsgstr ""\n'
    rendered = make_pseudolocale.render_pseudo_po(pot)
    assert 'msgid ""\nmsgstr ""\n"Project-Id-Version: claudia\\n"\n' in rendered  # header untouched
    assert "#: a.py:1\n" in rendered  # the comment survives
    assert f'msgid "Save"\nmsgstr {make_pseudolocale._po_string(make_pseudolocale.pseudo("Save"))}' in rendered


def test_render_pseudo_po_round_trips_an_escaped_msgid():
    pot = 'msgid "say \\"hi\\""\nmsgstr ""\n'
    rendered = make_pseudolocale.render_pseudo_po(pot)
    assert 'msgid "say \\"hi\\""' in rendered  # the msgid line itself is carried over unchanged
    expected_msgstr = make_pseudolocale._po_string(make_pseudolocale.pseudo('say "hi"'))
    assert f"msgstr {expected_msgstr}" in rendered


def test_render_pseudo_po_of_a_header_only_pot_changes_nothing():
    header_only = 'msgid ""\nmsgstr ""\n"Project-Id-Version: claudia\\n"\n'
    assert make_pseudolocale.render_pseudo_po(header_only) == header_only


def test_main_fails_cleanly_when_the_pot_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(make_pseudolocale, "ROOT", tmp_path)
    monkeypatch.setattr(make_pseudolocale, "POT_PATH", tmp_path / "claudia.pot")
    monkeypatch.setattr(make_pseudolocale, "PSEUDO_PO_PATH", tmp_path / "xx.po")
    assert make_pseudolocale.main([]) == 1
    assert "no such file" in capsys.readouterr().err


def test_main_writes_the_pseudo_po(tmp_path, monkeypatch):
    pot_path = tmp_path / "claudia.pot"
    pot_path.write_text('msgid ""\nmsgstr ""\n\n#: a.py:1\nmsgid "Save"\nmsgstr ""\n', encoding="utf-8")
    out_path = tmp_path / "xx.po"
    monkeypatch.setattr(make_pseudolocale, "ROOT", tmp_path)
    monkeypatch.setattr(make_pseudolocale, "POT_PATH", pot_path)
    monkeypatch.setattr(make_pseudolocale, "PSEUDO_PO_PATH", out_path)
    assert make_pseudolocale.main([]) == 0
    assert 'msgid "Save"' in out_path.read_text(encoding="utf-8")
