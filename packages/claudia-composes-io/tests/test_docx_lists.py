"""Lists in a docx: written from the items of the model, read back as items, and patched into a file that has them
(D453). The one property that matters: whatever is done, the file says the same lists the model does."""

from __future__ import annotations

import random
import re
import zipfile
from io import BytesIO

from claudia_composes_io import (
    apply_edits_to_docx,
    docx_import_losses,
    docx_to_text,
    text_to_docx,
)
from docx import Document
from docx.oxml.ns import qn
from test_odt_lists import shape, text_of

from claudia_composes import Block, TextModel
from claudia_core import ListDef, ListItem
from claudia_odf_io import Loss
from claudia_opc_io import read_parts, write_parts


def again(model: TextModel) -> TextModel:
    return docx_to_text(text_to_docx(model))


def parts(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(data)) as package:
        return {name: package.read(name) for name in package.namelist()}


def numbering_of(data: bytes) -> list[tuple[int | None, int | None]]:
    """``(numId, ilvl)`` of each paragraph, as the paragraphs say it themselves."""
    found = []
    for paragraph in Document(BytesIO(data)).paragraphs:
        properties = paragraph._p.pPr
        numbering = properties.find(qn("w:numPr")) if properties is not None else None
        if numbering is None:
            found.append((None, None))
            continue
        number, level = numbering.find(qn("w:numId")), numbering.find(qn("w:ilvl"))
        found.append((int(number.get(qn("w:val"))), int(level.get(qn("w:val")))))
    return found


def saved(document) -> bytes:
    out = BytesIO()
    document.save(out)
    return out.getvalue()


def foreign_file() -> bytes:
    """A file the model did not write: a paragraph of a style that carries a list, one that numbers itself, one that
    switches its style's numbering off."""
    document = Document()
    document.add_paragraph("bullet", style="List Bullet")
    document.add_paragraph("plain")
    document.add_paragraph("bullet again", style="List Bullet")
    document.add_paragraph("number", style="List Number")
    return saved(document)


# -- export and import -------------------------------------------------------------------------------------------
def test_items_are_written_with_the_number_of_their_list_and_their_level():
    data = text_to_docx(text_of(("a", "l1", 0), ("b", "l1", 1), ("plain",), ("c", "l1", 0)))
    first, second, plain, third = numbering_of(data)
    assert first[0] == second[0] == third[0] and plain == (None, None)
    assert (first[1], second[1], third[1]) == (0, 1, 0)


def test_two_lists_are_two_numbers():
    model = text_of(("a", "l1", 0), ("b", "l2", 0), lists=(ListDef("l1", "bullets"), ListDef("l2", "numbers")))
    first, second = numbering_of(text_to_docx(model))
    assert first[0] != second[0]


def test_a_list_comes_back_as_the_same_list():
    model = text_of(
        ("one", "l1", 0), ("plain", None, 0), ("two", "l1", 0), lists=(ListDef("l1", "numbers", 3, "Steps"),)
    )
    assert shape(again(model)) == shape(model)


def test_every_level_comes_back():
    rows = [(f"level {level}", "l1", level) for level in range(9)]
    assert shape(again(text_of(*rows, lists=(ListDef("l1", "numbers"),)))) == shape(
        text_of(*rows, lists=(ListDef("l1", "numbers"),))
    )


def test_items_apart_from_each_other_are_one_list():
    model = text_of(("a", "l1", 0), ("between",), ("b", "l1", 0))
    assert len(again(model).lists.ids()) == 1


def test_the_list_the_model_draws_is_not_reported_as_drawn_otherwise():
    model = text_of(("a", "l1", 0), lists=(ListDef("l1", "numbers", 5),))
    assert docx_import_losses(text_to_docx(model)) == ()


def test_a_fresh_file_has_a_look_for_every_level():
    document = Document(BytesIO(text_to_docx(text_of(("a", "l1", 0)))))
    levels = document.part.numbering_part.element.findall(".//" + qn("w:abstractNum") + "/" + qn("w:lvl"))
    assert len([lvl for lvl in levels if lvl.getparent().find(qn("w:name")) is None]) >= 9


