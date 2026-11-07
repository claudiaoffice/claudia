"""Locale detection and gettext wiring (E5.7, D31): see i18n.py. No GTK import, so this runs without a display."""

from __future__ import annotations

from claudia_shell_gtk.i18n import DEFAULT_LOCALE, detect_system_locale, install_translation, negotiate

# --------------------------------------------------------------------------- detect_system_locale


def test_falls_back_to_default_when_nothing_is_set():
    assert detect_system_locale({}) == DEFAULT_LOCALE


def test_reads_lang_when_nothing_more_specific_is_set():
    assert detect_system_locale({"LANG": "de_DE.UTF-8"}) == "de-DE"


def test_prefers_language_over_lc_all_over_lc_messages_over_lang():
    env = {"LANGUAGE": "fr", "LC_ALL": "de_DE", "LC_MESSAGES": "es_ES", "LANG": "en_US"}
    assert detect_system_locale(env) == "fr"
    del env["LANGUAGE"]
    assert detect_system_locale(env) == "de-DE"
    del env["LC_ALL"]
    assert detect_system_locale(env) == "es-ES"


def test_language_may_list_several_colon_separated_most_preferred_first():
    assert detect_system_locale({"LANGUAGE": "de:en"}) == "de"


def test_c_and_posix_mean_no_preference_so_the_next_variable_is_tried():
    assert detect_system_locale({"LANG": "C"}) == DEFAULT_LOCALE
    assert detect_system_locale({"LC_ALL": "POSIX", "LANG": "de_DE"}) == "de-DE"


def test_an_encoding_or_modifier_suffix_is_stripped():
    assert detect_system_locale({"LANG": "pt_BR.UTF-8@euro"}) == "pt-BR"


def test_an_unusable_value_does_not_crash_and_falls_through():
    assert detect_system_locale({"LANG": "not a locale!"}) == DEFAULT_LOCALE


# --------------------------------------------------------------------------- negotiate


def test_an_exact_match_wins():
    assert negotiate("de-DE", ["de", "de-DE", "fr"]) == "de-DE"


def test_falls_back_to_the_same_language_in_another_region():
    assert negotiate("de-AT", ["de-DE", "fr"]) == "de-DE"


def test_falls_back_to_default_when_nothing_matches():
    assert negotiate("ja", ["de", "fr"]) == DEFAULT_LOCALE


# --------------------------------------------------------------------------- install_translation


def test_without_a_catalog_the_translation_is_the_identity():
    # po/ has no .mo files yet (E5.7 groundwork); this must not raise and must not alter the text
    _ = install_translation("de", localedir="/no/such/directory")
    assert _("Save") == "Save"
    assert _("") == ""


def test_an_unknown_locale_also_falls_back_to_identity():
    _ = install_translation("xx-XX", localedir="/no/such/directory")
    assert _("Open document") == "Open document"
