# xlsx/docx/pptx additive extensions (D135)

Three new workspace packages, each `claudia-core` + its one app package + its one format library:

- `claudia-computes-io` (`openpyxl`): `xlsx.py` — `workbook_to_xlsx(WorkbookModel)` (base export: one worksheet per
  sheet, each cell as its stored content, a formula as its text with the leading `=`) and `add_pivot_table(xlsx_bytes,
  ...)` (one row field, one summed data field; builds the cache definition, cache records and pivot table parts plus
  the relationships/content-type overrides that reference them, by editing the zip `openpyxl.load_workbook` already
  wrote). `_sheet_part`/`_resolve_target` resolve a sheet's own zip member through `workbook.xml` + its rels rather
  than assuming sheet order — needed in practice: openpyxl writes the workbook's own sheet relationships as
  package-absolute targets (a leading `/`), not relative ones, which the first version of this got wrong (silently
  dropped the pivot table on an openpyxl load-edit-save round trip, caught by a test, not by the LibreOffice check).
- `claudia-composes-io` (`python-docx`): `docx.py` — `text_to_docx(TextModel, track_suggestions=True)` (base export:
  one paragraph per block, the six built-in style ids mapped to Word's own Title/Heading 1/Heading 2/Quote, anything
  else to Normal). Every open suggestion with a replacement becomes a real `w:ins`/`w:del` pair, built with
  `docx.oxml.OxmlElement` (python-docx's own documented escape hatch) and appended to the paragraph's element — a
  suggestion is reviewable in Word like any other tracked change. No `w:date` is written: the model carries no
  timestamp for a suggestion, so one is not invented.
- `claudia-creates-io` (`python-pptx`): `pptx.py` — `slides_to_pptx(SlideModel)` (base export: a 16:9 deck matching
  `SLIDE_WIDTH`/`SLIDE_HEIGHT`'s own aspect ratio; text boxes; the three built-in shapes — circle, rectangle,
  triangle — mapped to the matching `MSO_SHAPE`, anything else falls back to a plain rectangle; best-effort styling
  from the object's `BUILTIN_STYLES` entry: font-size and color, fill and stroke for shapes) and
  `add_transition(pptx_bytes, slide_index, kind, speed, advance_on_click)` (`fade`/`wipe`/`push`/`none`, edited
  straight into the slide's own part — no new parts needed, transitions live inline).

All three keep the same "first slice" status as `claudia_computes`/`claudia_composes`: not in
`scripts/api_surface.py`'s `PACKAGES`, no `CHANGELOG.md`, static `version` in `pyproject.toml` rather than a
`_version.py`.

Checked against LibreOffice (`soffice --headless --convert-to <format>`), not just structurally:
- The pivot table's source range, field roles (Region as a row field, Amount as the summed data field) and the
  **live-computed sums** all come through correctly as ODF `table:data-pilot-table`; openpyxl's own `ws._pivots`
  also parses it back after a round trip.
- The tracked change comes through as ODF `text:tracked-changes`/`text:changed-region` with the right author and
  the deleted text preserved; python-docx's own `paragraph.text` does not show the tracked word at all (only
  `w:r` elements that are direct children of `w:p` count, and the tracked ones sit under `w:ins`/`w:del` instead) —
  expected, not a bug, and covered by a test.
- The transition comes through as ODF `smil:type="fade" smil:subtype="crossfade"`; LibreOffice maps the speed to
  `presentation:transition-speed="fast"` regardless of what was asked for (checked: the source XML still says
  `spd="slow"`) — a LibreOffice import quirk, not an injection bug.

Not done, on purpose: `odfdo` is not a dependency of any of the three packages (D135) — no ODF gap has been spiked,
and D70 wants the ODF-first story (E6.9/E9.5/E10.3) built as its own thing, not bolted onto this slice. Multiple row
fields, column fields and filters on a pivot table; styling fidelity for docx/pptx beyond the built-in style names
and a few CSS properties; shapes with a free-form (non-autoshape) outline in pptx — all left for when E6.9/E9.5/E10.3
are actually picked up.
