"""Lists in an odt: written from the items of the model, read back as items, and patched into a file that has them
(D453). The one property that matters: whatever is done, the file says the same lists the model does."""

from __future__ import annotations

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
from test_odt import RICH, an_odt, body_of, content, shown

from claudia_composes import Paragraph, TextModel
from claudia_core import ListBook, ListDef, ListItem
from claudia_odf_io import NS, Loss, LossLog, problems
from claudia_opc_io import read_parts

T = f"{{{NS['text']}}}"


def text_of(*rows: tuple, lists: tuple[ListDef, ...] = (ListDef("l1", "bullets"),)) -> TextModel:
    """A text from ``(text, list id | None, level)`` rows."""
    paragraphs = [
        Paragraph(f"b{n}", "body", row[0], item=ListItem(row[1], row[2]) if len(row) > 1 and row[1] else None)
        for n, row in enumerate(rows, start=1)
    ]
    return TextModel(paragraphs, lists=ListBook(lists))


def shape(model: TextModel) -> list[tuple]:
    """What a text says, its lists named by when they first appear (an id is the model's, not the file's): the
    paragraphs with their items, and the lists that are used with their scheme, start and name."""
    names: dict[str, str] = {}
    rows = []
    for paragraph in model.paragraphs:
        item = None
        if paragraph.item is not None:
            item = (names.setdefault(paragraph.item.list, f"L{len(names) + 1}"), paragraph.item.level)
        rows.append((paragraph.style, paragraph.text, item))
    used = {names[list_id]: (d.scheme, d.start, d.name) for list_id in names for d in [model.lists.get(list_id)]}
    return [*rows, ("lists", sorted(used.items()))]


def again(model: TextModel) -> TextModel:
    return odt_to_text(text_to_odt(model))


# -- export and import -------------------------------------------------------------------------------------------
def test_items_are_written_as_the_items_of_a_list():
    data = text_to_odt(text_of(("a", "l1", 0), ("b", "l1", 0)))
    assert problems(data) == []
    top = body_of(data).find("text:list", NS)
    assert top is not None and len(top.findall("text:list-item/text:p", NS)) == 2
    assert top.get(f"{T}style-name")


def test_a_list_comes_back_as_the_same_list():
    model = text_of(
        ("one", "l1", 0), ("plain", None, 0), ("two", "l1", 0), lists=(ListDef("l1", "numbers", 3, "Steps"),)
    )
    assert shape(again(model)) == shape(model)


def test_the_scheme_the_start_and_the_name_are_in_the_style_of_the_list():
    data = text_to_odt(text_of(("one", "l1", 0), lists=(ListDef("l1", "numbers", 3, "Steps"),)))
    root = etree.fromstring(read_parts(data)["content.xml"])
    style = root.find("office:automatic-styles/text:list-style", NS)
    assert style is not None and style.get(f"{{{NS['style']}}}display-name") == "Steps"
    first = style[0]
    assert first.tag == f"{T}list-level-style-number" and first.get(f"{T}start-value") == "3"


@pytest.mark.parametrize("scheme", ["bullets", "numbers"])
def test_nested_levels_and_skipped_levels_come_back(scheme):
    rows = [("a", "l1", 0), ("b", "l1", 1), ("c", "l1", 2), ("d", "l1", 1), ("e", "l1", 0), ("f", "l1", 2)]
    model = text_of(*rows, lists=(ListDef("l1", scheme),))
    assert shape(again(model)) == shape(model)


def test_the_levels_are_nested_lists_inside_the_item_before():
    data = text_to_odt(text_of(("a", "l1", 0), ("b", "l1", 1)))
    top = body_of(data).find("text:list", NS)
    assert top is not None and top.find("text:list-item/text:list/text:list-item/text:p", NS) is not None


def test_two_lists_next_to_each_other_stay_two_lists():
    model = text_of(("a", "l1", 0), ("b", "l2", 0), lists=(ListDef("l1", "bullets"), ListDef("l2", "numbers")))
    assert shape(again(model)) == shape(model)
    assert len(body_of(text_to_odt(model)).findall("text:list", NS)) == 2


