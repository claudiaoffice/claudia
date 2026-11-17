"""A link of a kept docx stays where it is when the words around it are edited, and goes (and is named) only when its
own words are rewritten (IEW-01)."""

from __future__ import annotations

from io import BytesIO

import pytest
from claudia_composes_io import apply_edits_to_docx, docx_to_text
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from test_docx_setup import saved

from claudia_odf_io import Loss, LossLog


def a_file(*pieces: str | tuple[str, str]) -> bytes:
    """A one-paragraph file: a plain run for each ``str`` piece, a hyperlink (to a made-up place) for each
    ``(words, "link")`` piece."""
    document = Document()
    paragraph = document.add_paragraph()
    for index, piece in enumerate(pieces):
        if isinstance(piece, str):
            paragraph.add_run(piece)
            continue
        link = OxmlElement("w:hyperlink")
        link.set(qn("w:anchor"), f"target{index}")
        run = OxmlElement("w:r")
        words = OxmlElement("w:t")
        words.text = piece[0]
        words.set(qn("xml:space"), "preserve")
        run.append(words)
        link.append(run)
        paragraph._p.append(link)
    return saved(document)


def reworded(original: bytes, text: str, losses: LossLog | None = None) -> bytes:
    baseline, current = docx_to_text(original), docx_to_text(original)
    block = current.blocks[0]
    current.blocks[0] = type(block)(block.id, block.style, text)
    return apply_edits_to_docx(original, baseline, current, losses=losses)


def paragraph_of(data: bytes):
    return Document(BytesIO(data)).paragraphs[0]._p


def spoken(data: bytes) -> str:
    return "".join(t.text or "" for t in paragraph_of(data).iter(qn("w:t")))


def links_of(data: bytes) -> list[tuple[str, str]]:
    return [
        ("".join(t.text or "" for t in link.iter(qn("w:t"))), link.get(qn("w:anchor")))
        for link in paragraph_of(data).findall(qn("w:hyperlink"))
    ]


def test_words_added_after_a_link_are_written_once_and_the_link_stays_a_link():
    edited = reworded(a_file("see ", ("the link", "link")), "SEE the link!")
    assert spoken(edited) == "SEE the link!"
    assert links_of(edited) == [("the link", "target1")]


def test_words_added_in_front_of_a_link_and_between_two_links_land_where_they_were_typed():
    original = a_file("a ", ("one", "link"), " b ", ("two", "link"), " c")
    edited = reworded(original, "A a one B b two c")
    assert spoken(edited) == "A a one B b two c"
    assert [words for words, _ in links_of(edited)] == ["one", "two"]
    paragraph = paragraph_of(edited)
    assert [child.tag.rsplit("}", 1)[1] for child in paragraph if child.tag != qn("w:pPr")] == [
        "r",
        "hyperlink",
        "r",
        "hyperlink",
        "r",
    ]


def test_a_link_whose_own_words_are_rewritten_goes_as_a_link_and_the_words_stay_as_they_were_typed():
    losses = LossLog()
    edited = reworded(a_file("see ", ("the link", "link"), "."), "see the page.", losses)
    assert spoken(edited) == "see the page."
    assert links_of(edited) == []
    assert Loss("removed-link", "", 1) in losses.result()


def test_a_link_stays_when_only_the_end_of_its_paragraph_is_cut_and_nothing_is_lost():
    losses = LossLog()
    edited = reworded(a_file(("the link", "link"), " and more"), "the link", losses)
    assert (spoken(edited), links_of(edited)) == ("the link", [("the link", "target0")])
    assert not [loss for loss in losses.result() if loss.kind == "removed-link"]


@pytest.mark.parametrize("text", ["", "x"])
def test_a_paragraph_rewritten_whole_loses_its_link_and_says_so(text):
    losses = LossLog()
    edited = reworded(a_file("see ", ("the link", "link")), text, losses)
    assert spoken(edited) == text and links_of(edited) == []
    assert Loss("removed-link", "", 1) in losses.result()


def test_a_long_paragraph_is_matched_by_its_ends_and_its_link_still_stays():
    words = "word " * 2000
    edited = reworded(a_file(words, ("the link", "link"), words), words + "the link" + words + "!")
    assert links_of(edited) == [("the link", "target1")]
    assert spoken(edited).count("the link") == 1
