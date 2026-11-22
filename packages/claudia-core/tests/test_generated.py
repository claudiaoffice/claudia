"""Tables of contents and agendas: generated paragraphs whose entries are derived from the headings (E9.31, step E of
claudiaoffice-log/notes/text-structure-across-apps.md)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from claudia_core import (
    ContentsEntry,
    GeneratedChanged,
    ListBook,
    ListDef,
    Paragraph,
    Placed,
    SchemeBook,
    SetGenerated,
    StyleBook,
    StyleDef,
    TextStructure,
    Toc,
    encode,
    generated_from_data,
    new_registry,
)


def styles() -> StyleBook:
    return StyleBook(
        [
            StyleDef("body", "Body", "", None, {}),
            StyleDef("title", "Title", "", "body", {}, heading_level=0),
            StyleDef("h1", "Heading 1", "", "body", {}, heading_level=1, numbering="outline"),
            StyleDef("h2", "Heading 2", "", "h1", {}, heading_level=2),
            StyleDef("h3", "Heading 3", "", "h2", {}, heading_level=3),
            StyleDef("contents-1", "Contents 1", "", "body", {}),
            StyleDef("contents-2", "Contents 2", "", "body", {}),
        ]
    )


@dataclass
class Host:
    """Paragraphs in holders, read in order; a holder's name is its place (a slide number) when ``places``."""

    holders: dict[str, list[Paragraph]]
    places: bool = False
    asides: frozenset[str] = frozenset()
    styles: StyleBook = field(default_factory=styles)
    lists: ListBook = field(default_factory=lambda: ListBook([ListDef("outline", "chapters")]))
    schemes: SchemeBook = field(default_factory=SchemeBook)
    order: int = 0

    def reading_order(self):
        for holder, paragraphs in self.holders.items():
            for paragraph in paragraphs:
                yield Placed(paragraph, holder, holder not in self.asides, holder if self.places else None)

    @property
    def structure_version(self):
        return (self.order,)


def para(pid: str, style: str = "body", text: str | None = None, toc: Toc | None = None) -> Paragraph:
    return Paragraph(pid, style, "" if toc else (pid if text is None else text), (), None, toc)


class Events(list):
    def emit(self, event):
        self.append(event)


def a_text(toc: Toc | None = None) -> Host:
    return Host(
        {
            "body": [
                para("t", "title", "School gardens"),
                para("c", toc=toc or Toc()),
                para("a", "h1", "Why"),
                para("b", "h2", "Asked"),
                para("x", "body", "text"),
                para("d", "h3", "Deep"),
                para("e", "h1", "How"),
            ]
        }
    )


def lines(entries) -> list[tuple]:
    return [(e.target, e.level, e.number, e.text, e.style, e.place) for e in entries]


def test_the_entries_are_the_headings_it_lists_with_their_numbers_and_their_contents_style():
    assert lines(TextStructure(a_text(Toc(1, 2))).entries("c")) == [
        ("a", 1, "1", "Why", "contents-1", None),
        ("b", 2, "1.1", "Asked", "contents-2", None),
        ("e", 1, "2", "How", "contents-1", None),
    ]


def test_the_title_is_never_listed_a_style_the_document_lacks_falls_back_and_numbers_can_be_off():
    entries = TextStructure(a_text(Toc(1, 3, numbers=False))).entries("c")
    assert [e.target for e in entries] == ["a", "b", "d", "e"], "the title (level 0) and body text are not listed"
    assert {e.number for e in entries} == {None}
    assert next(e for e in entries if e.target == "d").style == "body", "no Contents 3: the table's own style"


def test_words_beside_the_main_text_and_other_tables_are_not_headings():
    host = a_text()
    host.holders["box"] = [para("o", "h1", "A heading in a box")]
    host.asides = frozenset({"box"})
    host.holders["body"].append(para("c2", toc=Toc()))
    assert "o" not in [e.target for e in TextStructure(host).entries("c")]
    assert TextStructure(host).entries("c2") == TextStructure(host).entries("c")


def test_in_a_presentation_an_entry_carries_its_place_unless_places_are_off():
    host = Host({"1": [para("ag", toc=Toc(1, 1))], "2": [para("t2", "h1", "Results")]}, places=True)
    assert lines(TextStructure(host).entries("ag")) == [("t2", 1, "1", "Results", "contents-1", "2")]
    host.holders["1"][0] = para("ag", toc=Toc(1, 1, places=False))
    host.order += 1
    assert TextStructure(host).entries("ag")[0].place is None


def test_settle_tells_the_entries_that_changed_and_a_table_that_went_away():
    host = a_text()
    structure, seen = TextStructure(host), Events()
    structure.settle(seen)
    assert seen == []
    host.holders["body"][2] = para("a", "h1", "Why we did it")  # retyped: text changes need no structure change
    structure.settle(seen)
    assert len(seen) == 1 and isinstance(seen[0], GeneratedChanged) and seen[0].entries[0].text == "Why we did it"
    assert seen[0].to_data()["type"] == "generated" and seen[0].to_data()["entries"][0]["target"] == "a"
    host.holders["body"][1] = para("c", text="")
    host.order += 1
    seen.clear()
    structure.settle(seen)
    assert seen == [GeneratedChanged("c", None)]


def test_a_document_without_a_table_of_contents_derives_nothing():
    host = a_text()
    host.holders["body"].pop(1)
    assert TextStructure(host).all_entries() == {}


@pytest.mark.parametrize(
    ("toc", "message"),
    [
        (Toc(0, 3), "levels 1 to 9"),
        (Toc(1, 10), "levels 1 to 9"),
        (Toc(3, 1), "the first is deeper"),
        (Toc(leader="stars"), "leader"),
        (Toc(numbers="yes"), "on or off"),  # type: ignore[arg-type]
    ],
)
def test_options_that_make_no_sense_are_refused_with_a_sentence(toc, message):
    with pytest.raises(ValueError, match=message):
        toc.check()


def test_the_options_and_the_command_survive_plain_data_and_the_log():
    toc = Toc(2, 4, False, False, "none")
    assert generated_from_data(toc.to_data()) == toc
    with pytest.raises(ValueError, match="generated as one of"):
        generated_from_data({"kind": "index"})
    registry = new_registry()
    for command in (SetGenerated("c", toc), SetGenerated("c", None)):
        assert registry.decode(encode(command)) == command
    paragraph = Paragraph("c", "body", generated=toc)
    assert Paragraph.from_data(paragraph.to_data()) == paragraph
    assert "generated" not in Paragraph("p", "body", "x").to_data()


def test_only_an_empty_paragraph_can_be_generated():
    with pytest.raises(ValueError, match="only an empty paragraph"):
        Paragraph("p", "body", "words").with_generated(Toc())
    assert ContentsEntry("a", 1, None, "Why", "contents-1").to_data()["place"] is None
