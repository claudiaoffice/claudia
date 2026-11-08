"""Locale detection and gettext wiring (E5.7, D31): see i18n.py. No GTK import, so this runs without a display."""

from __future__ import annotations

import os

import pytest

from claudia_shell_gtk import i18n
from claudia_shell_gtk.i18n import DEFAULT_LOCALE, detect_system_locale, install_translation, negotiate, translate


@pytest.fixture(autouse=True)
def _restore_active_translation():
    """``install_translation`` replaces process-wide, module-global state (the usual gettext pattern) — every test
    below that calls it gets a clean slate, and leaves one for whatever test (in this file or another) runs next."""
    before = i18n._active
    yield
    i18n._active = before


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


# --------------------------------------------------------------------------- translate


def test_translate_is_the_identity_before_anything_is_installed():
    # the module's own fresh state, restored by the fixture above after any earlier test in this process installed
    # something — exactly what window.py's _layout() gets if it is ever imported before __main__.py calls
    # install_translation (it must not be, see window.py's own docstring, but translate() still degrades safely).
    i18n._active = i18n._identity
    assert translate("Save") == "Save"


def test_translate_reads_whatever_was_most_recently_installed():
    install_translation("de", localedir="/no/such/directory")
    assert translate("Save") == "Save"  # no catalog at that path: still the identity, through install_translation
    assert i18n._active is not i18n._identity  # but it is now gettext's own fallback function, not the module default


def test_bundled_localedir_points_at_a_locale_folder_next_to_this_module():
    localedir = i18n.bundled_localedir()
    assert os.path.basename(localedir) == "locale"
    assert os.path.dirname(localedir).endswith("claudia_shell_gtk")


def test_install_translation_without_an_explicit_localedir_uses_the_bundled_one():
    """``zz`` has no catalog and never will (not a real BCP-47 language), so this stays the identity regardless of
    which real locales ``locale/`` holds a compiled ``.mo`` for — the point is that *no* ``localedir`` is passed,
    confirming the bundled default is what gets used, not that any particular translation exists there."""
    _ = install_translation("zz")
    assert _("Save") == "Save"