def test_a_list_that_goes_on_after_a_paragraph_is_one_list_that_continues():
    model = text_of(("a", "l1", 0), ("between", None, 0), ("b", "l1", 0), lists=(ListDef("l1", "numbers"),))
    data = text_to_odt(model)
    first, second = body_of(data).findall("text:list", NS)
    assert second.get(f"{T}continue-list") == first.get("{http://www.w3.org/XML/1998/namespace}id")
    assert shape(odt_to_text(data)) == shape(model)


def test_a_list_nobody_uses_is_not_in_the_file():
    data = text_to_odt(text_of(("a", None, 0), lists=(ListDef("l1", "bullets"),)))
    assert b"list-style" not in read_parts(data)["content.xml"]


def test_a_heading_in_a_list_is_still_a_heading():
    model = TextModel(
        [Paragraph("b1", "heading-1", "H", item=ListItem("l1", 0))], lists=ListBook([ListDef("l1", "bullets")])
    )
    assert shape(again(model)) == shape(model)
    assert body_of(text_to_odt(model)).find("text:list/text:list-item/text:h", NS) is not None


def test_lists_are_no_loss_of_an_export():
    assert odt_export_losses(text_of(("a", "l1", 0))) == ()


# -- what a file has ------------------------------------------------------------------------------------------------
NUMBERED = (
    '<text:list-style style:name="WWNum1"><text:list-level-style-number text:level="1" style:num-format="1" '
    'style:num-suffix="." text:start-value="5"/><text:list-level-style-number text:level="2" style:num-format="a" '
    'style:num-suffix="."/></text:list-style>'
)


def test_a_numbered_list_of_a_file_is_a_numbered_list_of_the_model():
    data = an_odt(
        '<text:list text:style-name="WWNum1"><text:list-item><text:p>a</text:p><text:list><text:list-item>'
        "<text:p>b</text:p></text:list-item></text:list></text:list-item><text:list-item><text:p>c</text:p>"
        "</text:list-item></text:list>",
        automatic=NUMBERED,
    )
    model = odt_to_text(data)
    assert [(b.text, b.item.level) for b in model.paragraphs if b.item] == [("a", 0), ("b", 1), ("c", 0)]
    assert model.lists.get("l1") == ListDef("l1", "numbers", 5, None)
    assert odt_import_losses(data) == ()


def test_a_second_paragraph_of_an_item_is_not_an_item():
    data = an_odt("<text:list><text:list-item><text:p>a</text:p><text:p>more</text:p></text:list-item></text:list>")
    assert [b.item is not None for b in odt_to_text(data).paragraphs] == [True, False]


def test_a_list_without_a_style_is_a_bullet_list_whose_look_is_reported():
    data = an_odt("<text:list><text:list-item><text:p>a</text:p></text:list-item></text:list>")
    assert odt_to_text(data).lists.get("l1").scheme == "bullets"
    assert odt_import_losses(data) == (Loss("list-look", "", 1),)


def test_numbers_drawn_as_roman_numerals_become_a_scheme_of_the_document_and_are_no_loss():
    """E9.22: schemes are document data, so a look the built-in ones lack is kept as a scheme of its own."""
    style = (
        '<text:list-style style:name="R" style:display-name="Articles"><text:list-level-style-number text:level="1" '
        'style:num-format="I" style:num-prefix="Art. " style:num-suffix=":"/></text:list-style>'
    )
    data = an_odt(
        '<text:list text:style-name="R"><text:list-item><text:p>a</text:p></text:list-item></text:list>',
        automatic=style,
    )
    model = odt_to_text(data)
    scheme = model.schemes.get(model.lists.get("l1").scheme)
    assert (scheme.name, scheme.marker((4,))) == ("Articles", "Art. IV:")
    assert Loss("list-look", "", 1) not in odt_import_losses(data)
    again = odt_to_text(text_to_odt(model))
    assert again.schemes.get(again.lists.get("l1").scheme).marker((4,)) == "Art. IV:"


def test_a_level_the_model_cannot_draw_is_still_reported_as_another_look():
    style = (
        '<text:list-style style:name="R"><text:list-level-style-number text:level="1" '
        'style:num-format="１, ２, ３, ..." style:num-suffix="."/></text:list-style>'
    )
    data = an_odt(
        '<text:list text:style-name="R"><text:list-item><text:p>a</text:p></text:list-item></text:list>',
        automatic=style,
    )
    assert odt_to_text(data).lists.get("l1").scheme == "numbers"
    assert Loss("list-look", "", 1) in odt_import_losses(data)


