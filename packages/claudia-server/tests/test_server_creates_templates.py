"""The methods of a presentation about templates: its note, Save as template…, Change theme and Change template
(E10.4, E10.22, D1539)."""

import base64

import pytest

from claudia_core import Document, MemoryStore, SetRole
from claudia_creates import AddSlide, DefineLayout, SlideModel
from claudia_creates.template import TemplateInfo
from claudia_server.auth import Account
from claudia_server.creates import creates_methods
from claudia_server.protocol import Context, Limits, RequestError
from claudia_server.template_library import TemplateLibrary, read_template_file, template_file

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")
TALK = TemplateInfo("Conference talk", "Talks of twenty minutes", "en")


@pytest.fixture
def library(tmp_path):
    donor = Document(SlideModel.empty(), store=MemoryStore())
    donor.execute(DefineLayout("title", "Title"), author="ana")
    donor.execute(SetRole("accent", "#aa0000"), author="ana")
    library = TemplateLibrary(tmp_path)
    library.add(template_file(donor.model, TALK, exporter="ana", exported_at="2026-11-23T10:00:00Z"), added_by="ana")
    return library


@pytest.fixture
def deck():
    doc = Document(SlideModel.empty(), store=MemoryStore())
    doc.execute(AddSlide("s2"), author="ann")
    return doc


class Requests:
    def __init__(self, deck, library):
        self.deck, self.library = deck, library

    def __call__(self, name, params=None, account=ANN, exported=None):
        left = []
        ctx = Context(
            self.deck, account, Limits(), lock_seconds=30.0, doc_id="talk", template_library=lambda: self.library
        )
        ctx.record_leaving = lambda kind, fmt, parts, pages=None: left.append((kind, fmt, parts))  # type: ignore[method-assign]
        answer = creates_methods.dispatch(ctx, name, params)
        if exported is not None:
            exported.extend(left)
        return answer


@pytest.fixture
def call(deck, library):
    return Requests(deck, library)


def test_a_presentation_says_which_template_it_came_from_and_a_plain_one_says_none(call):
    assert call("template") is None
    call("change_template", {"template": "conference-talk"})
    assert call("template") == TALK.to_data()


def test_save_as_template_answers_a_file_with_the_layouts_and_not_the_slides_and_is_an_export(call):
    left: list = []
    answer = call(
        "save_as_template",
        {"name": "Weekly", "purpose": "The Monday update", "language": "en"},
        exported=left,
    )
    template = read_template_file(base64.b64decode(answer["data"]))
    assert (template.info.name, len(template.model.order)) == ("Weekly", 0)
    assert answer["filename"] == "weekly.claudia-export.zip"
    assert left == [("export", answer["format"], ("content",))]


def test_save_as_template_says_what_is_wrong_with_the_note(call):
    with pytest.raises(RequestError) as refused:
        call("save_as_template", {"name": " ", "purpose": "x", "language": "en"})
    assert (refused.value.code, str(refused.value.message)) == ("command_error", "a template needs a name")


def test_the_assistant_does_not_save_the_presentation_as_a_template(call):
    with pytest.raises(RequestError) as refused:
        call(
            "save_as_template",
            {"name": "W", "purpose": "x", "language": "en"},
            account=Account("ai", "editor", system=True),
        )
    assert refused.value.code == "forbidden"


def test_change_template_gives_the_presentation_the_layouts_and_one_step_undoes_it(call, deck):
    before = [layout.name for layout in deck.model.layouts]
    answer = call("change_template", {"template": "conference-talk"})
    assert "Title" in [layout.name for layout in deck.model.layouts] and answer["revision"]
    deck.undo("ann")
    assert [layout.name for layout in deck.model.layouts] == before


def test_change_theme_changes_the_colours_and_not_the_layouts(call, deck):
    call("change_theme", {"template": "conference-talk"})
    assert deck.model.palette.colours()["accent"] == "#AA0000"
    assert "Title" not in [layout.name for layout in deck.model.layouts]


def test_a_template_nobody_has_is_a_command_error(call):
    with pytest.raises(RequestError) as refused:
        call("change_template", {"template": "nothing"})
    assert refused.value.code == "command_error"


def test_a_viewer_does_not_change_the_template(call):
    with pytest.raises(RequestError) as refused:
        call("change_template", {"template": "conference-talk"}, account=VERA)
    assert refused.value.code == "forbidden"


def test_a_server_without_a_library_has_no_template_to_change_to(deck):
    with pytest.raises(RequestError) as refused:
        Requests(deck, None)("change_template", {"template": "basic"})
    assert refused.value.code == "command_error"
