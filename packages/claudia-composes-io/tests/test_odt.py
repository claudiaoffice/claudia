"""text_to_odt / odt_to_text / apply_edits_to_odt: the text app's OpenDocument import, export and edit-and-reexport
(D401, D402). Edit-and-reexport keeps what Claudia never modeled -- byte for byte where it was not edited."""

from __future__ import annotations

import re

import pytest
from claudia_composes_io import (
    UnsupportedEdit,
    apply_edits_to_odt,
    odt_export_losses,
    odt_import_losses,
    odt_to_text,
    text_to_odt,
)
from lxml import etree

from claudia_composes import DEFAULT_STYLE, Block, Suggestion, TextModel, TextRange
from claudia_odf_io import MIME, NS, Loss, LossLog, OdfError, new_package, problems, xml_safe
from claudia_opc_io import read_parts

DECLS = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items() if p != "xml")
HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'
STYLES = (
    f'{HEAD}<office:document-styles {DECLS} office:version="1.3"><office:styles>'
    '<style:style style:name="Standard" style:family="paragraph" style:class="text"/>'
    '<style:style style:name="Text_20_body" style:display-name="Text body" style:family="paragraph" '
    'style:parent-style-name="Standard"/>'
    '<style:style style:name="Heading_20_1" style:display-name="Heading 1" style:family="paragraph" '
    'style:parent-style-name="Standard" style:default-outline-level="1"/>'
    '<style:style style:name="Fancy" style:family="paragraph" style:parent-style-name="Standard"/>'
    "</office:styles></office:document-styles>"
)


def an_odt(body: str, *, automatic: str = "", styles: str = STYLES) -> bytes:
    content = (
        f'{HEAD}<office:document-content {DECLS} office:version="1.3"><office:scripts/><office:font-face-decls/>'
        f"<office:automatic-styles>{automatic}</office:automatic-styles>"
        f"<office:body><office:text>{body}</office:text></office:body></office:document-content>"
    )
    return new_package("text", content.encode(), styles.encode())


def model_of(*blocks: tuple[str, str]) -> TextModel:
    return TextModel([Block(f"b{i}", style, text) for i, (style, text) in enumerate(blocks, start=1)])


def body_of(data: bytes) -> etree._Element:
    root = etree.fromstring(read_parts(data)["content.xml"])
    found = root.find("office:body/office:text", NS)
    assert found is not None
    return found


def shown(element: etree._Element) -> str:
    return re.sub(r' xmlns:\w+="[^"]*"', "", etree.tostring(element, encoding="unicode"))


def paragraph_markup(data: bytes) -> list[str]:
    return [shown(e) for e in body_of(data).iterchildren() if e.tag in (f"{{{NS['text']}}}p", f"{{{NS['text']}}}h")]


# -- export ------------------------------------------------------------------------------------------------------
def test_an_exported_text_is_an_opendocument_text_file():
    data = text_to_odt(model_of((DEFAULT_STYLE, "Hello")))
    assert problems(data) == []
    assert read_parts(data)["mimetype"] == MIME["text"].encode()


def test_paragraphs_keep_their_text_and_order():
    data = text_to_odt(model_of((DEFAULT_STYLE, "First."), (DEFAULT_STYLE, "Second.")))
    assert paragraph_markup(data) == [
        '<text:p text:style-name="Standard">First.</text:p>',
        '<text:p text:style-name="Standard">Second.</text:p>',
    ]


@pytest.mark.parametrize(
    ("style", "markup"),
    [
        ("title", '<text:p text:style-name="Title">x</text:p>'),
        ("heading-1", '<text:h text:style-name="Heading_20_1" text:outline-level="1">x</text:h>'),
        ("heading-2", '<text:h text:style-name="Heading_20_2" text:outline-level="2">x</text:h>'),
        ("quote", '<text:p text:style-name="Quotations">x</text:p>'),
        ("body", '<text:p text:style-name="Standard">x</text:p>'),
    ],
)
def test_the_built_in_styles_map_to_the_styles_of_opendocument(style, markup):
    assert paragraph_markup(text_to_odt(model_of((style, "x")))) == [markup]


def test_a_style_the_file_has_no_name_for_falls_back_to_the_standard_one():
    assert paragraph_markup(text_to_odt(model_of(("my-style", "x")))) == [
        '<text:p text:style-name="Standard">x</text:p>'
    ]