def test_a_list_that_continues_another_is_one_list():
    data = an_odt(
        '<text:list xml:id="x1" text:style-name="WWNum1">'
        "<text:list-item><text:p>a</text:p></text:list-item></text:list>"
        "<text:p>between</text:p>"
        '<text:list text:continue-list="x1" text:style-name="WWNum1">'
        "<text:list-item><text:p>b</text:p></text:list-item></text:list>",
        automatic=NUMBERED,
    )
    model = odt_to_text(data)
    assert [b.item.list for b in model.paragraphs if b.item] == ["l1", "l1"]
    assert len(model.lists) == 1


def test_a_list_that_only_follows_another_of_the_same_style_is_a_new_list():
    data = an_odt(
        '<text:list text:style-name="WWNum1"><text:list-item><text:p>a</text:p></text:list-item></text:list>'
        '<text:list text:style-name="WWNum1"><text:list-item><text:p>b</text:p></text:list-item></text:list>',
        automatic=NUMBERED,
    )
    assert [b.item.list for b in odt_to_text(data).paragraphs] == ["l1", "l2"]


def test_levels_deeper_than_the_model_has_are_the_deepest_and_say_so():
    nest = "".join("<text:list><text:list-item>" for _ in range(11))
    close = "</text:list-item></text:list>" * 11
    data = an_odt(f"{nest}<text:p>deep</text:p>{close}")
    assert odt_to_text(data).paragraphs[0].item.level == 8
    assert Loss("list-depth", "", 1) in odt_import_losses(data)


# -- editing a file that has lists ----------------------------------------------------------------------------------
LIST_FILE = (
    '<text:p text:style-name="Standard">before</text:p>'
    '<text:list text:style-name="WWNum1"><text:list-item><text:p text:style-name="Standard">one</text:p>'
    '<text:list><text:list-item><text:p text:style-name="Standard">one-a</text:p></text:list-item></text:list>'
    '</text:list-item><text:list-item><text:p text:style-name="Standard">two</text:p></text:list-item></text:list>'
    '<text:p text:style-name="Standard">after</text:p>'
)


def an_edited(original: bytes, change, **options) -> tuple[bytes, TextModel]:
    baseline, current = odt_to_text(original), odt_to_text(original)
    change(current)
    edited = apply_edits_to_odt(original, baseline, current, **options)
    assert problems(edited) == []
    assert shape(odt_to_text(edited)) == shape(current), (shown(body_of(edited)), shape(current))
    return edited, current


def index(model: TextModel, text: str) -> int:
    return next(i for i, b in enumerate(model.paragraphs) if b.text == text)


def test_a_file_with_lists_comes_back_as_it_was_when_nothing_changed():
    original = an_odt(LIST_FILE, automatic=NUMBERED)
    assert apply_edits_to_odt(original, odt_to_text(original), odt_to_text(original)) == original


def test_editing_the_words_of_an_item_changes_that_paragraph_only():
    original = an_odt(LIST_FILE, automatic=NUMBERED)

    def edit(model: TextModel) -> None:
        old = model.paragraphs[index(model, "two")]
        model.paragraphs[index(model, "two")] = Paragraph(old.id, old.style, "second", (), old.item)

    edited, _ = an_edited(original, edit)
    old, new = content(original), content(edited)
    assert new.replace("second", "two") == old


def test_an_item_added_after_the_last_item_is_the_next_item_of_the_list():
    def add(model: TextModel) -> None:
        model.paragraphs.insert(index(model, "two") + 1, Paragraph("n1", "body", "three", item=ListItem("l1", 0)))

    edited, _ = an_edited(an_odt(LIST_FILE, automatic=NUMBERED), add)
    assert len(body_of(edited).findall("text:list", NS)) == 1


def test_an_item_added_below_an_item_goes_one_level_deeper():
    def add(model: TextModel) -> None:
        model.paragraphs.insert(index(model, "two") + 1, Paragraph("n1", "body", "two-a", item=ListItem("l1", 1)))

    an_edited(an_odt(LIST_FILE, automatic=NUMBERED), add)


