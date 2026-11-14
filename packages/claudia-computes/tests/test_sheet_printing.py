"""How a workbook prints (E6.19, D1001–D1009): its page, the setup of each sheet, and its language."""

import pytest

from claudia_computes import (
    DEFAULT_SHEET_PRINT,
    AddSheet,
    PrintSetupError,
    SetPrintPage,
    SetSheetPrint,
    SheetPrintSetup,
    WorkbookModel,
)
from claudia_core import CommandLog, Document, PageSetup, PageSetupError, SetLanguage

S1 = "s1"


# ------------------------------------------------------------------------------ the setup of one sheet
def test_a_sheet_nobody_set_up_prints_portrait_fitted_to_the_width_with_its_name_in_the_footer():
    setup = DEFAULT_SHEET_PRINT
    assert (setup.orientation, setup.scale, setup.order) == ("portrait", "fit-width", "down-then-across")
    assert (setup.repeat_rows, setup.repeat_cols) == (None, None)
    assert (setup.gridlines, setup.headings, setup.purposes) == (False, False, False)  # purpose tints: optional (D1005)
    assert (setup.footer_name, setup.objects, setup.skip_empty) == (True, True, True)


def test_a_setup_is_read_back_as_written_and_a_part_left_out_keeps_its_default():
    setup = SheetPrintSetup(
        orientation="landscape", scale="percent", percent=80, order="across-then-down", repeat_rows=(0, 1),
        repeat_cols=(0, 0), gridlines=True, headings=True, purposes=True, footer_name=False, objects=False,
        skip_empty=False,
    )  # fmt: skip
    data = setup.to_data()
    assert data["scale"] == {"kind": "percent", "percent": 80}
    assert data["repeat_rows"] == [0, 1] and data["repeat_cols"] == [0, 0]
    assert SheetPrintSetup.from_data(data) == setup
    assert SheetPrintSetup.from_data({"orientation": "landscape"}) == SheetPrintSetup(orientation="landscape")
    assert SheetPrintSetup.from_data({}) == DEFAULT_SHEET_PRINT
    assert DEFAULT_SHEET_PRINT.to_data()["scale"] == {"kind": "fit-width"}  # a percentage only where it counts


def test_a_setup_that_cannot_be_used_says_which_part():
    for bad, words in [
        ({"orientation": "sideways"}, "orientation"),
        ({"scale": {"kind": "huge"}}, "scale"),
        ({"scale": {"kind": "percent", "percent": 9}}, "10 %"),
        ({"scale": {"kind": "percent", "percent": 401}}, "400 %"),
        ({"scale": {"kind": "percent", "percent": 80.5}}, "10 %"),
        ({"scale": "fit-width"}, "scale"),
        ({"order": "diagonal"}, "order"),
        ({"repeat_rows": [3, 1]}, "repeat_rows"),
        ({"repeat_rows": [-1, 1]}, "repeat_rows"),
        ({"repeat_cols": "A"}, "repeat_cols"),
        ({"gridlines": "yes"}, "gridlines"),
        ({"colour": "red"}, "colour"),
    ]:
        with pytest.raises(PrintSetupError, match=words):
            SheetPrintSetup.from_data(bad)
    with pytest.raises(PrintSetupError, match="object"):
        SheetPrintSetup.from_data(["landscape"])


def test_a_setup_describes_itself_in_a_few_words_for_the_history():
    assert DEFAULT_SHEET_PRINT.describe() == "portrait, fit to width"
    full = SheetPrintSetup("landscape", "percent", 80, repeat_rows=(0, 0), gridlines=True, headings=True)
    assert full.describe() == "landscape, 80 %, repeating rows, gridlines, headings"
    assert SheetPrintSetup(scale="fit-page").describe() == "portrait, fit to one page"


# ------------------------------------------------------------------------------ the workbook
@pytest.fixture
def book():
    doc = Document(WorkbookModel())
    doc.execute(AddSheet(S1, "Sheet1"), author="ann")
    return doc