def test_a_style_that_carries_a_list_makes_its_paragraphs_items():
    model = docx_to_text(foreign_file())
    assert [(b.text, b.item is not None) for b in model.blocks] == [
        ("bullet", True),
        ("plain", False),
        ("bullet again", True),
        ("number", True),
    ]
    assert model.blocks[0].item.list == model.blocks[2].item.list != model.blocks[3].item.list
    assert [model.lists.get(b.item.list).scheme for b in (model.blocks[0], model.blocks[3])] == ["bullets", "numbers"]


def test_a_list_the_model_draws_otherwise_is_reported_with_how_many():
    # Word's bullets are a symbol in another font; its numbered list is drawn as the model draws numbers
    assert docx_import_losses(foreign_file()) == (
        Loss("style", "List Bullet", 2),
        Loss("style", "List Number", 1),
        Loss("list-look", "", 1),
    )


def test_a_paragraph_that_switches_numbering_off_is_no_item():
    document = Document(BytesIO(foreign_file()))
    properties = document.paragraphs[0]._p.get_or_add_pPr()
    properties.get_or_add_numPr().get_or_add_numId().val = 0
    assert docx_to_text(saved(document)).blocks[0].item is None


def test_a_number_the_file_does_not_define_is_no_item():
    document = Document(BytesIO(foreign_file()))
    document.paragraphs[1]._p.get_or_add_pPr().get_or_add_numPr().get_or_add_numId().val = 4242
    assert docx_to_text(saved(document)).blocks[1].item is None


def without_numbering(data: bytes) -> bytes:
    """``data`` as a package that has no numbering part, which is what a file made without lists is."""
    package = read_parts(data)
    package.pop("word/numbering.xml")
    package["[Content_Types].xml"] = re.sub(rb"<Override[^>]*numbering[^>]*/>", b"", package["[Content_Types].xml"])
    package["word/_rels/document.xml.rels"] = re.sub(
        rb"<Relationship [^>]*numbering[^>]*/>", b"", package["word/_rels/document.xml.rels"]
    )
    return write_parts(package)


def test_a_file_without_numbering_has_no_lists():
    data = without_numbering(text_to_docx(text_of(("plain",))))
    assert docx_to_text(data).lists.ids() == [] and docx_import_losses(data) == ()


# -- patching ----------------------------------------------------------------------------------------------------
def test_a_changed_text_in_an_item_keeps_the_item():
    original = text_to_docx(text_of(("one", "l1", 0), ("two", "l1", 0)))
    baseline = docx_to_text(original)
    current = docx_to_text(original)
    current.blocks[1] = Block("b2", "body", "two!", current.blocks[1].runs, current.blocks[1].item)
    assert shape(docx_to_text(apply_edits_to_docx(original, baseline, current)))[1][1] == "two!"
    assert numbering_of(apply_edits_to_docx(original, baseline, current)) == numbering_of(original)


def test_a_paragraph_made_an_item_joins_the_list_of_the_file():
    original = text_to_docx(text_of(("one", "l1", 0), ("plain",)))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.blocks[1] = Block("b2", "body", "plain", (), ListItem(current.blocks[0].item.list, 1))
    first, second = numbering_of(apply_edits_to_docx(original, baseline, current))
    assert first[0] == second[0] and second[1] == 1


def test_an_item_made_a_paragraph_is_no_item():
    original = text_to_docx(text_of(("one", "l1", 0), ("two", "l1", 0)))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.blocks[0] = Block("b1", "body", "one", (), None)
    assert numbering_of(apply_edits_to_docx(original, baseline, current))[0] == (None, None)


def test_an_item_of_a_style_that_carries_a_list_made_a_paragraph_stays_one_no_longer():
    original = foreign_file()
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.blocks[0] = Block("b1", "body", "bullet", (), None)
    assert docx_to_text(apply_edits_to_docx(original, baseline, current)).blocks[0].item is None


