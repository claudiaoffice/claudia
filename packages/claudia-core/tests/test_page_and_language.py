"""The page a document prints on and its language belong to the kernel, shared by composes and creates (D917)."""

import pytest

from claudia_core import PAPERS, Document, PageSetup, SetLanguage
from claudia_core.testing import ListModel


def test_the_slide_paper_is_powerpoints_widescreen_size():
    assert PAPERS["slide"] == (540000, 960000)
    page = PageSetup.preset(
        "slide", orientation="landscape", margin_top=0, margin_right=0, margin_bottom=0, margin_left=0
    )
    assert page.describe() == "Slide size, landscape"


def test_a_document_without_a_language_refuses_one():
    doc = Document(ListModel())
    with pytest.raises(TypeError, match="no language"):
        doc.execute(SetLanguage("de"), author="ann")
    assert SetLanguage(None).summary == "removed the language"