def test_every_style_a_paragraph_uses_is_defined_in_the_file():
    data = text_to_odt(model_of(("title", "a"), ("heading-1", "b"), ("heading-2", "c"), ("quote", "d"), ("body", "e")))
    styles = etree.fromstring(read_parts(data)["styles.xml"])
    defined = {e.get(f"{{{NS['style']}}}name") for e in styles.iter(f"{{{NS['style']}}}style")}
    used = {e.get(f"{{{NS['text']}}}style-name") for e in body_of(data).iterchildren()}
    assert used <= defined


def test_the_file_has_a_page_so_that_a_program_can_lay_it_out():
    styles = read_parts(text_to_odt(model_of((DEFAULT_STYLE, "x"))))["styles.xml"]
    assert b"<style:page-layout " in styles and b"<style:master-page " in styles


def test_spaces_tabs_and_line_breaks_survive_the_trip():
    text = "a  b\tc\nd  "
    assert odt_to_text(text_to_odt(model_of((DEFAULT_STYLE, text)))).blocks[0].text == text


def test_characters_xml_cannot_hold_do_not_break_the_file():
    data = text_to_odt(model_of((DEFAULT_STYLE, "a\x00b\x0cc")))
    assert problems(data) == []
    assert odt_to_text(data).blocks[0].text == "a�b�c"


def test_the_same_model_gives_the_same_bytes():
    model = model_of((DEFAULT_STYLE, "x"))
    assert text_to_odt(model) == text_to_odt(model)


def test_an_empty_model_is_an_empty_but_valid_text():
    data = text_to_odt(TextModel())
    assert problems(data) == []


def suggestion_model() -> TextModel:
    model = model_of((DEFAULT_STYLE, "The committee rejected the proposal."))
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b1", 14, 22), "rejected", "approved", "tone")
    return model


def test_an_open_suggestion_becomes_a_tracked_change_a_reviewer_can_accept():
    data = text_to_odt(suggestion_model())
    body = body_of(data)
    regions = body.findall("text:tracked-changes/text:changed-region", NS)
    assert [r[0].tag.rpartition("}")[2] for r in regions] == ["deletion", "insertion"]
    deletion = regions[0][0]
    assert deletion.findtext("office:change-info/dc:creator", namespaces=NS) == "Claudia AI"
    assert deletion.findtext("text:p", namespaces=NS) == "rejected"
    assert paragraph_markup(data)[0].startswith('<text:p text:style-name="Standard">The committee <text:change ')
    assert "approved" in paragraph_markup(data)[0] and "rejected" not in paragraph_markup(data)[0]


def test_a_tracked_change_has_the_date_libreoffice_needs_and_no_invented_one():
    body = body_of(text_to_odt(suggestion_model()))
    dates = {d.text for d in body.iterfind(".//office:change-info/dc:date", NS)}
    assert dates == {"1970-01-01T00:00:00"}


def test_the_marks_in_the_text_point_at_their_changes():
    body = body_of(text_to_odt(suggestion_model()))
    ids = {r.get(f"{{{NS['text']}}}id") for r in body.iterfind("text:tracked-changes/text:changed-region", NS)}
    marks = {f"{{{NS['text']}}}{name}" for name in ("change", "change-start", "change-end")}
    used = {e.get(f"{{{NS['text']}}}change-id") for e in body.iter() if e.tag in marks}
    assert ids == used and len(ids) == 2


def test_a_remark_with_no_replacement_is_left_out():
    model = model_of((DEFAULT_STYLE, "Some text."))
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b1", 0, 4), "Some", None, "a remark")
    assert body_of(text_to_odt(model)).find("text:tracked-changes", NS) is None


def test_track_suggestions_false_exports_plain_text():
    data = text_to_odt(suggestion_model(), track_suggestions=False)
    assert body_of(data).find("text:tracked-changes", NS) is None
    assert odt_to_text(data).blocks[0].text == "The committee rejected the proposal."


def test_a_suggestion_that_only_inserts_has_no_deletion():
    model = model_of((DEFAULT_STYLE, "Hello world"))
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b1", 5, 5), "", ", dear", "warmer")
    kinds = [r[0].tag.rpartition("}")[2] for r in body_of(text_to_odt(model)).iterfind(".//text:changed-region", NS)]
    assert kinds == ["insertion"]


def test_two_suggestions_in_one_paragraph_keep_their_places():
    model = model_of((DEFAULT_STYLE, "one two three"))
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b1", 0, 3), "one", "1", "")
    model.suggestions["s2"] = Suggestion("s2", "Claudia AI", TextRange("b1", 8, 13), "three", "3", "")
    assert odt_to_text(text_to_odt(model)).blocks[0].text == "1 two 3"


