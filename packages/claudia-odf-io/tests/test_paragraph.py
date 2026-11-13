"""The text of one ODF paragraph, and changing it in place without losing what is around the words (D401).

A paragraph of the model has plain text; a paragraph of the file has that text cut into spans and links, with
bookmarks, footnotes and frames between the characters. Reading gives the text; ``set_text`` changes it by editing
the characters that differ and leaving every element where it was, so a changed word does not cost the paragraph
its links and its bold."""

from __future__ import annotations

import random
import re

import pytest
from lxml import etree

from claudia_odf_io import NS
from claudia_odf_io.paragraph import hidden_content, insert_elements, read_text, set_text

DECLS = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items() if p != "xml")


def para(inner: str, tag: str = "text:p") -> etree._Element:
    return etree.fromstring(f"<{tag} {DECLS}>{inner}</{tag}>")


def show(p: etree._Element) -> str:
    """The markup of the paragraph, without the namespace declarations."""
    return re.sub(r' xmlns:\w+="[^"]*"', "", etree.tostring(p, encoding="unicode"))


def edited(inner: str, new: str) -> str:
    p = para(inner)
    set_text(p, new)
    assert read_text(p) == new
    return show(p)


# -- reading ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("inner", "text"),
    [
        ("", ""),
        ("Hello", "Hello"),
        ("a <text:span>bold</text:span> word", "a bold word"),
        ('see <text:a xlink:href="https://example.org">here</text:a>.', "see here."),
        ("<text:span><text:span>deep</text:span></text:span>", "deep"),
        ("a<text:s/>b", "a b"),
        ('a<text:s text:c="3"/>b', "a   b"),
        ("a<text:tab/>b", "a\tb"),
        ("a<text:line-break/>b", "a\nb"),
        ("<text:s/>x", " x"),
        ("x<text:s/>", "x "),
    ],
)
def test_the_text_of_a_paragraph(inner, text):
    assert read_text(para(inner)) == text


@pytest.mark.parametrize(
    ("inner", "text"),
    [
        ("a  b", "a b"),  # runs of white space are one space
        ("a\n      b", "a b"),  # an indented file is not a paragraph with indentation
        ("  leading", "leading"),  # white space at the start does not count
        ("trailing  ", "trailing"),  # nor at the end
        ("a <text:span> b</text:span>", "a b"),  # across an element too
    ],
)
def test_white_space_in_the_file_is_collapsed_as_odf_says(inner, text):
    assert read_text(para(inner)) == text


@pytest.mark.parametrize(
    ("inner", "text"),
    [
        ('a<text:bookmark text:name="x"/>b', "ab"),
        ('a<text:bookmark-start text:name="x"/>b<text:bookmark-end text:name="x"/>c', "abc"),
        ('a<text:change text:change-id="ct1"/>b', "ab"),
        (
            'a<text:note text:note-class="footnote"><text:note-body><text:p>note</text:p></text:note-body>'
            "</text:note> b",
            "a b",
        ),
        ("a <text:page-number>3</text:page-number> b", "a  b"),  # a field shows what it computes, not what it is
        ("a<draw:frame><draw:text-box><text:p>inside</text:p></draw:text-box></draw:frame>b", "ab"),
        ("<text:ruby><text:ruby-base>漢字</text:ruby-base><text:ruby-text>かんじ</text:ruby-text></text:ruby>", "漢字"),
        ("tail after <text:soft-page-break/>break", "tail after break"),
    ],
)
def test_what_is_not_the_text_of_the_paragraph_is_not_read_as_text(inner, text):
    assert read_text(para(inner)) == text


def test_what_a_paragraph_holds_that_the_text_cannot_show_is_named():
    inner = (
        'a<text:note text:note-class="footnote"><text:note-body><text:p>n</text:p></text:note-body></text:note>'
        "<text:date>1.1.</text:date><draw:frame/><office:annotation/><text:bookmark/>"
    )
    assert hidden_content(para(inner)) == [
        "footnote",
        "field",
        "frame",
        "comment",
    ]  # a bookmark shows nothing: not named


