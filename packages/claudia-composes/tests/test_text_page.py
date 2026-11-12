"""The page a text is printed on (D904): stored with the text, changed in one step that can be undone."""

import pytest

from claudia_composes import PAPERS, PageSetup, PageSetupError, SetPageSetup, TextModel
from claudia_core import CommandLog, Document


def test_a_new_text_is_laid_out_on_a4_portrait_with_25_mm_margins():
    page = TextModel().page
    assert (page.paper, page.width, page.height, page.orientation) == ("a4", 595276, 841890, "portrait")
    assert (page.margin_top, page.margin_left) == (70866, 70866)
    assert page.page_numbers is False


def test_presets_are_the_layout_librarys_sizes_short_side_first():
    assert PAPERS["letter"] == (612000, 792000)
    assert PAPERS["a3"] == (841890, 1190551)
    assert all(w <= h for w, h in PAPERS.values())


def test_setting_the_page_is_one_step_with_an_exact_inverse_and_an_event():
    doc = Document(TextModel())
    events = []
    doc.bus.subscribe(lambda e: events.append(e.to_data()) if hasattr(e, "to_data") else None)
    letter = PageSetup.preset("letter", orientation="landscape", page_numbers=True)
    doc.execute(SetPageSetup(letter), author="anna")
    assert doc.model.page == letter
    assert {"type": "page", "setup": letter.to_data()} in events
    doc.undo("anna")
    assert doc.model.page == PageSetup()


def test_the_page_survives_the_log_and_a_snapshot():
    doc = Document(TextModel())
    custom = PageSetup(
        paper="custom",
        width=283465,
        height=425197,
        margin_top=28346,
        margin_right=28346,
        margin_bottom=28346,
        margin_left=28346,
    )
    doc.execute(SetPageSetup(custom), author="anna")
    log = CommandLog.from_data(doc.log.to_data(), TextModel.registry)
    assert Document.open(TextModel, log).model.page == custom
    assert TextModel.restore(doc.model.serialize()).page == custom


def test_an_older_state_without_a_page_gets_the_default():
    state = TextModel().serialize()
    del state["page"]
    assert TextModel.restore(state).page == PageSetup()


@pytest.mark.parametrize(
    ("data", "why"),
    [
        ({"paper": "a4", "width": 1, "height": 841890}, "size"),
        ({"paper": "folio", "width": 595276, "height": 841890}, "unknown paper"),
        ({"paper": "custom", "width": 900000, "height": 800000}, "short side"),
        ({"paper": "custom", "width": 1000, "height": 841890}, "between 25 mm"),
        ({"paper": "a4", "width": 595276, "height": 841890, "orientation": "sideways"}, "orientation"),
        ({"paper": "a4", "width": 595276, "height": 841890, "margins": [0, 300000, 0, 300000]}, "10 mm"),
        ({"paper": "a4", "width": 595276, "height": 841890, "margins": [0, 0, 0]}, "four numbers"),
        ({"paper": "a4", "width": 595276, "height": 841890, "margins": [0, 0, 0, 1.5]}, "whole"),
        ({"paper": "a4", "width": 595276, "height": 841890, "page_numbers": "yes"}, "true or false"),
        ({"paper": "a4", "height": 841890}, "needs width"),
        ("a4", "an object"),
    ],
)
def test_a_page_that_cannot_be_used_is_refused_with_a_reason(data, why):
    with pytest.raises(PageSetupError, match=why):
        PageSetup.from_data(data)


def test_a_landscape_page_checks_its_margins_across_the_long_side():
    # 20.5 cm of margins left and right fit across A4 landscape (29.7 cm) but not across portrait (21 cm)
    margins = [70866, 290000, 70866, 290000]
    PageSetup.from_data(
        {"paper": "a4", "width": 595276, "height": 841890, "orientation": "landscape", "margins": margins}
    )
    with pytest.raises(PageSetupError):
        PageSetup.from_data({"paper": "a4", "width": 595276, "height": 841890, "margins": margins})


def test_the_history_says_what_the_page_became():
    assert (
        SetPageSetup(PageSetup.preset("a5", page_numbers=True)).summary == "set the page to A5, portrait, page numbers"
    )
    assert SetPageSetup(PageSetup.preset("letter")).summary == "set the page to Letter, portrait"
    custom = PageSetup(paper="custom", width=283465, height=425197)
    assert SetPageSetup(custom).summary == "set the page to 100 × 150 mm, portrait"
