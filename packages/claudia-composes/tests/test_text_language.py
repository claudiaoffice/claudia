"""The language of a text (D915): a BCP 47 tag stored with the text, set in one step that can be undone."""

import json

import pytest

from claudia_composes import BUILTIN_STYLES, LanguageError, SetLanguage, TextModel, normalize_language
from claudia_core import CommandLog, Document


def test_a_new_text_has_no_language():
    assert TextModel().language is None


@pytest.mark.parametrize(
    ("tag", "written"),
    [("de", "de"), ("EN-gb", "en-GB"), ("sr-latn-rs", "sr-Latn-RS"), ("es-419", "es-419"), (" de-AT ", "de-AT")],
)
def test_a_tag_is_written_as_bcp_47_recommends(tag, written):
    assert normalize_language(tag) == written


@pytest.mark.parametrize("tag", ["", "d", "deutsch-", "de_DE", "1de", "x" * 40, "de--AT"])
def test_what_is_not_a_tag_is_refused(tag):
    with pytest.raises(LanguageError, match="language tag"):
        normalize_language(tag)


def test_setting_the_language_is_one_step_with_an_exact_inverse_and_an_event():
    doc = Document(TextModel())
    events = []
    doc.bus.subscribe(lambda e: events.append(e.to_data()) if hasattr(e, "to_data") else None)
    doc.execute(SetLanguage("de-de"), author="anna")
    assert doc.model.language == "de-DE"
    assert {"type": "language", "language": "de-DE"} in events
    assert list(doc.log)[-1].command.summary == "set the language to de-DE"
    doc.undo("anna")
    assert doc.model.language is None
    assert {"type": "language", "language": None} in events
    assert SetLanguage(None).summary == "removed the language"


def test_the_language_survives_the_log_and_a_snapshot_and_older_snapshots_have_none():
    doc = Document(TextModel())
    doc.execute(SetLanguage("en-GB"), author="anna")
    log = CommandLog.from_data(doc.log.to_data(), TextModel.registry)
    assert Document.open(TextModel, log).model.language == "en-GB"
    state = doc.model.serialize()
    assert TextModel.restore(state).language == "en-GB"
    del state["language"]
    assert TextModel.restore(state).language is None


def test_body_text_is_hyphenated_and_titles_and_headings_are_not():
    styles = {s.id: s.css for s in BUILTIN_STYLES}
    assert styles["body"]["hyphens"] == "auto"
    for heading in ("title", "heading-1", "heading-2"):
        assert styles[heading]["hyphens"] == "manual"


def test_a_log_written_before_the_language_moved_to_the_kernel_still_opens():
    """D917: ``composes.SetLanguage`` was the command's kind for a day; its logs replay to the same text."""
    doc = Document(TextModel())
    doc.execute(SetLanguage("de"), author="anna")
    written = json.dumps(doc.log.to_data())
    assert "core.SetLanguage" in written
    log = CommandLog.from_data(
        json.loads(written.replace("core.SetLanguage", "composes.SetLanguage")), TextModel.registry
    )
    assert Document.open(TextModel, log).model.language == "de"
