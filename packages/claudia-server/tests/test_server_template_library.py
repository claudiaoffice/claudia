"""The template file and the library of templates a server offers (E10.4, E10.22, D1537)."""

import zipfile
from io import BytesIO

import pytest

from claudia_core import CreateStyle, Document, MemoryStore, StyleDef
from claudia_creates import AddSlide, DefineLayout, SetSlideNotes, SlideModel
from claudia_creates.template import TemplateInfo, TemplateRefused, template_state
from claudia_document_file import ExportRefused, read_export, write_export
from claudia_server.template_library import (
    BASIC_ID,
    SUFFIX,
    TemplateLibrary,
    describe,
    read_template_file,
    template_file,
)

TALK = TemplateInfo("Conference talk", "Talks of twenty minutes", "en")


@pytest.fixture
def deck():
    doc = Document(SlideModel.empty(), store=MemoryStore())
    doc.execute(DefineLayout("title", "Title"), author="ana")
    doc.execute(CreateStyle(StyleDef("quote", "Quote", "", None, {"font-style": "italic"})), author="ana")
    doc.execute(AddSlide("s2"), author="ana")
    doc.execute(SetSlideNotes("s2", "do not say the number"), author="ana")
    return doc.model


def a_file(deck, info=TALK):
    return template_file(deck, info, exporter="anna", exported_at="2026-11-23T10:00:00Z")


# -- the file --------------------------------------------------------------------------------------------------------


def test_a_template_file_holds_the_content_and_nothing_of_the_slides_the_history_or_the_chat(deck):
    data = a_file(deck)
    with zipfile.ZipFile(BytesIO(data)) as archive:
        assert sorted(archive.namelist()) == ["content.json", "export.json", "format"]
        assert b"do not say the number" not in archive.read("content.json")
    exported = read_export(data)
    assert (exported.history, exported.chat, exported.exporter) == (None, None, "anna")


def test_a_template_file_reads_back_as_the_template_it_was_written_as(deck):
    template = read_template_file(a_file(deck))
    assert template.info == TALK
    assert [layout.name for layout in template.model.layouts] == [layout.name for layout in deck.layouts]
    assert not template.model.order


@pytest.mark.parametrize(
    "data, said",
    [
        (b"not a zip", "this is not a Claudia export"),
        (write_export("composes", 1, {}, exporter="a", exported_at="now"), "this is not a presentation"),
        (
            write_export(SlideModel.app, SlideModel.state_schema + 1, {}, exporter="a", exported_at="now"),
            "this template was made by another version of Claudia",
        ),
    ],
)
def test_a_file_that_is_no_template_of_this_version_is_refused_with_a_sentence(data, said):
    with pytest.raises((ExportRefused, TemplateRefused)) as refused:
        read_template_file(data)
    assert str(refused.value) == said


def test_a_presentation_with_slides_is_no_template(deck):
    exported = write_export(deck.app, deck.state_schema, deck.serialize(), exporter="a", exported_at="now")
    with pytest.raises(TemplateRefused, match="a template has no slides"):
        read_template_file(exported)


# -- the library -----------------------------------------------------------------------------------------------------


def test_every_library_has_the_basic_template_and_it_cannot_be_removed(tmp_path):
    library = TemplateLibrary(tmp_path)
    assert [entry.id for entry in library.entries()] == [BASIC_ID]
    assert library.entries()[0].builtin
    with pytest.raises(TemplateRefused, match="the basic template cannot be removed"):
        library.remove(BASIC_ID)


def test_an_added_template_is_kept_in_a_file_and_found_again_by_a_new_library(tmp_path, deck):
    library = TemplateLibrary(tmp_path / "templates")
    added = library.add(a_file(deck), added_by="anna")
    assert [entry.id for entry in library.entries()] == [BASIC_ID, added]
    again = TemplateLibrary(tmp_path / "templates")
    assert again.get(added).info == TALK