# -- changing ----------------------------------------------------------------------------------------------------
def test_text_that_is_already_right_leaves_the_markup_exactly_alone():
    inner = 'a<text:s/>b\n  <text:span text:style-name="x">c</text:span>'
    p = para(inner)
    before = show(p)
    set_text(p, read_text(p))
    assert show(p) == before


def test_text_added_at_the_end_extends_the_last_run():
    assert edited("Hello", "Hello world") == "<text:p>Hello world</text:p>"


def test_text_added_inside_a_span_stays_in_the_span():
    out = edited('a <text:span text:style-name="B">bold</text:span> c', "a bolder c")
    assert out == '<text:p>a <text:span text:style-name="B">bolder</text:span> c</text:p>'


def test_text_added_right_after_a_span_continues_it_as_typing_does():
    out = edited('<text:span text:style-name="B">bold</text:span> plain', "bold, plain")
    assert out == '<text:p><text:span text:style-name="B">bold,</text:span> plain</text:p>'


def test_text_added_at_the_start_goes_into_the_first_run():
    out = edited('<text:span text:style-name="B">bold</text:span> plain', "Very bold plain")
    assert out == '<text:p><text:span text:style-name="B">Very bold</text:span> plain</text:p>'


def test_text_added_to_an_empty_paragraph_goes_into_the_paragraph():
    assert edited("", "new") == "<text:p>new</text:p>"


def test_a_word_replaced_keeps_the_markup_around_it():
    out = edited(
        'The <text:span text:style-name="B">committee</text:span> '
        '<text:a xlink:href="https://x.org">rejected</text:a> it.',
        "The committee approved it.",
    )
    assert "<text:span" in out and "committee</text:span>" in out
    assert "approved" in out and "rejected" not in out
    assert "xlink:href" not in out  # the link text is gone, so is the link: an empty link means nothing


def test_deleting_all_the_text_of_a_span_removes_the_span_and_keeps_what_follows():
    out = edited('a<text:span text:style-name="B">XX</text:span> b', "a b")
    assert out == "<text:p>a b</text:p>"


def test_deleting_across_a_span_boundary_trims_both_sides():
    out = edited('ab<text:span text:style-name="B">cd</text:span>ef', "aef")
    assert out == "<text:p>aef</text:p>"
    out = edited('ab<text:span text:style-name="B">cdX</text:span>ef', "abXef")
    assert out == '<text:p>ab<text:span text:style-name="B">X</text:span>ef</text:p>'


def test_an_empty_span_that_was_already_there_is_not_touched():
    p = para('a<text:span text:style-name="E"/>b')
    set_text(p, "aXb")
    assert '<text:span text:style-name="E"/>' in show(p)


def test_zero_width_things_stay_put_when_the_text_around_them_changes():
    inner = 'one <text:bookmark text:name="m"/>two <text:note text:note-class="footnote"/>three'
    out = edited(inner, "ONE two three")
    assert 'text:bookmark text:name="m"' in out and "<text:note " in out


def test_a_bookmark_inside_deleted_text_stays():
    out = edited('ab<text:bookmark text:name="m"/>cd', "ad")
    assert 'text:bookmark text:name="m"' in out


def test_spaces_that_would_collapse_are_written_as_text_s():
    assert edited("ab", "a  b") == '<text:p>a<text:s text:c="2"/>b</text:p>'
    assert edited("ab", "ab ") == "<text:p>ab<text:s/></text:p>"
    assert edited("ab", " ab") == "<text:p><text:s/>ab</text:p>"
    assert edited("ab", "a b") == "<text:p>a b</text:p>"  # one space between words is plain


def test_deleting_between_two_spaces_does_not_leave_two_plain_spaces():
    # "a b c" without the b: the two spaces that were each fine on their own would be read as one
    assert edited("a b c", "a  c") == '<text:p>a<text:s text:c="2"/>c</text:p>'


def test_tabs_and_line_breaks_are_elements():
    assert edited("ab", "a\tb") == "<text:p>a<text:tab/>b</text:p>"
    assert edited("ab", "a\nb") == "<text:p>a<text:line-break/>b</text:p>"


