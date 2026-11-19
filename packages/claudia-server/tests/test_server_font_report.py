"""The font report (E1.9, D1306): what a document asks for and this server does not have, said when it is opened. It
never blocks, and what it offers (getting a font) is the administrator's, decided by the server."""

from types import SimpleNamespace

import pytest
from test_server_composes import ANN

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore, StyleDef
from claudia_server.composes import composes_methods
from claudia_server.protocol import Context, Limits


class Catalogue:
    """Just what the report asks a font catalogue: how a family resolves. The starter fonts the built-in styles ask for
    are there; ``other`` says what each of the families named is shown in (``None``: nothing stands in for it)."""

    def __init__(self, other: dict[str, str | None]):
        self.other = other

    def resolve(self, family: str):
        provided = self.other.get(family, family)
        closeness = "other" if provided is None else ("same" if provided == family else "same-widths")
        return SimpleNamespace(requested=family, provided=provided, substituted=provided != family, closeness=closeness)


@pytest.fixture
def paper():
    doc = Document(TextModel(), store=MemoryStore())
    doc.model.styles.add(StyleDef("fira", "Fira", "", None, {"font-family": "'Fira Sans', sans-serif"}))
    return doc


def report(doc, catalogue):
    ctx = Context(doc, ANN, Limits(), font_catalogue=lambda: catalogue)
    return composes_methods.dispatch(ctx, "font_report", {})


def test_a_font_the_server_lacks_is_reported_with_nothing_to_stand_in():
    doc = Document(TextModel(), store=MemoryStore())
    doc.model.styles.add(StyleDef("fira", "Fira", "", None, {"font-family": "Fira Sans"}))
    answer = report(doc, Catalogue({"Fira Sans": None}))
    assert answer["checked"] is True
    assert answer["missing"] == [{"family": "Fira Sans", "stand_in": None, "closeness": "other"}]


def test_a_font_with_a_stand_in_says_which(paper):
    answer = report(paper, Catalogue({"Fira Sans": "Open Sans"}))
    assert answer["missing"] == [{"family": "Fira Sans", "stand_in": "Open Sans", "closeness": "same-widths"}]


def test_a_font_the_server_has_is_not_reported(paper):
    assert report(paper, Catalogue({}))["missing"] == []


def test_a_server_that_cannot_say_what_it_has_reports_nothing(paper):
    ctx = Context(paper, ANN, Limits())
    assert composes_methods.dispatch(ctx, "font_report", {}) == {"checked": False, "missing": []}


def test_the_report_is_a_read_any_viewer_may_ask_and_nothing_changes(paper):
    from claudia_server.auth import Account

    before = paper.revision
    ctx = Context(paper, Account("vera", "viewer"), Limits(), font_catalogue=lambda: Catalogue({"Fira Sans": None}))
    assert composes_methods.dispatch(ctx, "font_report", {})["missing"]
    assert paper.revision == before


def test_the_methods_of_every_app_have_it():
    from claudia_server.computes import computes_methods
    from claudia_server.creates import creates_methods

    assert all("font_report" in t.names() for t in (composes_methods, computes_methods, creates_methods))
