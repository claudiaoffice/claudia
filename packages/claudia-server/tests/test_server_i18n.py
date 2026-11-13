"""The server's own messages are said in the language of the connection that gets them (E5.7, D31, D293)."""

from __future__ import annotations

import pytest

from claudia_server import i18n
from claudia_server.i18n import Message, localized, msg
from claudia_server.protocol import RequestError


def test_a_message_reads_as_its_english_text() -> None:
    message = msg("set_cells: at most {limit} cells at a time", limit=500)
    assert message == "set_cells: at most 500 cells at a time"
    assert isinstance(message, str)


def test_a_message_without_parameters_is_its_text_untouched() -> None:
    assert msg("the range is {sheet, row0}") == "the range is {sheet, row0}"


def test_a_message_remembers_its_template_and_parameters() -> None:
    message = msg("{name} is not allowed", name="x")
    assert isinstance(message, Message)
    assert (message.template, message.params) == ("{name} is not allowed", {"name": "x"})


def test_english_is_the_source_language() -> None:
    assert localized(msg("this document has no styles"), "en") == "this document has no styles"


def test_german_is_looked_up_in_the_catalog() -> None:
    assert localized(msg("this document has no styles"), "de") == "Dieses Dokument hat keine Stile"


def test_parameters_are_filled_into_the_german_text() -> None:
    assert localized(msg("set_cells: at most {limit} cells at a time", limit=500), "de") == (
        "set_cells: Höchstens 500 Zellen auf einmal"
    )


def test_a_region_falls_back_to_its_language() -> None:
    assert localized(msg("this document has no styles"), "de-AT") == "Dieses Dokument hat keine Stile"


def test_a_language_without_a_catalog_gets_english() -> None:
    assert localized(msg("this document has no styles"), "fr") == "this document has no styles"


def test_a_text_that_is_not_a_message_is_left_alone() -> None:
    """What claudia_core says (``str(exc)``) is English until it carries its own template."""
    assert localized("some error from the core", "de") == "some error from the core"


def test_a_translation_with_the_wrong_placeholders_falls_back_to_english(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(i18n, "_lookup", lambda template, locale: "{gone} is wrong")
    assert localized(msg("{name} is not allowed", name="x"), "de") == "x is not allowed"


def test_a_request_error_is_sent_in_the_connections_language() -> None:
    error = RequestError("bad_request", msg("this document has no styles"))
    assert error.to_dict("de") == {"code": "bad_request", "message": "Dieses Dokument hat keine Stile"}
    assert error.to_dict() == {"code": "bad_request", "message": "this document has no styles"}


def test_a_request_error_keeps_its_english_text_for_logs() -> None:
    error = RequestError("bad_request", msg("this document has no styles"))
    assert str(error) == error.message == "this document has no styles"