def test_deleting_some_of_a_run_of_spaces_shortens_it():
    assert edited('a<text:s text:c="3"/>b', "a  b") == '<text:p>a<text:s text:c="2"/>b</text:p>'


def test_deleting_all_of_a_run_of_spaces_removes_the_element_and_keeps_the_text_after_it():
    assert edited('a<text:s text:c="2"/>b', "ab") == "<text:p>ab</text:p>"
    assert edited('<text:span text:style-name="B">a<text:s/></text:span>b', "ab") == (
        '<text:p><text:span text:style-name="B">a</text:span>b</text:p>'
    )


def test_deleting_a_tab_or_a_line_break_keeps_the_text_after_it():
    assert edited("a<text:tab/>b", "ab") == "<text:p>ab</text:p>"
    assert edited("a<text:line-break/>b<text:line-break/>c", "ab c") == "<text:p>ab c</text:p>"


def test_white_space_of_an_indented_file_is_tidied_when_the_paragraph_changes():
    assert edited("one\n      two", "one two three") == "<text:p>one two three</text:p>"


def test_characters_that_xml_cannot_hold_are_replaced_not_raised():
    p = para("ab")
    set_text(p, "a\x01b")
    assert read_text(p) == "a�b"


def test_a_heading_is_a_paragraph_too():
    p = para("Title", tag="text:h")
    set_text(p, "Titles")
    assert read_text(p) == "Titles" and p.tag.endswith("}h")


# -- the guarantee, tried on many paragraphs ---------------------------------------------------------------------
def build_random_inner(rng: random.Random) -> str:
    parts = []
    for _ in range(rng.randint(0, 7)):
        kind = rng.choice(["text", "text", "span", "link", "s", "tab", "br", "mark", "note", "field"])
        word = "".join(rng.choice("abcdefg ") for _ in range(rng.randint(1, 6))).strip() or "w"
        parts.append(
            {
                "text": word,
                "span": f'<text:span text:style-name="S">{word}</text:span>',
                "link": f'<text:a xlink:href="https://x.org">{word}</text:a>',
                "s": f'<text:s text:c="{rng.randint(1, 3)}"/>',
                "tab": "<text:tab/>",
                "br": "<text:line-break/>",
                "mark": '<text:bookmark text:name="m"/>',
                "note": '<text:note text:note-class="footnote"><text:note-body><text:p>n</text:p></text:note-body>'
                "</text:note>",
                "field": "<text:page-number>1</text:page-number>",
            }[kind]
        )
    return "".join(parts)


def random_text(rng: random.Random, old: str) -> str:
    alphabet = "abcdefg  \t\n"
    new = list(old)
    for _ in range(rng.randint(0, 4)):
        at = rng.randint(0, len(new))
        if rng.random() < 0.5 and new:
            del new[at : at + rng.randint(1, 3)]
        else:
            new[at:at] = rng.choices(alphabet, k=rng.randint(1, 4))
    return "".join(new)


def test_whatever_the_paragraph_and_the_new_text_the_paragraph_reads_back_as_the_new_text():
    rng = random.Random(401)
    for _ in range(600):
        p = para(build_random_inner(rng))
        new = random_text(rng, read_text(p))
        markers_before = len(p.xpath("//text:bookmark | //text:note | //text:page-number", namespaces=NS))
        set_text(p, new)
        assert read_text(p) == new, show(p)
        markers_after = len(p.xpath("//text:bookmark | //text:note | //text:page-number", namespaces=NS))
        assert markers_after == markers_before  # nothing that is not text is lost when text changes


def test_the_result_is_valid_for_a_reader_that_collapses_white_space():
    """Written out and read again from the bytes, as another program would read it: the same text."""
    rng = random.Random(402)
    for _ in range(300):
        p = para(build_random_inner(rng))
        new = random_text(rng, read_text(p))
        set_text(p, new)
        again = etree.fromstring(etree.tostring(p))
        assert read_text(again) == new