def test_a_new_list_gets_its_own_number():
    original = text_to_docx(text_of(("one", "l1", 0), ("plain",)))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.lists.add(ListDef("l9", "numbers", 4))
    current.blocks[1] = Block("b2", "body", "plain", (), ListItem("l9", 0))
    edited = apply_edits_to_docx(original, baseline, current)
    assert numbering_of(edited)[0][0] != numbering_of(edited)[1][0]
    assert shape(docx_to_text(edited))[-1] == ("lists", [("L1", ("bullets", 1, None)), ("L2", ("numbers", 4, None))])


def test_a_list_drawn_otherwise_follows_its_definition_without_touching_its_paragraphs():
    original = text_to_docx(text_of(("one", "l1", 0), ("two", "l1", 0)))
    baseline, current = docx_to_text(original), docx_to_text(original)
    list_id = baseline.lists.ids()[0]
    current.lists.replace(ListDef(list_id, "numbers", 7, "Steps"))
    edited = apply_edits_to_docx(original, baseline, current)
    assert shape(docx_to_text(edited))[-1] == ("lists", [("L1", ("numbers", 7, "Steps"))])
    assert parts(edited)["word/document.xml"] == parts(original)["word/document.xml"]


def test_a_text_that_changes_nothing_about_lists_leaves_the_numbering_as_it_was():
    original = text_to_docx(text_of(("one", "l1", 0), ("plain",)))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.blocks[1] = Block("b2", "body", "plain!", current.blocks[1].runs, None)
    assert (
        parts(apply_edits_to_docx(original, baseline, current))["word/numbering.xml"]
        == parts(original)["word/numbering.xml"]
    )


def test_a_file_without_a_list_gets_no_numbering_part_it_does_not_need():
    document = Document()
    document.add_paragraph("plain")
    original = saved(document)
    package = dict(parts(original))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.blocks[0] = Block("b1", "body", "plain!", current.blocks[0].runs, None)
    assert set(parts(apply_edits_to_docx(original, baseline, current))) == set(package)


def test_a_style_a_file_has_is_kept_when_only_the_text_changes():
    original = foreign_file()
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.blocks[0] = Block("b1", "body", "bullet!", current.blocks[0].runs, current.blocks[0].item)
    document = Document(BytesIO(apply_edits_to_docx(original, baseline, current)))
    assert document.paragraphs[0].style.name == "List Bullet"


def test_a_list_made_in_a_file_that_had_none_is_in_the_package():
    original = without_numbering(text_to_docx(text_of(("one",), ("two",), lists=())))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.lists.add(ListDef("l1", "numbers", 2))
    current.blocks[1] = Block("b2", "body", "two", (), ListItem("l1", 0))
    edited = apply_edits_to_docx(original, baseline, current)
    assert shape(docx_to_text(edited))[-1] == ("lists", [("L1", ("numbers", 2, None))])
    assert b"numbering" in parts(edited)["[Content_Types].xml"] and "word/numbering.xml" in parts(edited)
    assert numbering_of(edited)[0] == (None, None)


def test_a_paragraph_added_to_a_list_is_an_item_of_it():
    original = text_to_docx(text_of(("one", "l1", 0)))
    baseline, current = docx_to_text(original), docx_to_text(original)
    current.blocks.append(Block("n1", "body", "new", (), ListItem(baseline.blocks[0].item.list, 0)))
    again = docx_to_text(apply_edits_to_docx(original, baseline, current))
    assert [b.text for b in again.blocks] == ["one", "new"]
    assert again.blocks[0].item.list == again.blocks[1].item.list