def test_what_is_kept_has_no_history_or_chat_even_if_the_file_brought_it(tmp_path, deck):
    brought = write_export(
        deck.app,
        deck.state_schema,
        template_state(deck, TALK),
        exporter="x",
        exported_at="now",
        history=[b"{}"],
        chat=[b"{}"],
    )
    library = TemplateLibrary(tmp_path)
    library.add(brought, added_by="anna")
    (stored,) = list(tmp_path.glob("*.zip"))
    assert (read_export(stored.read_bytes()).history, read_export(stored.read_bytes()).chat) == (None, None)


def test_a_name_that_is_taken_is_refused_whatever_its_letters(tmp_path, deck):
    library = TemplateLibrary(tmp_path)
    library.add(a_file(deck), added_by="anna")
    with pytest.raises(TemplateRefused, match="there is a template called CONFERENCE TALK already"):
        library.add(a_file(deck, TemplateInfo("CONFERENCE TALK", "again", "en")), added_by="anna")
    with pytest.raises(TemplateRefused, match="there is a template called basic already"):
        library.add(a_file(deck, TemplateInfo("basic", "the same name as the built-in one", "en")), added_by="anna")


def test_names_that_make_the_same_id_get_different_files(tmp_path, deck):
    library = TemplateLibrary(tmp_path)
    first = library.add(a_file(deck, TemplateInfo("A b", "one", "en")), added_by="anna")
    second = library.add(a_file(deck, TemplateInfo("a-b", "two", "en")), added_by="anna")
    assert first != second
    assert len(list(tmp_path.glob("*.zip"))) == 2


def test_removing_a_template_removes_its_file(tmp_path, deck):
    library = TemplateLibrary(tmp_path)
    added = library.add(a_file(deck), added_by="anna")
    library.remove(added)
    assert library.get(added) is None
    assert not list(tmp_path.glob("*.zip"))
    with pytest.raises(KeyError):
        library.remove(added)


def test_a_file_in_the_folder_that_is_no_template_is_left_out_not_fatal(tmp_path, deck):
    (tmp_path / "broken.zip").write_bytes(b"nothing")
    library = TemplateLibrary(tmp_path)
    library.add(a_file(deck), added_by="anna")
    assert len(TemplateLibrary(tmp_path).entries()) == 2


def test_the_basic_template_is_described_in_the_language_asked(tmp_path):
    entry = TemplateLibrary(tmp_path).entries()[0]
    english, german = describe(entry, "en"), describe(entry, "de")
    assert (english["id"], english["name"], english["builtin"]) == (BASIC_ID, "Basic", True)
    assert german["name"] != english["name"] and german["purpose"] != english["purpose"]
    assert english["layouts"] and english["language"] == "en"


def test_a_file_that_is_no_export_at_all_does_not_stop_the_library_from_starting(tmp_path, deck):
    (tmp_path / "junk.claudia-export.zip").write_bytes(b"PK\x03\x04 not really")
    (tmp_path / "gone.claudia-export.zip").write_bytes(write_export("composes", 1, {}, exporter="a", exported_at="n"))
    library = TemplateLibrary(tmp_path)
    library.add(a_file(deck), added_by="anna")
    assert [entry.id for entry in TemplateLibrary(tmp_path).entries()] == [BASIC_ID, "conference-talk"]


def test_a_file_in_the_folder_cannot_take_the_name_of_another_template_or_the_id_of_the_built_in_one(tmp_path, deck):
    (tmp_path / f"a{SUFFIX}").write_bytes(a_file(deck))
    (tmp_path / f"b{SUFFIX}").write_bytes(a_file(deck, TemplateInfo("conference TALK", "the same name again", "en")))
    (tmp_path / f"{BASIC_ID}{SUFFIX}").write_bytes(a_file(deck, TemplateInfo("Not basic", "an id that is taken", "en")))
    library = TemplateLibrary(tmp_path)
    assert [entry.id for entry in library.entries()] == [BASIC_ID, "a"]
