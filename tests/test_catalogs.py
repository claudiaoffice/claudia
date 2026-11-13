"""The shipped catalogs, as they are in the repository (E5.7, D31, D148, D160): German is complete, its placeholders
are the English ones, and the three derived files are what their sources make."""

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


po_to_json = load("po_to_json")
update_po = load("update_po")
make_pseudolocale = load("make_pseudolocale")
compile_mo = load("compile_mo")

POT = (ROOT / "po" / "claudia.pot").read_text(encoding="utf-8")
DE = po_to_json.parse_po((ROOT / "po" / "de.po").read_text(encoding="utf-8"))
# parse_po leaves out an untranslated entry, so the template is read with every msgstr filled in
MSGIDS = list(po_to_json.parse_po(re.sub(r'^msgstr ""$', 'msgstr "x"', POT, flags=re.M)))
PLACEHOLDER = re.compile(r"\{\w+\}")


def test_every_string_of_the_template_has_a_german_translation():
    missing = [m for m in MSGIDS if m not in DE]
    assert not missing, f"{len(missing)} untranslated, for example: {missing[:5]}"


def test_german_keeps_no_string_the_template_lacks():
    assert [m for m in DE if m not in set(MSGIDS)] == []


def test_a_translation_keeps_the_placeholders_of_its_english_string():
    """A renamed or lost ``{placeholder}`` would show as a literal brace, or leave a value out, only in German."""
    broken = [m for m, s in DE.items() if sorted(PLACEHOLDER.findall(m)) != sorted(PLACEHOLDER.findall(s))]
    assert broken == []


def test_german_is_what_update_po_would_leave_it_as():
    path = ROOT / "po" / "de.po"
    current = path.read_text(encoding="utf-8")
    assert update_po.merge(POT, current) == current


def test_the_web_catalog_is_derived_from_the_po_file():
    shipped = json.loads((ROOT / "web" / "public" / "i18n" / "de.json").read_text(encoding="utf-8"))
    assert shipped == DE


def test_the_pseudo_locale_is_derived_from_the_template():
    assert (ROOT / "po" / "xx.po").read_text(encoding="utf-8") == make_pseudolocale.render_pseudo_po(POT)
