"""A table -- content claudia has no model for -- sits in the same ``content.xml`` an edit rewrites, and an odt
keeps *everything* there, so no whole-part guarantee can carry it. What carries it is that an edit replaces only the
bytes of the paragraph that changed (D401): the table's own markup, byte for byte, is the check."""

from __future__ import annotations

from claudia_composes import DEFAULT_STYLE, TextModel
from claudia_core import Run
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case


def import_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        (DEFAULT_STYLE, "Status report."),
        (DEFAULT_STYLE, "End of report."),
    ]


def modify(model: TextModel) -> TextModel:
    block_id, new_text = model.blocks[0].id, "Status report (updated)."
    model.remove(block_id, 0, len(model.block(block_id).text))
    model.insert(block_id, 0, new_text, [Run(len(new_text), None)])
    return model


def after_checks(model: TextModel) -> None:
    assert [(b.style, b.text) for b in model.blocks] == [
        (DEFAULT_STYLE, "Status report (updated)."),
        (DEFAULT_STYLE, "End of report."),
    ]


def table_markup(data: bytes) -> str:
    content = read_parts(data)["content.xml"].decode()
    return content[content.index("<table:table ") : content.index("</table:table>") + len("</table:table>")]


def preserve_table(original: bytes, edited: bytes) -> None:
    assert table_markup(edited) == table_markup(original)
    assert "North" in table_markup(edited) and "120" in table_markup(edited)
    assert (
        read_parts(edited)["content.xml"]
        .decode()
        .endswith(read_parts(original)["content.xml"].decode().split("</table:table>", 1)[1])
    )


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "meta.xml", "settings.xml"],
    preserve_elements=preserve_table,
)