def test_the_losses_of_an_export_name_what_the_file_cannot_hold():
    model = model_of(("remark", "x"), ("body", "y"), ("my-style", "z"))
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b2", 0, 1), "y", None, "a remark")
    assert odt_export_losses(model) == (Loss("style", "remark"), Loss("style", "my-style"), Loss("remark", "", 1))


def test_an_export_without_losses_reports_none():
    assert odt_export_losses(model_of(("title", "x"), ("body", "y"))) == ()


def test_authorship_of_runs_is_a_loss_because_opendocument_text_has_nowhere_for_it():
    from claudia_composes import Run

    model = TextModel([Block("b1", DEFAULT_STYLE, "ab", (Run(1, "ann"), Run(1, "ben")))])
    assert odt_export_losses(model) == (Loss("authorship", "", 1),)


# -- import --------------------------------------------------------------------------------------------------------
def test_an_imported_text_has_one_block_per_paragraph_in_order():
    model = odt_to_text(an_odt('<text:p text:style-name="Standard">One</text:p><text:p>Two</text:p>'))
    assert [(b.id, b.style, b.text) for b in model.blocks] == [("b1", "body", "One"), ("b2", "body", "Two")]
    assert model.blocks[0].runs[0].length == 3


def test_an_empty_text_imports_as_an_empty_model():
    assert odt_to_text(an_odt("")).blocks == TextModel().blocks


@pytest.mark.parametrize(
    ("markup", "style"),
    [
        ('<text:p text:style-name="Title">x</text:p>', "title"),
        ('<text:h text:style-name="Heading_20_1" text:outline-level="1">x</text:h>', "heading-1"),
        ('<text:h text:style-name="Heading_20_2" text:outline-level="2">x</text:h>', "heading-2"),
        ('<text:p text:style-name="Quotations">x</text:p>', "quote"),
        ('<text:p text:style-name="Text_20_body">x</text:p>', "body"),
        ('<text:h text:outline-level="1">x</text:h>', "heading-1"),
        ('<text:h text:outline-level="2">x</text:h>', "heading-2"),
        ('<text:p text:style-name="Fancy">x</text:p>', "body"),
    ],
)
def test_styles_map_back_to_the_styles_of_the_text_app(markup, style):
    assert odt_to_text(an_odt(markup)).blocks[0].style == style


def test_a_style_made_by_formatting_is_the_style_it_is_based_on():
    automatic = '<style:style style:name="P1" style:family="paragraph" style:parent-style-name="Heading_20_1"/>'
    assert (
        odt_to_text(an_odt('<text:p text:style-name="P1">x</text:p>', automatic=automatic)).blocks[0].style
        == "heading-1"
    )


def test_a_deeper_heading_is_body_text_and_says_so():
    data = an_odt('<text:h text:outline-level="3">x</text:h>')
    assert odt_to_text(data).blocks[0].style == "body"
    assert Loss("heading-level", "3") in odt_import_losses(data)


def test_paragraphs_in_lists_and_sections_are_blocks_too():
    data = an_odt(
        "<text:list><text:list-item><text:p>a</text:p><text:list><text:list-item><text:p>b</text:p>"
        "</text:list-item></text:list></text:list-item></text:list>"
        '<text:section text:name="S"><text:p>c</text:p></text:section><text:p>d</text:p>'
    )
    assert [b.text for b in odt_to_text(data).blocks] == ["a", "b", "c", "d"]


def test_a_table_is_not_in_the_model_and_is_reported():
    data = an_odt(
        "<text:p>before</text:p><table:table table:name='T'><table:table-row><table:table-cell>"
        "<text:p>in a cell</text:p></table:table-cell></table:table-row></table:table><text:p>after</text:p>"
    )
    assert [b.text for b in odt_to_text(data).blocks] == ["before", "after"]
    assert Loss("table", "", 1) in odt_import_losses(data)


def test_what_the_text_does_not_show_is_reported():
    data = an_odt(
        "<text:p>a <text:span text:style-name='B'>bold</text:span> and "
        "<text:a xlink:href='https://example.org'>link</text:a>"
        "<text:note text:note-class='footnote'><text:note-citation>1</text:note-citation>"
        "<text:note-body><text:p>n</text:p></text:note-body></text:note>"
        "<draw:frame><draw:image xlink:href='Pictures/a.png'/></draw:frame></text:p>"
        "<text:list><text:list-item><text:p>x</text:p></text:list-item></text:list>"
    )
    losses = odt_import_losses(data)
    assert {Loss("formatting"), Loss("link"), Loss("footnote"), Loss("frame"), Loss("list")} <= set(losses)