def test_whatever_is_done_to_the_lists_of_a_file_it_says_the_same_lists_as_the_model():
    rng = random.Random(454)
    original = text_to_docx(
        text_of(
            ("a", "l1", 0),
            ("b", "l1", 1),
            ("c",),
            ("d", "l2", 0),
            ("e", "l2", 0),
            ("f",),
            ("g", "l1", 0),
            lists=(ListDef("l1", "bullets"), ListDef("l2", "numbers", 2, "Two")),
        )
    )
    for _ in range(200):
        baseline, current = docx_to_text(original), docx_to_text(original)
        current.lists.add(ListDef("l9", "numbers", 3))
        ids = baseline.lists.ids()
        for position, block in enumerate(current.blocks):
            roll = rng.random()
            if roll < 0.35:
                item = rng.choice(
                    [None, ListItem(rng.choice(ids), rng.randint(0, 3)), ListItem("l9", rng.randint(0, 2))]
                )
                current.blocks[position] = Block(block.id, block.style, block.text, block.runs, item)
            elif roll < 0.5:
                current.blocks[position] = Block(block.id, block.style, block.text + "!", (), block.item)
        if rng.random() < 0.3:
            scheme = rng.choice(["bullets", "numbers"])  # where nothing counts, there is no number to start at
            current.lists.replace(ListDef(ids[0], scheme, rng.randint(1, 5) if scheme == "numbers" else 1))
        edited = apply_edits_to_docx(original, baseline, current)
        assert shape(docx_to_text(edited)) == shape(current)


# ----------------------------------------------------------------------------- schemes and numbered headings (E9.22)
def headed_text() -> TextModel:
    """A text whose Heading 1 and 2 are numbered in the list "outline" (scheme chapters), and a numbered list whose
    scheme the document changed: "Step 1)"."""
    from dataclasses import replace

    blocks = [
        Block("b1", "heading-1", "Why"),
        Block("b2", "heading-2", "Asked"),
        Block("b3", "body", "one", item=ListItem("l1")),
        Block("b4", "heading-1", "How"),
    ]
    model = TextModel(blocks)
    model.lists.add(ListDef("outline", "chapters", name="Outline"))
    model.lists.add(ListDef("l1", "numbers"))
    numbers = model.schemes.get("numbers")
    first = replace(numbers.levels[0], before="Step ", after=")")
    model.schemes.replace(replace(numbers, levels=(first, *numbers.levels[1:])))
    for style in ("heading-1", "heading-2"):
        model.styles.set_numbering(style, "outline")
    return model


def test_numbered_headings_are_written_as_numbered_word_styles_and_read_back_as_such():
    data = text_to_docx(headed_text())
    styles = {s.name: s for s in Document(BytesIO(data)).styles}
    said = styles["Heading 2"].element.pPr.find(qn("w:numPr"))
    assert said is not None and said.find(qn("w:ilvl")).get(qn("w:val")) == "1"
    assert numbering_of(data)[0] == (None, None), "a heading is numbered by its style, not by itself"
    model = docx_to_text(data)
    assert {b.id: b.item for b in model.blocks}["b1"] is None
    assert model.styles.numbering("heading-1") == model.styles.numbering("heading-2") is not None
    assert {k: v.marker for k, v in model.labels().items()} == {"b1": "1", "b2": "1.1", "b3": "Step 1)", "b4": "2"}


def test_a_changed_scheme_is_written_into_the_list_and_comes_back():
    model = again(headed_text())
    assert model.schemes.get(model.lists.get("l2").scheme).marker((3,)) == "Step 3)"
    assert docx_import_losses(text_to_docx(headed_text())) == ()


def test_numbering_the_headings_of_an_imported_file_patches_its_styles():
    plain = TextModel([Block("b1", "heading-1", "Why"), Block("b2", "body", "text")])
    original = text_to_docx(plain)
    baseline = docx_to_text(original)
    current = docx_to_text(original)
    current.lists.add(ListDef("outline", "chapters"))
    current.styles.set_numbering("heading-1", "outline")
    patched = docx_to_text(apply_edits_to_docx(original, baseline, current))
    assert {k: v.marker for k, v in patched.labels().items()} == {"b1": "1"}