def test_a_new_workbook_prints_a_4_portrait_with_the_usual_margins_and_no_setups_of_its_own(book):
    model = book.model
    assert (model.print_page.paper, model.print_page.orientation) == ("a4", "portrait")
    assert model.print_page.margin_top == 70866 and model.print_page.page_numbers is False
    assert model.sheet_print == {} and model.language is None
    assert model.sheet_print_of(S1) == DEFAULT_SHEET_PRINT


def test_setting_the_page_is_one_step_with_an_exact_inverse_and_an_event(book):
    events = []
    book.bus.subscribe(lambda e: events.append(e.to_data()) if hasattr(e, "to_data") else None)
    page = PageSetup.preset("letter", page_numbers=True)
    book.execute(SetPrintPage(page), author="ann")
    assert book.model.print_page == page
    assert {"type": "print_setup", "page": page.to_data()} in events
    assert list(book.log)[-1].command.summary == "set the page to Letter, portrait, page numbers"
    book.undo("ann")
    assert book.model.print_page == PageSetup()


def test_setting_a_sheet_up_is_one_step_with_an_exact_inverse_and_an_event(book):
    events = []
    book.bus.subscribe(lambda e: events.append(e.to_data()) if hasattr(e, "to_data") else None)
    landscape = SheetPrintSetup(orientation="landscape", repeat_rows=(0, 0))
    book.execute(SetSheetPrint(S1, landscape), author="ann")
    assert book.model.sheet_print_of(S1) == landscape
    assert {"type": "print_setup", "sheet": S1, "setup": landscape.to_data()} in events
    assert list(book.log)[-1].command.summary == "set printing of a sheet to landscape, fit to width, repeating rows"
    book.execute(SetSheetPrint(S1, SheetPrintSetup(gridlines=True)), author="ann")
    book.undo("ann")
    assert book.model.sheet_print_of(S1) == landscape
    book.undo("ann")
    assert book.model.sheet_print == {}  # back to the default stores nothing


def test_only_a_sheet_or_a_chart_tab_can_be_set_up(book):
    with pytest.raises(KeyError):
        book.execute(SetSheetPrint("nope", SheetPrintSetup()), author="ann")
    assert book.model.sheet_print == {}


def test_a_workbook_has_the_kernels_language(book):
    book.execute(SetLanguage("de-de"), author="ann")
    assert book.model.language == "de-DE"
    book.undo("ann")
    assert book.model.language is None


def test_setups_survive_the_log_and_a_snapshot_and_older_snapshots_get_the_defaults(book):
    book.execute(SetPrintPage(PageSetup.preset("a3", orientation="landscape")), author="ann")
    book.execute(SetSheetPrint(S1, SheetPrintSetup(scale="fit-page")), author="ann")
    book.execute(SetLanguage("en-GB"), author="ann")
    log = CommandLog.from_data(book.log.to_data(), WorkbookModel.registry)
    again = Document.open(WorkbookModel, log).model
    assert (again.print_page.paper, again.sheet_print_of(S1).scale, again.language) == ("a3", "fit-page", "en-GB")
    state = book.model.serialize()
    assert state["sheet_print"] == {S1: SheetPrintSetup(scale="fit-page").to_data()}
    restored = WorkbookModel.restore(state)
    assert (restored.print_page, restored.sheet_print_of(S1).scale) == (book.model.print_page, "fit-page")
    for key in ("print_page", "sheet_print", "language"):
        del state[key]
    old = WorkbookModel.restore(state)
    assert (old.print_page, old.sheet_print, old.language) == (PageSetup(), {}, None)


def test_a_page_that_cannot_be_used_is_refused_by_the_page_setup(book):
    with pytest.raises(PageSetupError):
        SetPrintPage.from_data({"page": {"paper": "a4", "width": 1, "height": 2}}, WorkbookModel.registry)