def test_existing_tracked_changes_are_reported():
    data = an_odt(
        '<text:tracked-changes><text:changed-region text:id="c1"><text:insertion><office:change-info>'
        "<dc:creator>x</dc:creator></office:change-info></text:insertion></text:changed-region>"
        "</text:tracked-changes><text:p>a</text:p>"
    )
    assert Loss("tracked-change", "", 1) in odt_import_losses(data)


def test_an_unknown_style_is_body_text_and_named_in_the_losses():
    data = an_odt('<text:p text:style-name="Mystery_20_Style">x</text:p>')
    assert odt_to_text(data).blocks[0].style == "body"
    assert Loss("style", "Mystery Style") in odt_import_losses(data)


def test_a_file_that_is_not_opendocument_text_is_an_error_with_a_sentence():
    with pytest.raises(OdfError, match="not an OpenDocument"):
        odt_to_text(b"not a zip")
    with pytest.raises(OdfError, match="text document"):
        odt_to_text(new_package("spreadsheet", b"<a/>", b"<a/>"))


def test_a_text_survives_the_trip_through_export_and_import():
    model = model_of(("title", "T"), ("heading-1", "H"), ("body", "b"), ("quote", "q"))
    again = odt_to_text(text_to_odt(model))
    assert [(b.id, b.style, b.text) for b in again.blocks] == [(b.id, b.style, b.text) for b in model.blocks]


# -- edit and re-export ----------------------------------------------------------------------------------------
RICH = (
    '<text:h text:style-name="Heading_20_1" text:outline-level="1">Title</text:h>'
    '<text:p text:style-name="Standard">Hello <text:span text:style-name="B">bold</text:span> world and '
    '<text:a xlink:href="https://example.org">a link</text:a><text:bookmark text:name="m"/>'
    "<text:note text:note-class='footnote'><text:note-citation>1</text:note-citation>"
    "<text:note-body><text:p>note</text:p></text:note-body></text:note>.</text:p>"
    "<table:table table:name='T'><table:table-row><table:table-cell><text:p>cell</text:p></table:table-cell>"
    "</table:table-row></table:table>"
    '<text:list><text:list-item><text:p text:style-name="Standard">item</text:p></text:list-item></text:list>'
    '<text:p text:style-name="Standard">Last &apos;one&apos;</text:p>'
)


def edit(original: bytes, change) -> tuple[bytes, TextModel, TextModel]:
    baseline = odt_to_text(original)
    current = odt_to_text(original)
    change(current)
    return apply_edits_to_odt(original, baseline, current), baseline, current


def retext(model: TextModel, block_id: str, text: str, style: str | None = None) -> None:
    index = next(i for i, b in enumerate(model.blocks) if b.id == block_id)
    old = model.blocks[index]
    model.blocks[index] = Block(old.id, style or old.style, text, ())


def test_without_edits_the_file_comes_back_exactly_as_it_was():
    original = an_odt(RICH)
    assert apply_edits_to_odt(original, odt_to_text(original), odt_to_text(original)) == original


def content(data: bytes) -> str:
    return read_parts(data)["content.xml"].decode()


def test_an_edit_changes_that_paragraph_and_nothing_else_in_the_file():
    original = an_odt(RICH)
    edited, *_ = edit(original, lambda m: retext(m, "b2", "Hello bold planet and a link."))
    before, after = read_parts(original), read_parts(edited)
    assert {n for n in before if before[n] != after[n]} == {"content.xml"}
    old, new = content(original), content(edited)
    start = old.index('<text:p text:style-name="Standard">Hello')
    end = old.index("</text:note>.</text:p>", start) + len("</text:note>.</text:p>")
    assert new.startswith(old[:start]) and new.endswith(old[end:])
    assert "planet" in new[start:] and "world" not in new[start:]


def test_an_edited_paragraph_still_has_its_links_notes_and_bookmarks():
    edited, *_ = edit(an_odt(RICH), lambda m: retext(m, "b2", "Hello bold planet and a link."))
    p = body_of(edited).findall("text:p", NS)[0]
    assert p.find("text:span", NS) is not None and p.find("text:a", NS) is not None
    assert p.find("text:bookmark", NS) is not None and p.find("text:note", NS) is not None


