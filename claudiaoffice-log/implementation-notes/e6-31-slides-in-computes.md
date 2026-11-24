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
- **Files** (`claudia_computes_io/slide_plan.py`): a copy of the workbook in which each slide is a sheet (made with the
  model's own methods, so it is checked like any change) is what the writers get, so charts and pictures on a slide are
  written by the code that writes a sheet's. Slide objects are scaled by 0.45 (1600 × 900 into the 720 × 432 of a chart
  tab) and hung at the nearest cell; one that would be smaller than the smallest object of a sheet (20 px) is scaled
  less, keeping its proportions. The sheet keeps what was written about the slide. Its name is written the way Excel
  allows a sheet's (the stricter format), for ods too. The loss is `slide` with the slide's name; nothing in the web
  client shows export losses yet (see the report). An edited import with a slide is not patched (`UnsupportedEdit`),
  so the server writes it afresh.
- **Web.** `lib/slide-host.ts`: `SlideHost`, what `SlideCanvas.vue` needs, the types of a slide's objects and shapes,
  and `SlideActions`, what both sessions do the same way on a slide (show one, select, move, resize, put a text box or
  shape there); each session has one. Creates' `objectsOn` is `slideObjects` now, computes' is `sheetObjects`. Showing
  the others where I am, holding and letting go (`showRegions`, `holdRegions`, `releaseRegions`) moved into
  `BaseSession` from both sessions, which had the same code. When a slide goes, the tab before it is shown (the one
  after it if it was the first, D1473). `InsertBar` shows Present only when it is given its words. A computes slide uses the workbook's own styles: its
  Body text is 13 px, small on a 1600-unit slide (see the report).
