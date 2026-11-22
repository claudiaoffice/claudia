# Implementation notes: E6.31 Slides in computes

Branch `e6-31-slides-in-computes`, decisions D1470–D1473 (range D1470–D1489). The design is
`notes/e6-31-slides-in-computes.md`, the scenarios `specs/computes/slides.feature`. This file keeps what the code does
not say, step by step.

## Step 1 · The slide shared by the core (D1470), 2026-11-22

- `claudia_core/slides.py` has the frame, `SlideAnchor`, the rule that keeps an object on a slide (`check_on_slide`,
  `turned_on_slide`, `room_on_slide`) and `Slide`/`Slides`. Creates' `check_anchor`, `turned_anchor` and
  `room_for_new_object` call them; the anchor's refusal of another kind now says "not a slide anchor" instead of
  "creates knows only slide anchors", as two apps read it.
- **Creates keeps `SlideModel.slides` as the order** (the presentation, as before): about 140 places in creates,
  creates-io, the server and the tests read it, and in the ODP reader and python-pptx `slides` means something else, so
  renaming it would have been a risky sweep for nothing. The records are `SlideModel.slide_records` (`Slides`), and
  they replace `slide_names` and `slide_descriptions`. The architecture note says so.
- **That a slide with objects cannot go is the core's `close_holder`**, as for every holder; `Slides` does not know
  objects. D1470 says so now.
- **The state** (schema 18) stores the slides as records in the presentation's order (`[{id, name?, description?}]`);
  the keys `names` and `descriptions` are gone. An older state is not read (pre-release, D1430): the test that read a
  state from before names and part of the test of a state from before notes went with it.
- `claudia_creates` still re-exports `SLIDE_WIDTH`, `SLIDE_HEIGHT` and `SlideAnchor`, as it re-exports `ObjectBody` and
  `VisualObject`: creates-io imports them from there and did not change. The server's `slide_lens.py` imported them
  from `claudia_creates.model` and now from `claudia_core`.
- **The kernel's purity test** (`packages/claudia-core/tests/test_purity.py`) forbade the word "slide" in the kernel;
  it leaves the list with D1470, as "paragraph" did with D181.
- **Found:** five `autodata` lines in `docs/api/claudia_creates.rst` had never been directives (no blank line after the
  paragraph above them), and named constants creates does not have (two of them exist nowhere). They are gone. Three
  of them (`MIN_OBJECT_SIZE`, `ASPECT_TOLERANCE`, `OBJECT_KINDS`) are in `claudia_core.__all__` but not on the core's
  API page; that is left as it is (not this story's).

**Run before delivery:** the gate (`scripts/check_debt.py --ci`; everything clean but six setup errors of
`clients/linux/tests/test_connect_flow.py`, whose module fixture saw its first server not answer within 40 s; the same
tests pass alone and in the whole Linux client suite, 655 passed, 64 skipped; the fixture discards the server's
output, so the cause is not known: likely three servers measuring their password hashing at once under the gate's
load), E2E `@core` (58 passed, 53 skipped, 2 xfailed, as before), creates' browser scripts against three one-app
servers as CI starts them (`slides`, `creates-styles`, `print-creates`, `describe-creates`, `present`, `dock`, `keys`,
`objects`: all good).