def test_the_table_the_list_and_the_last_paragraph_are_byte_for_byte_the_same():
    original = an_odt(RICH)
    edited, *_ = edit(original, lambda m: retext(m, "b1", "New title"))
    old, new = content(original), content(edited)
    assert new[new.index("<table:table") :] == old[old.index("<table:table") :]


def test_an_edited_file_is_still_a_valid_package():
    edited, *_ = edit(an_odt(RICH), lambda m: retext(m, "b3", "changed"))
    assert problems(edited) == []


def test_a_style_change_from_paragraph_to_heading_makes_it_a_heading():
    edited, *_ = edit(an_odt(RICH), lambda m: retext(m, "b2", "Hello", style="heading-2"))
    heading = body_of(edited).findall("text:h", NS)[1]
    assert heading.get(f"{{{NS['text']}}}outline-level") == "2"
    assert heading.get(f"{{{NS['text']}}}style-name") == "Heading_20_2"


def test_the_style_it_changes_to_is_added_to_the_file_when_the_file_has_none():
    edited, *_ = edit(an_odt(RICH), lambda m: retext(m, "b2", "Hello", style="heading-2"))
    assert b'style:name="Heading_20_2"' in read_parts(edited)["styles.xml"]
    assert problems(edited) == []


def test_a_style_the_file_already_has_is_not_added_again():
    edited, *_ = edit(an_odt(RICH), lambda m: retext(m, "b2", "Hello", style="heading-1"))
    assert read_parts(edited)["styles.xml"] == read_parts(an_odt(RICH))["styles.xml"]


def test_a_heading_changed_to_body_text_becomes_a_paragraph():
    edited, *_ = edit(an_odt(RICH), lambda m: retext(m, "b1", "Title", style="body"))
    first = next(iter(body_of(edited)))
    assert first.tag == f"{{{NS['text']}}}p" and first.get(f"{{{NS['text']}}}outline-level") is None


def test_a_block_added_in_the_middle_goes_where_it_was_added():
    def add(model: TextModel) -> None:
        model.blocks.insert(1, Block("b9", "body", "inserted"))

    edited, *_ = edit(an_odt(RICH), add)
    assert [b.text for b in odt_to_text(edited).blocks] == [
        "Title",
        "inserted",
        "Hello bold world and a link.",
        "item",
        "Last 'one'",
    ]


def test_blocks_added_at_the_start_the_end_and_in_a_row_keep_their_order():
    def add(model: TextModel) -> None:
        model.blocks.insert(0, Block("n1", "body", "first"))
        model.blocks.append(Block("n2", "body", "x"))
        model.blocks.append(Block("n3", "body", "y"))

    edited, *_ = edit(an_odt(RICH), add)
    assert [b.text for b in odt_to_text(edited).blocks] == [
        "first",
        "Title",
        "Hello bold world and a link.",
        "item",
        "Last 'one'",
        "x",
        "y",
    ]


def test_blocks_added_to_an_empty_text_are_all_there():
    original = an_odt("")

    def add(model: TextModel) -> None:
        model.blocks.extend([Block("n1", "body", "a"), Block("n2", "heading-1", "b")])

    edited, *_ = edit(original, add)
    assert [(b.style, b.text) for b in odt_to_text(edited).blocks] == [("body", "a"), ("heading-1", "b")]
    assert problems(edited) == []


def test_a_block_added_after_a_list_item_is_a_paragraph_of_that_item():
    """The model has no bullets to give it, so it is the paragraph next to the one it was added after -- inside the
    item, where it is valid and nothing about the list changes."""

    def add(model: TextModel) -> None:
        model.blocks.insert(3, Block("n1", "body", "after the item"))

    edited, *_ = edit(an_odt(RICH), add)
    item = body_of(edited).find("text:list/text:list-item", NS)
    assert item is not None and [shown(p).count("item") for p in item] == [1, 1]
    assert [b.text for b in odt_to_text(edited).blocks][3] == "after the item"


def test_a_removed_block_is_gone_and_the_rest_is_untouched():
    original = an_odt(RICH)
    losses = LossLog()
    baseline = odt_to_text(original)
    current = odt_to_text(original)
    current.blocks.pop(2)  # the list item
    edited = apply_edits_to_odt(original, baseline, current, losses=losses)
    assert [b.text for b in odt_to_text(edited).blocks] == ["Title", "Hello bold world and a link.", "Last 'one'"]
    assert b"<table:table " in read_parts(edited)["content.xml"]
    assert losses.result() == ()


