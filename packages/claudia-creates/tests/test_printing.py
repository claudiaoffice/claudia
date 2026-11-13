"""How a presentation prints (D917): its print setup and its language, both stored in the deck."""

import pytest

from claudia_core import CommandLog, Document, PageSetup, PageSetupError, SetLanguage
from claudia_creates import LAYOUTS, PrintSetup, PrintSetupError, SetPrintSetup, SlideModel


def test_a_new_presentation_prints_one_slide_to_a_slide_sized_page():
    setup = SlideModel.empty().print_setup
    assert setup.layout == "slides"
    assert (setup.page.paper, setup.page.orientation) == ("slide", "landscape")
    assert (setup.page.width, setup.page.height) == (540000, 960000)  # 7.5 × 13.333 in, PowerPoint's widescreen
    assert [setup.page.margin_top, setup.page.margin_right, setup.page.margin_bottom, setup.page.margin_left] == [0] * 4
    assert setup.describe() == "slides on Slide size, landscape"
    assert LAYOUTS == ("slides", "handouts-2", "handouts-3", "handouts-4", "handouts-6", "handouts-9")


def test_a_setup_is_read_back_as_written_and_checked():
    setup = PrintSetup("handouts-3", PageSetup.preset("letter", page_numbers=True))
    assert PrintSetup.from_data(setup.to_data()) == setup
    assert setup.describe() == "3 slides a page on Letter, portrait, page numbers"
    with pytest.raises(PrintSetupError, match="layout"):
        PrintSetup("handouts-5")
    with pytest.raises(PrintSetupError, match="object"):
        PrintSetup.from_data(["slides"])
    with pytest.raises(PageSetupError):
        PrintSetup.from_data({"layout": "slides", "page": {"paper": "a4", "width": 1, "height": 2}})


def test_setting_up_printing_is_one_step_with_an_exact_inverse_and_an_event():
    doc = Document(SlideModel.empty())
    events = []
    doc.bus.subscribe(lambda e: events.append(e.to_data()) if hasattr(e, "to_data") else None)
    handouts = PrintSetup("handouts-6", PageSetup.preset("a4"))
    doc.execute(SetPrintSetup(handouts), author="ann")
    assert doc.model.print_setup == handouts
    assert {"type": "print_setup", "setup": handouts.to_data()} in events
    doc.undo("ann")
    assert doc.model.print_setup == PrintSetup()


def test_a_presentation_has_the_kernels_language():
    doc = Document(SlideModel.empty())
    doc.execute(SetLanguage("de-de"), author="ann")
    assert doc.model.language == "de-DE"
    assert list(doc.log)[-1].command.kind == "core.SetLanguage"


def test_setup_and_language_survive_the_log_and_a_snapshot_and_older_snapshots_get_the_defaults():
    doc = Document(SlideModel.empty())
    doc.execute(SetPrintSetup(PrintSetup("handouts-2", PageSetup.preset("a5"))), author="ann")
    doc.execute(SetLanguage("en-GB"), author="ann")
    log = CommandLog.from_data(doc.log.to_data(), SlideModel.registry)
    again = Document.open(SlideModel, log).model
    assert (again.print_setup.layout, again.language) == ("handouts-2", "en-GB")
    state = doc.model.serialize()
    assert SlideModel.restore(state).print_setup.page.paper == "a5"
    del state["print_setup"], state["language"]
    old = SlideModel.restore(state)
    assert (old.print_setup, old.language) == (PrintSetup(), None)
