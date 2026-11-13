"""The function catalog (E13.5/E13.6): every cell function, library and core, as one searchable list."""

from __future__ import annotations

from claudia_computes.formula.forms import CORE_NAMES
from claudia_computes.functions.help import function_catalog, get_function, search_functions, translatable_texts

CATALOG = function_catalog()


def test_the_catalog_has_both_halves_and_leaves_nothing_out():
    names = {entry.name for entry in CATALOG}
    assert names == {entry.name for entry in CATALOG if entry.source == "library"} | CORE_NAMES
    assert "SUM" in names and "XLOOKUP" in names and "IF" in names  # a library name and two core ones


def test_the_catalog_is_sorted_by_name_with_no_duplicates():
    names = [entry.name for entry in CATALOG]
    assert names == sorted(names)
    assert len(names) == len(set(names))


def test_every_entry_has_a_one_line_tooltip_and_some_help():
    for entry in CATALOG:
        assert entry.tooltip.startswith(entry.signature), entry.name
        assert "\n" not in entry.tooltip, entry.name
        assert entry.help, entry.name


def test_a_library_entry_matches_its_bound():  # SUM: UserFunction, so its text comes straight from Bound
    sum_entry = get_function("SUM")
    assert sum_entry is not None
    assert sum_entry.source == "library"
    assert sum_entry.signature == "SUM(*values)"
    assert sum_entry.tooltip == "SUM(*values): The sum of the numbers in the ranges. Text and empty cells are skipped."


def test_a_core_entry_is_read_from_its_docstring():  # XLOOKUP: a form, so its text comes from its own docstring
    xlookup = get_function("XLOOKUP")
    assert xlookup is not None
    assert xlookup.source == "core"
    assert xlookup.signature.startswith("XLOOKUP(value, lookup range")
    assert "XMATCH" in xlookup.description  # the docstring's cross-reference survives collapsing the line wrap
    assert "\n" in xlookup.help  # the full docstring, not collapsed, is kept for the topic view


def test_get_function_is_case_insensitive_and_unknown_names_give_none():
    assert get_function("sum") == get_function("Sum") == get_function("SUM")
    assert get_function("NOSUCHFUNCTION") is None


def test_search_with_no_query_gives_the_whole_catalog():
    assert search_functions("") == CATALOG
    assert search_functions("   ") == CATALOG


def test_search_by_name_ranks_an_exact_match_first_then_a_prefix_then_a_substring():
    found = [entry.name for entry in search_functions("sum")]
    assert found[0] == "SUM"  # exact
    assert found[1:4] == ["SUMIF", "SUMIFS", "SUMPRODUCT"]  # prefix matches, alphabetical
    assert "CHECKSUM" not in found  # no such function; guards against a false read of this test
    assert "VLOOKUP" not in found


def test_search_by_description_finds_a_function_whose_name_does_not_mention_the_word():
    found = [entry.name for entry in search_functions("angle")]
    assert {"SIN", "COS", "TAN", "RADIANS", "DEGREES"} <= set(found)


def test_search_is_case_insensitive():
    assert search_functions("xlookup") == search_functions("XLOOKUP") == search_functions("XlookUp")


# ------------------------------------------------------------------------------- in another language (E13.8, D294)
GERMAN = {
    "The sum of the numbers in the ranges. Text and empty cells are skipped.": "Die Summe der Zahlen in den Bereichen.",
    "{formula}  gives  {result}": "{formula}  ergibt  {result}",
    "{formula}  gives  {result}  (with {given})": "{formula}  ergibt  {result}  (mit {given})",
}


def say_in_german(text: str) -> str:
    return GERMAN.get(text, text)


def test_translating_with_no_words_changed_gives_the_same_entry():
    sum_entry = get_function("SUM")
    assert sum_entry is not None
    assert sum_entry.translated(lambda text: text) is sum_entry


def test_a_library_entry_is_said_in_another_language_in_all_three_texts():
    sum_entry = get_function("SUM")
    assert sum_entry is not None
    german = sum_entry.translated(say_in_german)
    assert german.description == "Die Summe der Zahlen in den Bereichen."
    assert german.tooltip == "SUM(*values): Die Summe der Zahlen in den Bereichen."
    assert german.help.startswith(german.tooltip + "\n\n")
    assert "ergibt" in german.help and "gives" not in german.help
    assert (german.name, german.signature, german.source) == (sum_entry.name, sum_entry.signature, "library")


def test_an_example_with_cells_says_which_cells_it_reads():
    entry = next(entry for entry in CATALOG if entry.source == "library" and any(e.cells for e in entry.examples))
    german = entry.translated(say_in_german)
    assert "(mit " in german.help and "(with " not in german.help


def test_a_core_entry_is_said_in_another_language_from_its_description():
    xlookup = get_function("XLOOKUP")
    assert xlookup is not None
    seen = []
    german = xlookup.translated(lambda text: seen.append(text) or "Zeile: " + text[:10])
    assert seen == [xlookup.description]
    assert german.tooltip == f"{xlookup.signature}: Zeile: {xlookup.description[:10]}"
    assert german.help == german.tooltip


def test_the_texts_to_translate_are_every_description_and_the_example_templates():
    texts = translatable_texts()
    assert texts == sorted(set(texts))
    assert {entry.description for entry in CATALOG if entry.description} <= set(texts)
    assert "{formula}  gives  {result}" in texts and "{formula}  gives  {result}  (with {given})" in texts