def test_removing_a_paragraph_with_a_note_says_the_note_went_with_it():
    original = an_odt(RICH)
    losses = LossLog()
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.blocks.pop(1)
    apply_edits_to_odt(original, baseline, current, losses=losses)
    assert Loss("removed-footnote", "", 1) in losses.result()


def test_every_block_removed_leaves_a_valid_text_without_paragraphs():
    original = an_odt("<text:p>a</text:p><text:p>b</text:p>")
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.blocks.clear()
    edited = apply_edits_to_odt(original, baseline, current)
    assert paragraph_markup(edited) == [] and problems(edited) == []


def test_an_unchanged_empty_text_stays_as_it_is():
    original = an_odt("")
    assert apply_edits_to_odt(original, odt_to_text(original), odt_to_text(original)) == original


def test_reordering_blocks_is_not_patched_onto_a_file():
    original = an_odt(RICH)
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.blocks[0], current.blocks[1] = current.blocks[1], current.blocks[0]
    with pytest.raises(UnsupportedEdit):
        apply_edits_to_odt(original, baseline, current)


def test_a_baseline_from_another_file_is_refused():
    original = an_odt(RICH)
    with pytest.raises(UnsupportedEdit):
        apply_edits_to_odt(original, model_of(("body", "x")), model_of(("body", "y")))


def test_a_suggestion_becomes_a_tracked_change_in_the_existing_paragraph():
    original = an_odt(RICH)
    baseline = odt_to_text(original)
    current = odt_to_text(original)
    current.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b2", 6, 10), "bold", "plain", "")
    edited = apply_edits_to_odt(original, baseline, current)
    body = body_of(edited)
    assert len(body.findall("text:tracked-changes/text:changed-region", NS)) == 2
    assert "plain" in shown(body.findall("text:p", NS)[0]) and 'xlink:href="https://example.org"' in shown(body)
    assert problems(edited) == []


def test_new_change_ids_do_not_clash_with_the_ones_the_file_has():
    original = an_odt(
        '<text:tracked-changes><text:changed-region text:id="ct1" xml:id="ct1"><text:insertion><office:change-info>'
        "<dc:creator>x</dc:creator></office:change-info></text:insertion></text:changed-region></text:tracked-changes>"
        "<text:p>one two</text:p>"
    )
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b1", 0, 3), "one", "1", "")
    body = body_of(apply_edits_to_odt(original, baseline, current))
    ids = [r.get(f"{{{NS['text']}}}id") for r in body.iterfind("text:tracked-changes/text:changed-region", NS)]
    assert len(ids) == len(set(ids)) == 3 and ids[0] == "ct1"


def test_a_file_that_is_not_text_is_refused_with_a_sentence():
    with pytest.raises(OdfError):
        apply_edits_to_odt(b"junk", TextModel(), TextModel())


# -- the property that matters: whatever is edited, the file is the edited text and nothing else changed -----------
def test_random_edits_of_a_rich_file_always_give_the_edited_text_and_leave_the_rest_alone():
    import random

    rng = random.Random(401)
    words = ["alpha", "beta", "gamma", "  ", "\t", "x,", "(y)", "ünï", "…"]
    styles = ["body", "title", "heading-1", "heading-2", "quote"]
    original = an_odt(RICH)
    old = content(original)
    for _ in range(150):
        baseline, current = odt_to_text(original), odt_to_text(original)
        for index in range(len(current.blocks)):
            kind = rng.random()
            block = current.blocks[index]
            if kind < 0.35:
                text = "".join(rng.choice(words) + rng.choice([" ", ""]) for _ in range(rng.randint(0, 5)))
                current.blocks[index] = Block(block.id, rng.choice(styles), text.strip(" "), ())
        for number in range(rng.randint(0, 2)):
            current.blocks.insert(
                rng.randint(0, len(current.blocks)), Block(f"n{number}", rng.choice(styles), f"new {number}")
            )
        if rng.random() < 0.3 and len(current.blocks) > 1:
            current.blocks.pop(rng.randrange(len(current.blocks)))
        edited = apply_edits_to_odt(original, baseline, current)
        assert problems(edited) == []
        again = odt_to_text(edited)
        assert [(b.style, b.text) for b in again.blocks] == [(b.style, xml_safe(b.text)) for b in current.blocks]
        new = content(edited)
        assert new.endswith("</office:text></office:body></office:document-content>")
        assert old[old.index("<table:table") : old.index("</table:table>")] in new  # the table is never touched
