"""Bringing a translation up to date with the template (E5.7, D31, D148): what ``msgmerge`` does, without GNU
gettext."""

import importlib.util
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("update_po", Path(__file__).parent.parent / "scripts" / "update_po.py")
update_po = importlib.util.module_from_spec(SPEC)
sys.modules["update_po"] = update_po
SPEC.loader.exec_module(update_po)

HEADER = 'msgid ""\nmsgstr ""\n"Project-Id-Version: claudia\\n"\n"Content-Type: text/plain; charset=UTF-8\\n"\n'


def template(*entries: tuple[str, str]) -> str:
    return HEADER + "".join(f'\n#: {places}\nmsgid "{msgid}"\nmsgstr ""\n' for places, msgid in entries)


def translation(*entries: tuple[str, str, str]) -> str:
    return HEADER + "".join(f'\n#: {places}\nmsgid "{msgid}"\nmsgstr "{msgstr}"\n' for places, msgid, msgstr in entries)


def test_keeps_what_is_translated():
    merged = update_po.merge(template(("a.vue:1", "Save")), translation(("a.vue:1", "Save", "Speichern")))
    assert 'msgid "Save"\nmsgstr "Speichern"\n' in merged


def test_adds_a_new_string_untranslated():
    merged = update_po.merge(
        template(("a.vue:1", "Save"), ("b.vue:2", "Open")), translation(("a.vue:1", "Save", "Speichern"))
    )
    assert 'msgid "Open"\nmsgstr ""\n' in merged


def test_drops_a_string_the_code_no_longer_has():
    merged = update_po.merge(
        template(("a.vue:1", "Save")), translation(("a.vue:1", "Save", "Speichern"), ("c.vue:3", "Gone", "Weg"))
    )
    assert "Gone" not in merged and "Weg" not in merged


def test_refreshes_the_places_from_the_template():
    merged = update_po.merge(template(("a.vue:9 b.vue:4", "Save")), translation(("a.vue:1", "Save", "Speichern")))
    assert "#: a.vue:9 b.vue:4\nmsgid" in merged
    assert "#: a.vue:1\n" not in merged


def test_follows_the_order_of_the_template_so_a_diff_shows_only_what_changed():
    merged = update_po.merge(
        template(("a:1", "B"), ("a:2", "A")),
        translation(("a:2", "A", "Ä"), ("a:1", "B", "Bé")),
    )
    assert merged.index('msgid "B"') < merged.index('msgid "A"')


def test_keeps_a_translation_with_an_escaped_quote_and_a_newline():
    merged = update_po.merge(
        template(("a:1", 'Say \\"hi\\"\\n')),
        translation(("a:1", 'Say \\"hi\\"\\n', 'Sag \\"hallo\\"\\n')),
    )
    assert 'msgstr "Sag \\"hallo\\"\\n"' in merged


def test_merging_twice_changes_nothing():
    once = update_po.merge(template(("a:1", "Save"), ("a:2", "Open")), translation(("a:1", "Save", "Speichern")))
    assert update_po.merge(template(("a:1", "Save"), ("a:2", "Open")), once) == once


def test_keeps_the_header_of_the_template():
    merged = update_po.merge(template(("a:1", "Save")), "")
    assert merged.startswith(HEADER)


def test_check_fails_for_a_stale_translation_and_writes_nothing(tmp_path, monkeypatch, capsys):
    po_dir = tmp_path / "po"
    po_dir.mkdir()
    (po_dir / "claudia.pot").write_text(template(("a:1", "Save"), ("a:2", "Open")), encoding="utf-8")
    stale = translation(("a:1", "Save", "Speichern"))
    (po_dir / "de.po").write_text(stale, encoding="utf-8")
    monkeypatch.setattr(update_po, "ROOT", tmp_path)
    monkeypatch.setattr(update_po, "PO_DIR", po_dir)
    monkeypatch.setattr(update_po, "POT_PATH", po_dir / "claudia.pot")

    assert update_po.main(["--check"]) == 1
    assert (po_dir / "de.po").read_text(encoding="utf-8") == stale
    assert "de.po is out of date" in capsys.readouterr().err

    assert update_po.main([]) == 0
    assert 'msgid "Open"' in (po_dir / "de.po").read_text(encoding="utf-8")
    assert update_po.main(["--check"]) == 0


def test_the_pseudo_locale_is_left_alone(tmp_path, monkeypatch):
    po_dir = tmp_path / "po"
    po_dir.mkdir()
    (po_dir / "claudia.pot").write_text(template(("a:1", "Save")), encoding="utf-8")
    (po_dir / "de.po").write_text(template(("a:1", "Save")), encoding="utf-8")
    (po_dir / "xx.po").write_text("not even a po file", encoding="utf-8")
    monkeypatch.setattr(update_po, "PO_DIR", po_dir)
    assert [p.name for p in update_po.languages()] == ["de.po"]
