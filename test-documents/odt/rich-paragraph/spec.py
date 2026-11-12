"""One paragraph with a link, a formatted word, a bookmark and a footnote in it. Claudia's model sees only its
text; changing a word of that text must not cost the paragraph any of the rest (D401): the edit is made inside the
paragraph, in place, and the paragraph next to it is not touched at all."""

from __future__ import annotations

from claudia_composes import TextModel
from claudia_core import Run
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

TEXT = "Read the manual and note the examples carefully."


def import_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        ("heading-1", "Reading list"),
        ("body", TEXT),
        ("body", "Nothing here changes."),
    ]


def modify(model: TextModel) -> TextModel:
    block_id = model.blocks[1].id
    start = TEXT.index("carefully")
    model.remove(block_id, start, start + len("carefully"))
    model.insert(block_id, start, "slowly", [Run(len("slowly"), None)])
    return model


def after_checks(model: TextModel) -> None:
    assert model.blocks[1].text == "Read the manual and note the examples slowly."
    assert model.blocks[2].text == "Nothing here changes."


def preserve_inside_the_paragraph(original: bytes, edited: bytes) -> None:
    after = read_parts(edited)["content.xml"].decode()
    for kept in (
        '<text:a xlink:href="https://example.org/manual" xlink:type="simple">manual</text:a>',
        '<text:span text:style-name="Strong">note</text:span>',
        '<text:bookmark text:name="examples"/>',
        "<text:note-body><text:p>See chapter two.</text:p></text:note-body>",
    ):
        assert kept in after, kept
    assert "slowly" in after and "carefully" not in after
    before = read_parts(original)["content.xml"].decode()
    tail = '<text:p text:style-name="Text_20_body">Nothing here changes.</text:p>'
    assert after[: after.index("<text:p")] == before[: before.index("<text:p")]
    assert after.endswith(before[before.index(tail) :])


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "meta.xml", "META-INF/manifest.xml"],
    preserve_elements=preserve_inside_the_paragraph,
)