def test_a_failure_to_edit_in_place_falls_back_to_rebuilding_the_text(monkeypatch):
    # if the opcodes were ever wrong, the paragraph must still end up with the right text, losing only its markup
    from claudia_odf_io import paragraph

    monkeypatch.setattr(paragraph, "_opcodes", lambda old, new: [])
    p = para('a <text:span text:style-name="B">b</text:span> c<text:bookmark text:name="m"/>')
    set_text(p, "a x c")
    assert read_text(p) == "a x c"
    assert 'text:bookmark text:name="m"' in show(p)  # what is not text still survives the fallback


# -- putting markers between characters -------------------------------------------------------------------------
def marker(tag: str = "change-start", **attributes: str) -> etree._Element:
    element = etree.Element(f"{{{NS['text']}}}{tag}", nsmap={"text": NS["text"]})
    for key, value in attributes.items():
        element.set(f"{{{NS['text']}}}{key.replace('_', '-')}", value)
    return element


def with_markers(inner: str, *placements: tuple[int, etree._Element]) -> tuple[str, str]:
    p = para(inner)
    before = read_text(p)
    insert_elements(p, list(placements))
    assert read_text(p) == before  # a marker is not text
    return show(p), read_text(p)


def test_a_marker_goes_between_the_characters_at_its_offset():
    assert with_markers("Hello world", (5, marker("bookmark", name="x")))[0] == (
        '<text:p>Hello<text:bookmark text:name="x"/> world</text:p>'
    )


def test_a_marker_at_the_start_and_one_at_the_end():
    shown, _ = with_markers(
        "abc", (0, marker("change-start", change_id="c1")), (3, marker("change-end", change_id="c1"))
    )
    assert shown == '<text:p><text:change-start text:change-id="c1"/>abc<text:change-end text:change-id="c1"/></text:p>'


def test_markers_at_the_same_offset_keep_the_order_they_were_given_in():
    shown, _ = with_markers("ab", (1, marker("bookmark", name="1")), (1, marker("bookmark", name="2")))
    assert shown == '<text:p>a<text:bookmark text:name="1"/><text:bookmark text:name="2"/>b</text:p>'


def test_a_marker_goes_inside_a_span_where_the_offset_is():
    shown, _ = with_markers("a <text:span>bold</text:span> word", (4, marker("bookmark", name="x")))
    assert shown == '<text:p>a <text:span>bo<text:bookmark text:name="x"/>ld</text:span> word</text:p>'


def test_a_marker_in_the_middle_of_a_run_of_spaces_cuts_the_run():
    shown, text = with_markers('a<text:s text:c="3"/>b', (3, marker("bookmark", name="x")))
    assert shown == '<text:p>a<text:s text:c="2"/><text:bookmark text:name="x"/><text:s/>b</text:p>'
    assert text == "a   b"


def test_a_marker_in_an_empty_paragraph():
    assert with_markers("", (0, marker("bookmark", name="x")))[0] == '<text:p><text:bookmark text:name="x"/></text:p>'


def test_a_marker_after_a_tab_and_one_before_a_line_break():
    shown, _ = with_markers(
        "a<text:tab/>b<text:line-break/>c", (2, marker("bookmark", name="x")), (3, marker("bookmark", name="y"))
    )
    assert shown == (
        '<text:p>a<text:tab/><text:bookmark text:name="x"/>b<text:bookmark text:name="y"/><text:line-break/>c</text:p>'
    )


def test_markers_never_change_the_text_whatever_the_paragraph_looks_like():
    rng = random.Random(7)
    pieces = [
        "word",
        " ",
        "  ",
        "<text:tab/>",
        "<text:line-break/>",
        "<text:span>sp</text:span>",
        "<text:bookmark text:name='b'/>",
    ]
    for _ in range(300):
        inner = "".join(rng.choice(pieces) for _ in range(rng.randint(0, 8)))
        p = para(inner)
        text = read_text(p)
        insert_elements(p, [(rng.randint(0, len(text)), marker("bookmark", name=f"m{i}")) for i in range(3)])
        assert read_text(p) == text
        assert len(p.findall(".//text:bookmark", {"text": NS["text"]})) >= 3