def test_an_item_added_at_the_top_of_the_text_starts_a_list_of_its_own():
    def add(model: TextModel) -> None:
        model.lists.add(ListDef("l9", "numbers"))
        model.paragraphs.insert(0, Paragraph("n1", "body", "first", item=ListItem("l9", 0)))

    edited, _ = an_edited(an_odt(LIST_FILE, automatic=NUMBERED), add)
    assert next(iter(body_of(edited))).tag == f"{T}list"


def test_a_paragraph_that_becomes_an_item_is_wrapped_in_a_list():
    def add(model: TextModel) -> None:
        model.lists.add(ListDef("l7", "bullets"))
        old = model.paragraphs[index(model, "before")]
        model.paragraphs[index(model, "before")] = Paragraph(old.id, old.style, old.text, old.runs, ListItem("l7", 0))

    edited, _ = an_edited(an_odt(LIST_FILE, automatic=NUMBERED), add)
    assert content(edited).count("<text:list ") == content(an_odt(LIST_FILE)).count("<text:list ") + 1


def test_an_item_that_stops_being_one_is_a_paragraph():
    def unlist(model: TextModel) -> None:
        old = model.paragraphs[index(model, "two")]
        model.paragraphs[index(model, "two")] = Paragraph(old.id, old.style, old.text, old.runs, None)

    edited, _ = an_edited(an_odt(LIST_FILE, automatic=NUMBERED), unlist)
    assert "<text:list-item><text:p" in content(edited)


def test_an_item_moved_a_level_is_in_the_other_list_of_the_tree():
    def indent(model: TextModel) -> None:
        old = model.paragraphs[index(model, "two")]
        model.paragraphs[index(model, "two")] = Paragraph(old.id, old.style, old.text, old.runs, ListItem("l1", 1))

    an_edited(an_odt(LIST_FILE, automatic=NUMBERED), indent)


def test_a_removed_item_leaves_no_empty_item_behind():
    def remove(model: TextModel) -> None:
        del model.paragraphs[index(model, "two")]

    edited, _ = an_edited(an_odt(LIST_FILE, automatic=NUMBERED), remove)
    assert "<text:list-item/>" not in content(edited) and "<text:list-item></text:list-item>" not in content(edited)


def test_a_list_all_of_whose_items_are_removed_is_gone():
    def remove(model: TextModel) -> None:
        for text in ("one", "one-a", "two"):
            del model.paragraphs[index(model, text)]

    edited, _ = an_edited(an_odt(LIST_FILE, automatic=NUMBERED), remove)
    assert body_of(edited).find("text:list", NS) is None


def test_a_list_changed_from_bullets_to_numbers_gets_a_style_that_counts():
    def renumber(model: TextModel) -> None:
        model.lists.replace(ListDef("l1", "bullets", 1, None))

    original = an_odt(LIST_FILE, automatic=NUMBERED)
    edited, _ = an_edited(original, renumber)
    assert b"list-level-style-bullet" in read_parts(edited)["content.xml"]
    assert body_of(edited).find("text:list", NS).get(f"{T}style-name") != "WWNum1"


def test_a_paragraph_after_the_last_item_is_after_the_list_not_in_its_item():
    def add(model: TextModel) -> None:
        model.paragraphs.insert(index(model, "two") + 1, Paragraph("n1", "body", "between"))

    edited, _ = an_edited(an_odt(LIST_FILE, automatic=NUMBERED), add)
    assert [child.tag for child in body_of(edited)][:3] == [f"{T}p", f"{T}list", f"{T}p"]


def test_a_paragraph_between_two_items_splits_the_list_and_both_parts_are_one_list():
    def add(model: TextModel) -> None:
        model.paragraphs.insert(index(model, "two"), Paragraph("n1", "body", "between"))

    edited, _ = an_edited(an_odt(LIST_FILE, automatic=NUMBERED), add)
    assert len(body_of(edited).findall("text:list", NS)) == 2


def test_a_list_with_a_table_in_an_item_cannot_be_restructured():
    table = (
        "<table:table table:name='T'><table:table-row><table:table-cell><text:p>x</text:p></table:table-cell>"
        "</table:table-row></table:table>"
    )
    original = an_odt(f"<text:list><text:list-item><text:p>a</text:p>{table}</text:list-item></text:list>")
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.paragraphs[0] = Paragraph("b1", "body", "a", (), None)
    with pytest.raises(UnsupportedEdit, match="list"):
        apply_edits_to_odt(original, baseline, current)


