# Implementation notes: E6.31 Slides in computes

Branch `e6-31-slides-in-computes`, decisions D1470–D1473 (range D1470–D1489). The design is
`notes/e6-31-slides-in-computes.md`, the scenarios `specs/computes/slides.feature`. This file keeps what the code does
not say, step by step.

## Step 1 · The slide shared by the core (D1470), 2026-11-22

- `claudia_core/slides.py` has the frame, `SlideAnchor`, the rule that keeps an object on a slide (`check_on_slide`,
  `turned_on_slide`, `room_on_slide`) and `Slide`/`Slides`. Creates' `check_anchor`, `turned_anchor` and
  `room_for_new_object` call them; the anchor's refusal of another kind now says "not a slide anchor" instead of
  "creates knows only slide anchors", as two apps read it.
- **Creates' names are computes' names** (the owner, after the review): `SlideModel.slides` are the records (`Slides`,
  replacing `slide_names` and `slide_descriptions`) and `SlideModel.order` is the presentation, which `slides` was. The
  ODP reader's own `self.slides` (the pages it scanned) and python-pptx's `prs.slides` are other things and kept their
  names.
- **A refused slide changes nothing, and refuses as before:** `Slides.check_new(id)` is what creates asks first, so a
  bad or taken id is still the first thing `AddSlide` refuses; computes' `add_slide` will ask the same before it
  touches its tabs. `Slides.from_data` gives the order back with the records, so the format is read in one place.
- **That a slide with objects cannot go is the core's `close_holder`**, as for every holder; `Slides` does not know
  objects. D1470 says so now.
- **The state** (schema 18) stores the slides as records in the presentation's order (`[{id, name?, description?}]`);
  the keys `names` and `descriptions` are gone. An older state is not read (pre-release, D1430): the test that read a
  state from before names went, and the test of a state from before notes became the test that a presentation
  (slides in another order, names, descriptions, notes, times) survives being stored and loaded.
- `claudia_creates` still re-exports `SLIDE_WIDTH`, `SLIDE_HEIGHT` and `SlideAnchor`, as it re-exports `ObjectBody` and
  `VisualObject`: creates-io imports them from there and did not change. The server's `slide_lens.py` imported them
  from `claudia_creates.model` and now from `claudia_core`.
- **The kernel's purity test** (`packages/claudia-core/tests/test_purity.py`) forbade the word "slide" in the kernel;
  it leaves the list with D1470, as "paragraph" did with D181.
- **Found:** five `autodata` lines in `docs/api/claudia_creates.rst` had never been directives (no blank line after the
  paragraph above them), and named constants creates does not have (two of them exist nowhere). They are gone. Three
  of them (`MIN_OBJECT_SIZE`, `ASPECT_TOLERANCE`, `OBJECT_KINDS`) are in `claudia_core.__all__` but not on the core's
  API page; that is left as it is (not this story's).

**Review (code-review, two axes) and what changed after it:** the order and the records got the agreed names (above);
`check_new` restores the order of `AddSlide`'s refusals; `Slides.from_data` returns the order and refuses an item that
is not a record with `ValueError`; tests for the refusals of `Slides.to_data` and `Slide.from_data`; `_ID` and
`_is_whole` come from `objects.py` instead of a third copy; `Slides.__len__` (unused) and a test that compared the frame
with itself are gone. Left as they are: two commit subjects of step 1 (`ac449481`, `e71968c4`) are not in the
imperative (coding-standards §10) and are pushed; the error for an anchor of another kind now reads "not a slide
anchor: the kind is …" (a client or the AI sees it; nothing reads its words); a creates snapshot shows `slides` as
records, which the web client does not read (it asks `slides`).

**Run before delivery:** the gate (`scripts/check_debt.py --ci`; everything clean but six setup errors of
`clients/linux/tests/test_connect_flow.py`, whose module fixture saw its first server not answer within 40 s; the same
tests pass alone and in the whole Linux client suite, 655 passed, 64 skipped; the fixture discards the server's
output, so the cause is not known: likely three servers measuring their password hashing at once under the gate's
load), E2E `@core` (58 passed, 53 skipped, 2 xfailed, as before), creates' browser scripts against three one-app
servers as CI starts them (`slides`, `creates-styles`, `print-creates`, `describe-creates`, `present`, `dock`, `keys`,
`objects`: all good).

## Step 2 · Slides in a workbook (D1471, D1473), 2026-11-22

- **Model.** `WorkbookModel.slides` (the core's `Slides`) and `tabs: list[Tab(kind, id)]`, kept by `add_sheet`,
  `drop_sheet`, `add_slide` and `remove_slide` only; `sheets` stays a dict in the order of the tabs, so everything that
  walks the sheets in order (files, print, the AI's lens) did not change. `AddSheet.index` counts the slides too; an
  index of an old log is the same number, since an old workbook has no slides. `AddSheet` refuses an id a slide has.
  `AddSlide(id, name, index, description)`/`RemoveSlide(id)` are computes' own. A slide must have a name (it is a tab),
  like a sheet. The event `SheetsChanged` (`sheets`) became `TabsChanged` (`tabs`); the web client still reloads on
  `sheets` from an older server. State schema 17.
- **Who builds a workbook by hand** (the xlsx and ods readers, and tests) puts sheets in with `add_sheet` now: a sheet
  put straight into `sheets` is in no tab and its objects would not be stored.
- **Wire.** `tabs`, `slide` (creates' answer without notes and time), the event `tabs`. The object methods take
  `slide`, `x`, `y` beside `sheet`, `row`, `col` (`CELLS_AND_SLIDES`); exactly one of `sheet`/`slide` for a new object,
  and a moved object stays on its kind of tab. `add_object` and `shapes` came to computes for a slide only (D1232: a
  sheet still has no text boxes or shapes); `computes_methods_with(library)` as for the two other apps.
- **Files** (`claudia_computes_io/slide_plan.py`): a copy of the workbook in which each slide is a sheet is what the
  writers get, so charts and pictures on a slide are written by the code that writes a sheet's. Slide objects are
  scaled by 0.45 (1600 × 900 into the 720 × 432 of a chart tab) and hung at the nearest cell; one smaller than the
  smallest object of a sheet (20 px) is written at 20 px. The loss is `slide` with the slide's name; nothing in the web
  client shows export losses yet (see the report). An edited import with a slide is not patched (`UnsupportedEdit`),
  so the server writes it afresh.
- **Web.** `lib/slide-host.ts`: `SlideHost`, what `SlideCanvas.vue` needs; creates' `objectsOn` is `slideObjects` now
  (computes' `objectsOn` is a sheet's). Showing, holding and letting go of a selection (`showRegions`, `holdRegions`,
  `releaseRegions`, `holdObject`, `letGoOfObject`) moved into `BaseSession` from both sessions, which had the same
  code. `InsertBar` shows Present only when it is given its words. A computes slide uses the workbook's own styles: its
  Body text is 13 px, small on a 1600-unit slide (see the report).
- **Print.** The layout library's `SheetDocument` takes a `PrintedSlide`: one landscape page with the sheet's footer,
  the slide drawn by `drawSlide`/`placedSlide`, which `layoutSlides` uses too (no change to its pages). A slide has no
  print setup: the bar's Portrait does nothing for it.
- **Browser script** `e2e:computes-slides` (on the computes server): there is no way to make a slide yet, so it
  imports a Claudia export (D1272) made with one by Python.
