"""`_resolve_locale`: the one place `composes()` decides which language the shell starts in (E5.7's second round).
Only this pure function is exercised here -- `composes()` itself goes on to build a real GTK application, which is
`test_e2e.py`'s job (``pytestmark = pytest.mark.gtk`` there), not a plain unit test's."""

from __future__ import annotations

import pytest

from claudia_shell_gtk import __main__ as main_module


def test_a_persisted_choice_wins_over_the_detected_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "load_shell_locale", lambda: "de")
    monkeypatch.setattr(main_module, "detect_system_locale", lambda: pytest.fail("should not be called"))
    assert main_module._resolve_locale() == "de"  # noqa: SLF001


def test_with_nothing_persisted_yet_the_detected_locale_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "load_shell_locale", lambda: None)
    monkeypatch.setattr(main_module, "detect_system_locale", lambda: "fr")
    assert main_module._resolve_locale() == "fr"  # noqa: SLF001