def test_removing_an_item_says_what_went_with_it():
    original = an_odt(
        "<text:list><text:list-item><text:p>a<text:note text:note-class='footnote'><text:note-citation>1"
        "</text:note-citation><text:note-body><text:p>n</text:p></text:note-body></text:note></text:p>"
        "</text:list-item></text:list>"
    )
    baseline, current = odt_to_text(original), odt_to_text(original)
    current.paragraphs.clear()
    losses = LossLog()
    apply_edits_to_odt(original, baseline, current, losses=losses)
    assert Loss("removed-footnote", "", 1) in losses.result()


def test_a_file_that_is_rich_in_lists_and_everything_else_survives_any_edit():
    import random

    rng = random.Random(453)
    original = an_odt(RICH + LIST_FILE, automatic=NUMBERED)
    table = content(original)[content(original).index("<table:table") : content(original).index("</table:table>")]
    for _ in range(200):
        baseline, current = odt_to_text(original), odt_to_text(original)
        current.lists.add(ListDef("l9", "numbers"))
        for position in range(len(current.paragraphs)):
            paragraph = current.paragraphs[position]
            roll = rng.random()
            if roll < 0.25:
                item = rng.choice([None, ListItem("l1", rng.randint(0, 3)), ListItem("l9", rng.randint(0, 2))])
                if paragraph.item is not None and item is not None and item.list == "l1" and "l1" not in baseline.lists:
                    item = None
                current.paragraphs[position] = Paragraph(paragraph.id, paragraph.style, paragraph.text, (), item)
            elif roll < 0.4:
                current.paragraphs[position] = Paragraph(
                    paragraph.id, paragraph.style, paragraph.text + "!", (), paragraph.item
                )
        for number in range(rng.randint(0, 3)):
            item = rng.choice([None, ListItem("l9", rng.randint(0, 2)), ListItem("l1", rng.randint(0, 2))])
            current.paragraphs.insert(
                rng.randint(0, len(current.paragraphs)), Paragraph(f"n{number}", "body", f"new {number}", item=item)
            )
        if rng.random() < 0.4 and current.paragraphs:
            current.paragraphs.pop(rng.randrange(len(current.paragraphs)))
        edited = apply_edits_to_odt(original, baseline, current)
        assert problems(edited) == []
        assert shape(odt_to_text(edited)) == shape(current)
        assert table in content(edited)


# ----------------------------------------------------------------------------- numbered headings (E9.22)
def test_numbered_headings_are_written_as_the_outline_style_and_read_back_as_such():
    from claudia_composes_io import apply_edits_to_odt

    model = TextModel(
        [
            Paragraph("b1", "heading-1", "Why"),
            Paragraph("b2", "heading-2", "Asked"),
            Paragraph("b3", "heading-1", "How"),
        ]
    )
    model.lists.add(ListDef("outline", "chapters"))
    model.styles.set_numbering("heading-1", "outline")
    model.styles.set_numbering("heading-2", "outline")
    data = text_to_odt(model)
    outline = etree.fromstring(read_parts(data)["styles.xml"]).find(".//text:outline-style", NS)
    assert outline is not None and outline[1].get(f"{{{NS['text']}}}display-levels") == "2"
    back = odt_to_text(data)
    assert {k: v.marker for k, v in back.labels().items()} == {"b1": "1", "b2": "1.1", "b3": "2"}
    current = odt_to_text(data)
    for style in current.styles:  # what Number Headings does when it is switched off
        if current.styles.numbering(style.id) is not None:
            current.styles.set_numbering(style.id, None)
    patched = odt_to_text(apply_edits_to_odt(data, odt_to_text(data), current))
    assert patched.labels() == {}


def test_a_text_whose_headings_are_not_numbered_writes_no_outline_numbers():
    data = text_to_odt(TextModel([Paragraph("b1", "heading-1", "Why")]))
    assert b"outline-style" not in read_parts(data)["styles.xml"]
    assert odt_to_text(data).labels() == {}