- **Print.** The layout library's `SheetDocument` takes a `PrintedSlide`: one landscape page with the sheet's footer,
  the slide drawn by `src/apps/slides.ts` (`drawSlide`, `placedSlide`, `slideFrame`), which `layoutSlides` uses too (no
  change to its pages). A slide printed from a workbook does not say that its words are not hyphenated, as a
  presentation does (computes' styles do not hyphenate). A slide has no
  print setup: the bar's Portrait does nothing for it.
- **Browser script** `e2e:computes-slides` (on the computes server): there is no way to make a slide yet, so it
  imports a Claudia export (D1272) made with one by Python.
- **Review (two axes) and what changed after it:** the shared slide drawing and the slide's types left creates' modules
  (§3: apps do not import each other); `placedSlide` lost its flag (CONTRIBUTING §2); `SlideActions` instead of the same
  code in two sessions; `_placed` on the server is two small functions; `slide_plan` uses the model's methods, not the
  stored form; `restore` refuses tabs that miss a sheet or a slide; a new sheet's id is free among the slides too, and
  the pivot dialog's sheet name among their names; tests with literal cells instead of the formula.

## Step 2, fixes UX-72 and UX-73 (D1474), 2026-11-22

- **Search on the slides (UX-72).** `workbook_texts` (`claudia_computes/search.py`) goes through the tabs in their
  order: a sheet gives its cells, a slide the words of its text boxes and the labels of its shapes, with creates' places
  `{slide, object, source}` (`object_texts` of the core, as creates reads them). `replace_command` makes one step of
  the cells (`SetCells`) and the words (`edit_object_text`), so undo takes both back. The scope `{slide}` searches one
  slide; the server refuses a slide that is not there. On the web, `sheet-search-host.ts` says "All sheets and slides"
  when there are slides, and "This slide" for the scope `sheet` while a slide is shown, when Selection is not offered
  (the host's `scopes` follow the tab shown, and the panel falls back to the first scope when its own goes). A match on
  a slide shows the slide and selects nothing (selecting would hold the object from the others at every step through
  the matches, as creates does not either); the slide marks the match in its words (`marksFor` of
  `slide-search-host.ts`). The host's `revision` carries the tab shown, so a listed search runs again when another tab
  is shown (before, "This sheet" kept the matches of the sheet that was shown when it ran). Descriptions and speaker
  notes are not searched: a workbook's slides have neither in the UI.
- **Review (two axes) and what changed after it:** the server refuses a scope whose `slide` is not a string as a bad
  request; the locks of an object are asked once for its box and its label; `place_of` says its refusal once;
  `describeSheets` takes the printed tabs as one `PrintedTabs`; the browser script starts its browser through
  `browser.cjs` (CODE-17); changelogs of computes and the server. Left as they were: the history's label "Replace in N
  places" is English and its plural made by hand, as every app's history labels are (UX-22); the refusal for too many
  changes still says "cells".
- **The print bar (UX-73).** With a slide shown, "Contents" is "This slide" and "Whole workbook" (no Selection: a slide
  has no cells), and the status line counts sheets and slides apart ("2 sheets and 1 slide").
- The search panel's scope list was cut off at 45 % of the row ("All sheets and slide"); it may now take 55 %.

## Main merged in with CODE-78 (typed refusals, D1510), 2026-11-23

The refusals that step 1 and 2 brought and that a person can meet are `Refusal`s now: "a slide needs a name" (computes'
`AddSlide` and rename), "the object must stay on the slide" and "this object is too large to turn that way" (the core's
`check_on_slide`, `turned_on_slide`), with German. A workbook's slide has its own sentence for a taken name
(`WorkbookModel.name_taken["slide"]`). The checks of ids and tabs (`tab_index`, `check_new_tab`, the anchors) stay
English: only a wrong client fails them.

## Step 3 · A chart becomes a slide (D1475), 2026-11-23

- **Model** (`claudia_computes/chart_steps.py`, A5). A chart is made, moved and taken away in one `Batch`, so one undo
  takes all of it back: `as_new_slide` (`AddSlide` right after the tab shown, the chart's definition and the chart
  filling the frame), `on_slide` (half the frame, in its middle), `on_sheet`, `to_new_slide` ("Move to Slide":
  `AddSlide` after the sheet, `MoveObject` to the slide's corner, `ResizeObject` to the frame) and `removal` (the
  objects, every definition nothing else shows, and every slide left empty). `NewChart` carries the ids and the name.
  The chart tab is gone: `Chart`, `AddChart`, `RemoveChart`, `model.charts`, the event `charts` and the stored key
  `charts`. State schema 18; a stored workbook with chart tabs is not read (no upgrade, D1475).
- **The core.** `ObjectModel.may_change_holder(obj, new)` replaces the flag `objects_change_holder`: composes moves an
  object to any paragraph; computes from a sheet to a slide and back (the undo of "Move to Slide"), never between two
  sheets or two slides. `TakeBackSlide` (a `RemoveSlide` of its own, not a flag: CONTRIBUTING §2) is the undo of `AddSlide`: it does nothing while the slide holds an
  object, so undoing "Move to Slide" keeps a slide a colleague has put something on.
- **Wire.** `insert_chart(definition, show_as, place, name?)` with `show_as` `slide` (`{after}`), `on_slide`
  (`{slide}`) or `sheet` (`{sheet, row, col, w, h}`); `move_to_slide(object)`; computes' `remove_object` goes through
  `removal`. `free_name(kind)`, a read method of every app, says the next free generic name ("Chart 2", in the
  language of the window). A new slide's id is the next free `p<n>` among the tabs, its name the next free "Slide n" in
  the language of the request. `charts`, `add_chart`, `remove_chart` and `add_diagram_object` are gone;
  `define_diagram` and its relatives stay until step 4 renames them.
- **Files.** A slide is still written as a sheet (`slide_plan`), its objects scaled by 0.45 (`SHEET_SIZE`, the size a
  chart tab had). The writers lost the chart tab; the loss `chart`/`tab` is gone.
- **Web.** `Session.insertChart`, `moveToSlide`, `freeName` (in `BaseSession`). Edit ▸ Chart… offers "A slide" first,
  and "A floating object on the sheet", or "On this slide" while a slide is shown; on a slide, "Data from" lists every
  table and query result of the workbook and says what to do when there is none. The name field is the chart's and
  starts with `free_name("diagram")`. The object menu of a chart on a sheet has "Move to Slide" after Style… (no key,
  D1475; `claudia-menus.xlsx`, Context menus row 25). After a new slide is made it is shown with nothing selected; a
  chart on the slide shown or on a sheet is selected. `ChartView` draws a chart in the frame of its object only (the tab
  that filled its pane is gone); `SlideCanvas` draws a chart through the session's figures, at the slide's own units and
  scaled with the slide, as print draws it. Print: the chart tab is gone from the web client and the layout library
  (`PrintedChart`); a chart on a slide is drawn as its picture (`asDrawn`, as on a sheet).
- **Found and fixed on the way.** CODE-77 (undoing a chart left its definition, and Plotly said the element was gone):
  the chart and its definition are one step now, and `ChartView` checks that its element is still there after loading
  Plotly. CODE-83 (writing in a text box on a workbook's slide was an internal error): the typing of an object's words
  (`insert_text`, `remove_text`, `text_regions`, `text_moved`) moved from creates into the core's `ObjectModel`. A chart
  on a slide printed as "the chart has no picture" (A8 had not been met: step 2's slide had no chart).
- **Assumptions** (the spec does not say): "A slide" is the first choice while a slide is shown too; a chart put on the
  slide shown takes half the frame in the middle and is selected; on a slide the first table or query result is
  chosen; the dialog's own error line is gone, a refusal is said by the notice every write gives.
- **E2E.** `tests/e2e/specs/test_computes_slides.py` binds the @core rules of `slides.feature`; the name of a chart is
  read in Name & describe…, and whether something was selected is noted when the slide is shown. The browser script
  `e2e:computes-slides` keeps the rules of search and print. Not bound yet (they skip, saying the step): the @extended
  scenarios of a chart on a sheet "at the selected cells", the dialog while a slide is shown, two
  people (Ben, Vera), a slide with a text box left, renaming a slide, "+" and printing. The scenario "A second chart on the
  slide" is dropped (owner, 2026-11-24): its Background had no table or query result, and on a slide the dialog offers
  only those (D1475).
- **Review (two axes) and what changed after it:** the undo of `AddSlide` is a command of its own, `TakeBackSlide`,
  not a flag on `RemoveSlide` (CONTRIBUTING §2); `may_change_holder` takes the object (D1471 named it `(old, new)`, two
  anchors), so in a workbook only a chart changes holder (a text box cannot leave a slide and leave it empty); `_check_place` and one table of the places
  `show_as` takes; `SlideHost.figures` instead of two optional methods; `freeName` catches only a refusal of the
  server; the vulture whitelist follows the methods; a reasoned `noqa` in composes. Left as they were: the server
  checks the tab, slide and sheet of a place before `chart_steps` does (its refusals are said to the person, the model's
  are for a wrong client); the history's label "Move to slide" is English, as all history labels are (UX-22); "Move to
  Slide" has no key (owner, D1475).

## Main merged in with E7.11, 2026-11-23

E7.11 had taken the ID CODE-79 for a bug of its own (and E7.2 reserves CODE-80 to CODE-82), so the bug of a slide's
text box is CODE-83; the commit that fixed it still says CODE-79 in its message.

## Step 4 · The chart names of E1.18 (D1476), 2026-11-24

- **How.** A script renamed `diagram`/`Diagram`/`DIAGRAM` to `chart`/`Chart`/`CHART` in the files where the word names
  a chart, line by line, leaving every line that speaks of a Mermaid diagram, a formula or a picture drawn from text,
  and never touching "Diagramm" (German for a chart). Left out as whole files: what speaks of a container's diagram
  (`claudia-render`, `claudia-typeset`, `rasterise`, `raster`, `sizing`, the core's `containers`, `ContainerEditor`,
  the GTK client's manifest), Word's drawings in `docx`, the style sheet of a diagram in `pptx`, the specs whose
  "diagram" is a container's (`new-object-sizes.feature`, the invariants of composes), the glossary, the vision, the
  history, the catalogs (regenerated) and the API snapshots (regenerated). Every remaining "diagram" in the code was
  read afterwards; the prose the script left odd ("a chart's chart spec", lines of the chart tabs that step 3 missed)
  was written by hand.
- **Kept on purpose:** `diagram` among the legacy pointer fields of an object body (`_LEGACY_POINTERS`,
  `testing.body_before_ref`), the name old bodies were written with, as `rendered`. An old body of the kind `chart`
  never existed, so the tests of old bodies use the kinds that still read (shape, image, table).
- **Stored names change outright:** computes' state schema 19 stores the definitions under `charts`; nothing reads a
  state, log or file with the old names (D1430, E1.16). The test of step 3 that said "no `charts` in the state" says
  what `charts` holds now; the old wire names (`diagrams`, `define_diagram`, `add_diagram_object`) are among the
  methods the server does not know.
- **Review (two axes) and what changed after it:** three comments the script had made wrong went back to "diagram"
  (the legacy pointer fields in `objects.py`, twice; a Mermaid diagram's style sheet in `odp.py`), and a line of
  history that should not have changed (schema 6 of computes, `AddSheet`'s old logs); `ChartDefinition`'s docstring no
  longer speaks of a tab; the local `chart` of `insert_chart` is `new_chart`, so `chart=new_chart.spec_id` reads as
  the id it is; `docs/versioning.md` names the renames and removals that are not upgraded. Left as they were: the
  computes parameters `chart_id` of `chart_figure` and `chart_cells` (the id of a chart's definition, as on the wire);
  `.charts` of the ods and xlsx patches, which are the file's chart frames; the versions and `PROTOCOL_VERSION`, which
  move when main is released, as for step 3; repeated `kind === 'chart'` checks and the twin xlsx/ods chart code,
  which this rename did not make and does not change.

## Main merged in with D1499 (one owner), 2026-11-24

The server's changelog had entries on both sides under Unreleased; the compiled catalogs were made again from the merged
`.po` files.

## Step 5a · A slide is a tab of its own, its objects where they were (D1477), 2026-11-24

- **One plan** (`claudia_computes_io/_placed.py`). `file_tabs(model)` is the tabs of a file in the workbook's order: a
  sheet by its name, a slide by its name as a sheet may be called in Excel (`tab_name`, which was `sheet_name` of
  `xlsx_charts`). `placed_objects(model, size)` is every object on its tab, bottom first: `x`, `y` in pixels from the
  corner of the tab (what ods writes), `pin` the cell the corner is in and how far into it (what xlsx writes), and the
  size in pixels. An object of a sheet is at the corner of its cell, as before; one of a slide where it is, scaled by
  `SlideSize.px_per_unit` (1.0, `ONE_TO_ONE`). `offset_of` moved here from `chart_plan`, and `cell_at` (the ods reader
  had one) is its inverse with the offset in the cell. A slide's tab has no cells and is written with the model's
  default sizes of a column and a row (96, 26 pixels), which `cell_at` counts with.
- **No duplicates.** `_charts.py`: `definition_of` (was `_definition` in both patches), `chart_change` (the comparison
  both patches made of a chart before and after), `written_charts(model, placed)` (both formats had a loop of their own),
  `hold_charts` (the block both readers had) and the base `FileChart` (both readers' fields and `spec`; each format adds
  where the chart is in its file). One placing function per format: xlsx `pinned_at(pin, width, height)` for the anchor
  of a chart and a picture; ods `place_of(placed, rotation)` for the frame of a chart, a picture and a frame moved by
  the patch. The patches place a chart with `placed_on_its_sheet`, the same plan.
- **The writers** go through `file_tabs` instead of `model.sheets`; `FileTab.sheet(model)` is what a tab writes (a
  slide: a sheet without cells by its name). The drawings of a tab are added in the order they are stacked, charts and
  pictures together (ods put the charts first and the pictures after, with the right `z-index`).
- **Not reported.** Writing a slide as a tab is no loss (owner, Q5); `slide_losses` went with `slide_plan`.
- **Not written (yet).** What was written about a slide (its description): neither format writes one for a sheet
  either, and the step-2 copy only carried it to a sheet that was not written with it.
- **Tests.** `tests/test_slide_tabs.py` replaces `test_slide_plan.py`; the two tests of `Drawings` in
  `test_xlsx_charts.py` give it a placed chart.

## Step 5b · The mark of the slides, and the pictures of a file (D1478, CODE-67), 2026-11-24

- **The mark** (`claudia_computes_io/slide_mark.py`). `SlideMark(slides, size)` with `to_text`/`from_text` (JSON;
  a value somebody changed into something else is no mark) and `slide_tabs`; `properties_of(names, size)` is what a
  file is written with (nothing without slides). xlsx: `claudia_opc_io.set_custom_properties` after the drawings;
  ods: `new_meta(info, properties)`.
- **Reading back** (`claudia_computes_io/_read_back.py`). Both readers now collect their tabs as sheets first and their
  drawings as `FileObject`s (charts first, so that their ids stay `o1`… for the patches, then pictures), and hand them
  to `file_tabs_of` (which tabs are slides: named by the mark, no cells, every drawing fits a slide, nudged onto it
  as a slide's objects are) and `hold` (adds the tabs in order and the objects: on a sheet at their cell, on a slide in
  its units). `within_limit` keeps a tab's objects to `MAX_OBJECTS_PER_SHEET`; `held_on` counts what a sheet's
  `chart` and `picture` losses no longer include. `hold_charts` of step 5a went into `hold`.
- **Where a drawing is, read once.** xlsx: `drawn_anchors` (every anchor of the drawings, with its cell, offsets, size
  and the sheet's geometry, read lazily); ods: `drawn_frames` (every frame alone on a sheet, with its cell and
  `frame_corner`: `svg:x`/`svg:y`, or the corner of a turned frame's box, to a hundredth of a pixel). Charts and
  pictures are read from them. The corner is worked out only for a tab that may be a slide: the sheet's geometry is
  parsed only then (and for a two-cell anchor, as before).
- **Pictures** (`xlsx_pictures.file_pictures`, `ods_pictures.file_pictures`) use what composes' docx and odt readers
  had, now shared: `claudia_opc_io.drawingml` (`turn_of`, `cropped`, `shown_part`, `is_decorative`) and
  `claudia_odf_io` (`held_frame`, `graphic_styles`, `pixels`). `ods_layout.pixels_of` is `pixels`, rounded.
- **Names** are written (`cNvPr name`, `draw:name`: the object's name, else "Chart n" / "Picture n") and read back,
  unless the model refuses the name (another thing has it): then the object has none.
- **The ods reader no longer changes** `_Table.left_out` for the charts it holds: `_left_out(table, held)` subtracts
  them where losses are said (the import losses and the patch's removed sheet), so reading a file twice (an import
  with pivot tables did) cannot subtract twice.
- **Assumptions** (the spec does not say): a tab is a slide only if every drawing on it fits a slide (a drawing moved
  far off it in another program makes the tab a sheet); a name of the file (a named range) that points at a slide tab
  is not looked at (we never write one); a picture imported into a kept file and then moved is reported as `object`
  until the patch learns pictures (CODE-66).
- **Tests.** `test_slide_tabs.py` (a slide comes back as a slide at both sizes; the mark in both formats; a renamed tab
  and one typed into are sheets), `test_pictures.py` (CODE-67 for both formats, and a kept file edited keeps its
  picture), `claudia-opc-io/tests/test_custom_properties.py`, `test_drawingml.py`, `claudia-odf-io/tests/test_meta.py`.

## Step 5c · Text boxes and shapes on a slide's tab (D1479), 2026-11-24

- **Shared with composes.** `claudia_odf_io.boxes` holds what composes-io's `_boxes.py` and `_odt_boxes.py` had that
  is not about a text: `BoxLook`, `look_of` (any model with `styles` and `palette`, the `Styled` protocol),
  `is_written`, `authored`, `points_of`, and the ODF elements (`box_element` without the anchoring, which each app
  does its way; `graphic_properties` without the wrapping; `held_box` with `plain_words`, since composes' plain words
  are `body` and computes' `body-text`; `box_look`; `odf_properties`, which was in composes' `_wrap`).
  `claudia_opc_io.drawingml` holds DrawingML's `solid`, `outline`, `look_in` (composes' `_colour` and `_look_of_file`),
  `PRESET`/`SHAPE_OF`, `UNKNOWN` and `EMU_PER_POINT` (`_docx_tables` had a copy of its own). The architecture of step 5
  put the look into `claudia_core.boxes`; it is beside the ODF layer instead, because `BoxLook` counts in EMU and the
  core depends on no package (said in D1479).
- **computes-io.** `_boxes.py`: `written_boxes` (a slide's boxes), `box_styles` (for the mark), `authorship_lost`,
  `words_css`, `styled` (the mark's styles where the model has them and the look is theirs, else plain and `look`).
  `xlsx_boxes.py`: `box_anchor` (placed by `pinned_at`, as charts and pictures) and `file_boxes`; `ods_boxes.py`:
  `box_frame` (placed by `place_of`) and `file_boxes`; `OdsLookWriter.words_style` and `box_style` make the named
  paragraph style of the words and the automatic graphic style of the box. `Drawings._append` is the one place an
  anchor gets its number (charts, pictures and boxes). `ods_chart_files.drawn_frames` walks rectangles, ellipses and
  custom shapes too.
- **Reading.** `FileObject` says the loss it is when not held (`kind`: `chart`, `picture`, `shape`, or `object` for an
  ods text box), its place among the drawings of the file (`order`: objects are put into the model in that order, so
  the stack is the file's whatever kind they are) and, for a box, its look. `held_of` holds a box only on a slide;
  `lost_looks` counts the boxes whose look the import reports.
- **Facets.** `_unwritten.facets` has `boxes` (a slide's boxes with the outlines they use), written only by a fresh
  export (`FRESH_ONLY`); `objects` keeps the rest (a box on a sheet).
- **Checked by eye.** An xlsx and an ods with a chart, a text box, a picture and a triangle turned by 30° on a slide,
  printed to PDF by LibreOffice 7: everything where it is on the slide, the triangle turned clockwise, the words in
  their place. Excel could not be run here.
- **Assumptions** (the spec does not say): a box without a name is written as "Text box n" / "Shape n" and comes back
  with that name; a workbook's own (not built-in) style of a box is not in the file, so a box read into a new workbook
  that has no such style has the plain style (and `look` when it looked otherwise); the words of a box are written as
  one run, so references in them (which computes does not make) would be written as their mark character.
