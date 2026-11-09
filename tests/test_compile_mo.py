"""Compiling a ``.po`` catalog into gettext's binary ``.mo`` format, without GNU ``msgfmt`` (E5.7, D31's groundwork,
D160): the one correctness bar that matters is CPython's own ``gettext.GNUTranslations``, the one and only reader
``i18n.install_translation`` ever points at — so most of these tests round-trip through it directly, not just
through this module's own encoding.
"""

import gettext
import importlib.util
import io
import sys
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("compile_mo", Path(__file__).parent.parent / "scripts" / "compile_mo.py")
compile_mo_module = importlib.util.module_from_spec(SPEC)
sys.modules["compile_mo"] = compile_mo_module
SPEC.loader.exec_module(compile_mo_module)


def _read_back(data: bytes) -> gettext.GNUTranslations:
    return gettext.GNUTranslations(io.BytesIO(data))


def test_a_translated_entry_round_trips_through_pythons_own_gettext():
    data = compile_mo_module.compile_mo({"Save": "Speichern"})
    assert _read_back(data).gettext("Save") == "Speichern"


def test_an_umlaut_survives_the_round_trip():
    """The bug a missing header entry causes: CPython's own reader falls back to decoding every string as plain
    ASCII (`self._charset or 'ascii'`) with no header, which crashes outright on the first umlaut."""
    data = compile_mo_module.compile_mo({"Settings": "Einstellungen für Ihr Benutzerkonto"})
    assert _read_back(data).gettext("Settings") == "Einstellungen für Ihr Benutzerkonto"


def test_a_msgid_with_no_translation_in_the_catalog_falls_back_to_itself():
    """`compile_mo` is handed an already-filtered catalog (`po_to_json.parse_po`'s job) -- this just confirms the
    other half: a `.mo` with nothing under a given key leaves `gettext` to fall back to the key itself, the
    correct behaviour for an untranslated string, rather than some other failure."""
    data = compile_mo_module.compile_mo({"Save": "Speichern"})
    assert _read_back(data).gettext("Cancel") == "Cancel"


def test_the_empty_catalog_compiles_to_a_valid_mo():
    data = compile_mo_module.compile_mo({})
    assert _read_back(data).gettext("anything") == "anything"


def test_many_entries_all_round_trip_correctly():
    """Catches an off-by-one in the running byte offset that a one- or two-entry catalog would not expose."""
    catalog = {f"id-{i}": f"wert-{i}-ö" for i in range(50)}
    translations = _read_back(compile_mo_module.compile_mo(catalog))
    for msgid, msgstr in catalog.items():
        assert translations.gettext(msgid) == msgstr


def test_the_header_entry_declares_utf8_so_the_reader_decodes_correctly():
    data = compile_mo_module.compile_mo({})
    assert _read_back(data)._charset == "UTF-8"  # noqa: SLF001 -- the one place this is actually observable


# ------------------------------------------------------------------------------------------------------------ main
def test_main_writes_the_compiled_mo(tmp_path):
    po_file = tmp_path / "de.po"
    po_file.write_text('msgid "Save"\nmsgstr "Speichern"\n', encoding="utf-8")
    locale_dir = tmp_path / "locale"
    assert compile_mo_module.main([str(po_file), "de", "--locale-dir", str(locale_dir)]) == 0
    mo_path = locale_dir / "de" / "LC_MESSAGES" / "claudia.mo"
    assert mo_path.is_file()
    assert _read_back(mo_path.read_bytes()).gettext("Save") == "Speichern"


def test_main_fails_cleanly_on_a_missing_file(tmp_path, capsys):
    assert compile_mo_module.main([str(tmp_path / "nope.po"), "de", "--locale-dir", str(tmp_path)]) == 1
    assert "no such file" in capsys.readouterr().err


def test_check_passes_when_the_mo_on_disk_already_matches(tmp_path):
    po_file = tmp_path / "de.po"
    po_file.write_text('msgid "Save"\nmsgstr "Speichern"\n', encoding="utf-8")
    locale_dir = tmp_path / "locale"
    compile_mo_module.main([str(po_file), "de", "--locale-dir", str(locale_dir)])
    assert compile_mo_module.main([str(po_file), "de", "--locale-dir", str(locale_dir), "--check"]) == 0


def test_check_fails_when_the_mo_on_disk_is_stale(tmp_path, capsys):
    po_file = tmp_path / "de.po"
    po_file.write_text('msgid "Save"\nmsgstr "Speichern"\n', encoding="utf-8")
    locale_dir = tmp_path / "locale"
    compile_mo_module.main([str(po_file), "de", "--locale-dir", str(locale_dir)])
    po_file.write_text('msgid "Save"\nmsgstr "Sichern"\n', encoding="utf-8")  # changed after the .mo was compiled
    assert compile_mo_module.main([str(po_file), "de", "--locale-dir", str(locale_dir), "--check"]) == 1
    assert "out of date" in capsys.readouterr().err


def test_check_fails_when_the_mo_does_not_exist_yet(tmp_path):
    po_file = tmp_path / "de.po"
    po_file.write_text('msgid "Save"\nmsgstr "Speichern"\n', encoding="utf-8")
    locale_dir = tmp_path / "locale"
    assert compile_mo_module.main([str(po_file), "de", "--locale-dir", str(locale_dir), "--check"]) == 1
