# Import/export coverage of the document functions (audit, 2026-11-14)

Question (owner): which functions of the three apps are wired to the import/export layer, which are not? Lists in composes were the known case.

**Method.** Read the code in the working copy of `claudia` (state of 2026-11-14): every registered command of composes, computes and creates and of the core (`core.*`), every wire method of the three server modules, against the converters in `claudia-composes-io`, `claudia-computes-io`, `claudia-creates-io`, `claudia-odf-io`, `claudia-opc-io` and the server's `office_export.py` / `formats.py`. Cross-checked with the implementation notes, decisions D70, D147, D217–D220, D299, D370–D380, D401–D414, D438–D441 and the test-document catalogue. **Nothing was run** (static reading only); where I could not tell from the code, the row says "verify".

## How to read the tables

Three paths exist for every format (D441):

- **Export**: a document made in Claudia, written as a new file (`text_to_docx`, `workbook_to_ods`, …).
- **Import**: a file read into the model (`docx_to_text`, `xlsx_to_workbook`, …).
- **Patch**: an imported file that was edited, written back by changing only what changed (`apply_edits_to_*`). Whatever Claudia never modelled stays in the file.

Status: ✅ wired · ◐ partly · ❌ not wired and **nothing says so** (silent) · 🔔 not wired but **reported** as a loss code (D299, D405) · n/a not content of a document.

"Silent" is the worse case: the person exports, believes the document is complete, and it is not.

---

## 1. Summary

1. **Composes is the least connected app.** Only paragraph text, four built-in styles and suggestions-as-tracked-changes reach docx/odt. Lists, page setup, language, palette, style definitions, floating objects (images, text boxes, shapes, LaTeX/Mermaid renderings) and alt text are in no converter. Most are not even reported.
2. **Computes** is the best wired (values, formulas, cell looks, number formats both ways, in both formats). Gaps: row heights and column widths, charts, floating objects, names/tables on export, sheet changes in an imported xlsx.
3. **Creates** exports text boxes, shapes, pictures, notes and (as literal formatting) styles. Gaps: rotation in odp, print setup, language, templates, and on import every look and every picture.
4. **Loss reporting is uneven**: odt/odp/ods are good; docx and pptx have no import-loss list at all; docx and the xlsx/pptx export lists are incomplete. This goes against D299/D405.
5. **The patch path can hide a change.** When a person edits an imported file, a change to anything the patcher does not know (e.g. a list made in Claudia) is neither written nor reported, and the answer says `patched: true`. Needs a general fix, not one fix per feature (section 5, A).
6. **docx export is visibly not Claudia's**: the file is US Letter, its author is "python-docx" and its date is 2013 (python-docx's template; checked).

---

## 2. composes (docx = Word, odt = OpenDocument)

| Function (command / wire method) | Export | Import | Patch of imported file | Notes |
|---|---|---|---|---|
| Typing, split, join (`InsertText`, `DeleteText`, `SplitBlock`, `JoinBlocks`) | docx ✅ odt ✅ | docx ✅ odt ✅ (paragraphs of the flow; text in tables is not) | docx ◐ text and style of existing paragraphs only; **adding or removing a paragraph raises `UnsupportedEdit`** and the export falls back to a fresh file that drops the file's tables and pictures (reported as `not-patched`). odt ✅ add/remove | The docx gap hits the most common edit |
| Apply style `SetStyle` / `set_style`: Title, Heading 1, Heading 2, Quote, Body | ✅ ✅ | ✅ ✅ | ✅ ✅ | By name only (D407) |
| Apply a style that is not one of those five (custom styles, `deviate_style`) | docx ❌ written as Normal; odt 🔔 `style` | docx ❌ body, silent; odt 🔔 `style` | as export | |
| Heading 3–9 in a file | n/a | docx ❌ body, silent; odt 🔔 `heading-level` | | Model has two heading levels |
| **Style definitions** (`CreateStyle`, `ChangeStyle`, `RenameStyle`, `RemoveStyle`; Format ▸ All styles) | ❌ the definitions in the file are fixed text in the code (`_STYLE_XML`; python-docx's template), so changing "Heading 1" in Claudia changes nothing in the file | ❌ (D407, by name only); the look of a file's styles is not read, and not reported | n/a | Silent in both formats |
| **Palette** (`SetRole`, `ReplacePalette`) | ❌ composes writes no colour at all (creates and computes resolve roles, D211) | ❌ | n/a | Silent |
| **Lists** (`SetListItem`, `CreateList`, `ChangeList`, `RemoveList`; `make_list`, `indent_item`, `continue_list`, `list_start`; Format ▸ List) | ❌ every item is a plain paragraph, marker and level gone. `odt_export_losses` has no list code | docx ❌ "List Bullet"/"List Number"/`numPr` ignored, silent. odt 🔔 `list` (counted, items flattened to paragraphs) | ❌ a list made in Claudia in an imported file is not written (silent). Lists already in the file stay (`odt-lists-and-sections`) | The case you reported. Needs: ODF `text:list` + list styles, docx `numPr` + numbering part; both directions; levels 0–8; schemes bullets/numbers; start number; continue-list |
| **Page setup** (`SetPageSetup` / `set_page`: paper, orientation, margins, page numbers) | ❌ odt: fixed A4 portrait, 2 cm margins (`pm1`); docx: US Letter | ❌ not read | ❌ | Silent. Page numbers: no footer field written |
| **Language** (`SetLanguage`, D915) | ❌ no `fo:language` / `w:lang` | ❌ | ❌ | Silent; also decides hyphenation |
| Suggestions as tracked changes (`ProposeSuggestion`, `ResolveSuggestion`, `AcceptSuggestion`; "include suggestions") | docx ✅ odt ✅ (replacements, dated, by author) | ❌ existing tracked changes are not imported as suggestions (odt 🔔 `tracked-change`; docx: their text is skipped, silent) | ◐ new suggestions are written; **the server calls `apply_edits_to_odt` without `info` and `change_times`**, so changes are dated 1970 and `meta.xml` is not updated (D411 gap; docx passes the times) | |
| Remarks (suggestion without replacement) | odt 🔔 `remark`; docx ❌ | n/a | | |
| Authorship of text (`Run.author`) | odt 🔔 `authorship`; docx ❌ | n/a | | By design (format cannot hold it) |
| **Floating objects**: text boxes, shapes, images (`AddObject`, `RemoveObject`, `MoveObject`, `ResizeObject`, `RotateObject`, `SetText`, `SetObjectStyle`, `SetParagraphStyle`, `DefineShape`, `DefineImage`, `ForgetImage`) | ❌ both, silent | docx ❌ silent; odt 🔔 `frame` (not imported) | ✅ the file's own objects stay; objects made in Claudia are not written | |
| Alt text / decorative (`DescribeObject`; BITV 1.1.1) | ❌ (follows objects) | ❌ | ❌ | creates writes it (pptx `descr`, odp `svg:desc`); composes cannot because it writes no objects |
| LaTeX / Mermaid rendered containers (`DefineRendering`, `UpdateRendering`, `ForgetRendering`; D66, D390–D395) | ❌ same as objects (they are pictures) | ❌ | ❌ | |
| Document metadata (title, author, dates from the log; D411) | odt ✅ docx ❌ (python-docx defaults) | n/a | odt ◐ (see suggestions row) | |
| Things Claudia never models: tables, footnotes, links, inline formatting, fields, comments, headers/footers | n/a | odt 🔔 (table, list, index, frame, formatting, link, hidden kinds); **docx ❌ no loss list at all** (`_reader` returns `None`) | odt ✅ byte-exact outside edited paragraphs; docx ◐ re-saved through python-docx, other parts restored | |
| LaTeX/Beamer import/export (D87), bibliography (D86) | no converter in the repository | | | Decided, not started (as far as the code shows) |
| History, chat, presence, locks, checkpoints, restore | n/a | | | Not content of the file (D145) |

---

## 3. computes (xlsx = Excel, ods = OpenDocument)

| Function | Export | Import | Patch | Notes |
|---|---|---|---|---|
| Values and formulas (`SetCells`) | xlsx ✅ ods ✅ | ✅ ✅ | ✅ ✅ | Formulas translated (Excel ⇄ OpenFormula, `_xlfn.`); untranslatable → value + 🔔 `formula` with reason |
| Array and spilled formulas | 🔔 as for formulas | 🔔 `formula/array`, read as values | ◐ cells inside refuse an edit (`UnsupportedEdit`) → fresh file | |
| Dates and times | ✅ ✅ | ✅ ✅ (🔔 `date` for ods without a date format) | ✅ ✅ | |
| Add / remove sheet (`AddSheet`, `RemoveSheet`) | ✅ ✅ | ✅ ✅ | xlsx ❌→ `UnsupportedEdit`, fresh file (reported `not-patched`, charts and pictures of the file lost). ods ✅ (🔔 `stale-reference`); reorder ✗ | |
| Insert / delete rows and columns (`Structure`) | ✅ ✅ (cells move) | n/a | ◐ cells are written; what the file holds that points at positions (charts, merges, validations, conditional formats, comments) is **not shifted**, and I found no loss code for it. **Verify** | Risk of silent damage in an imported file |
| Cell styles and looks (`SetCellStyle`, named styles, palette, D307–D318, D379) | ✅ ✅ | ✅ ✅ (file's direct formats become provisional styles) | ✅ ✅ (D380) | 🔔 `look` for what no style holds |
| Number formats (D378) | ✅ ✅ | ✅ ✅ | ✅ ✅ | |
| **Row heights, column widths** (`ResizeLines`, D135, D215) | xlsx ❌ silent; ods 🔔 `layout` | ❌ ❌ not read, no loss code | ❌ a resize in Claudia on an imported file is not written | The loss code exists only for the ods export |
| **Charts** (`AddChart`, `RemoveChart`, `DefineDiagram`, chart specs; D204–D209) | xlsx ❌ silent ("No charts yet"); ods 🔔 `chart` | 🔔 `chart` (stays in the file) | ◐ the file's charts stay; adding/removing one in Claudia is not written, silent | |
| **Floating objects** (images, shapes, text boxes: `AddObject`, `MoveObject`, `ResizeObject`, `RotateObject`, `DescribeObject`) | xlsx ❌ silent; ods 🔔 `object` | 🔔 `picture` / `shape` | ◐ as charts | Alt text not written either |
| **Names and tables** (`DefineName`, `RenameName`, `RemoveName`, `RestoreNames`; D600–D603) | ❌ ❌ no defined names or tables written, none reported. A formula that uses a name is written with the name in it and the name is missing in the file (likely `#NAME?` in Excel; **verify with a test**) | xlsx ✅ (names, tables as names); ods 🔔 `named-range` (not imported) | ❌ ❌ a name defined in Claudia is not written | The most serious computes gap |
| SQL queries (`define_sql`, D605–D607) | ◐ the formula cannot be said; written as its value, probably 🔔 `formula` (**verify**) | n/a | | |
| Alternatives `{a\|b}` (D294, D298) | ◐ first alternative + note, 🔔 `alternatives` | ◐ | ◐ | Lossy by design |
| Random numbers (`RANDOM`, D291–D293) | ◐ Excel formula that draws the same distribution, else value + 🔔 `formula/random` | ✅ Excel's inverse functions read back as `RANDOM` | | |
| Random seed, resample (`SetRandomSeed`, `Resample`) | ❌ no place in either format; I found no loss code | n/a | | Minor |
| Outcome table, trace ("follow the computation"), random preview | n/a (views of the model) | | | |
| Merged cells, comments, validation, conditional formats, filters, pivot tables, protection, hidden sheets | n/a | 🔔 reported (both formats) | ✅ stay in the file | Not modelled |
| Language (`core.SetLanguage`) | ❌ | ❌ | ❌ | No converter in any app writes it |
| Document metadata | ods ✅ xlsx ❌ | | | |

---

## 4. creates (pptx = PowerPoint, odp = OpenDocument)

| Function | Export | Import | Patch | Notes |
|---|---|---|---|---|
| Slides (`AddSlide`, `RemoveSlide`) | pptx ✅ odp ✅ | ✅ ✅ | pptx ❌ `UnsupportedEdit` → fresh file (reported `not-patched`). odp ✅ add/remove, reorder ✗ | |
| Text boxes and shapes (`AddObject`, `RemoveObject`, `MoveObject`, `ResizeObject`, `SetText`) | ✅ ✅ | ✅ ✅ for text box, circle, rectangle, triangle. Other shapes: odp 🔔; pptx ❌ silent (no import-loss list) | pptx ◐ move/resize/retext/restyle only; add/remove object → fresh file. odp ✅ | Custom shape outlines (`DefineShape`): **verify** |
| **Rotation** (`RotateObject`) | pptx ✅ odp ❌ silent (no transform written) | pptx ✅; odp 🔔 `rotated-object` (object not imported) | pptx ✅ odp ✗ | |
| Pictures (`AddObject` image, `DefineImage`, `ForgetImage`; png/jpg/svg) | ✅ ✅ (svg: 🔔 `svg-fallback` / `svg-picture`) | ❌ stays beyond-claudia: odp 🔔 `picture`; pptx ❌ silent | ✅ stays in the file | |
| Alt text / decorative (`DescribeObject`) | pptx ✅ (`descr` + decorative mark) odp ✅ (`svg:desc`; 🔔 `decorative`) | ❌ (pictures are not imported) | | |
| LaTeX / Mermaid renderings (`DefineRendering`, …) | ✅ as pictures; 🔔 `rendering-pending` | ❌ | | Editability does not come back |
| Styles (`SetObjectStyle`, `SetParagraphStyle`, `ChangeStyle`, palette; D304–D311) | ◐ resolved to literal formatting (parents and palette roles taken in, D211); style **names** are not in the file | ❌ look not read: every text box becomes plain-box/body-text, every shape plain-shape (D407). odp 🔔 `look`; pptx ❌ silent | ✅ restyle of existing objects (both) | |
| Speaker notes (`SetSlideNotes`, D347) | ✅ ✅ (Markdown subset; odp 🔔 `notes-link/image/code/quote`; pptx does not report these) | ✅ ✅ | ✅ ✅ | |
| Planned time per slide (`SetSlideTime`, D343) | ❌ by design; odp 🔔 `planned-time`; **pptx silent** | n/a | | |
| Print setup (`SetPrintSetup`, D917) | ❌ ❌ silent (slide size fixed 16:9) | ❌ | | Layout/handouts have no Office equivalent; paper/margins do |
| Language (`SetLanguage`) | ❌ ❌ | ❌ | | |
| Templates, layouts, masters (E10.4, D68, D373–D376, undecided) | ❌ every pptx slide on the blank layout | ❌ masters stay in the file (D375 undecided) | ✅ stay | Not built in the model |
| Bullets/lists in text boxes | n/a today (model has `Paragraph.item`; creates has no list UI or methods) | | | Will need both converters when built |
| Document metadata | odp ✅ pptx ❌ | | | |
| Snap/grid (`SetSnap`), presenter mode, transitions | n/a (editing/viewing aids; `add_transition` exists as helper only) | | | |
| Tables, groups, charts, animations in files | n/a | odp 🔔 `table`, `group`, `object`, `transition`; pptx ❌ silent | ✅ stay | |
| LaTeX/Beamer export (D87) | no converter in the repository | | | |

---

## 5. Findings that cut across the apps

**A. A change to something the patcher does not know disappears silently.** `export_with_original` answers `patched: true` with an empty loss list. Each patcher compares only the slice it writes (text and style in composes, cells and looks in computes, objects in creates). Anything else changed since the import (a list, the page, a width, a name, a chart) is lost without a word. Suggested fix, once: before patching, compare the serialised state of every part the writer cannot write between baseline and current, and report each difference as a loss (`not-written`, with the feature). Then every new feature is covered by default, and the gaps in this list show up as warnings instead of nothing.

**B. Loss lists are incomplete or missing (D299, D405).** No import-loss function for docx and pptx (`formats._reader` returns `None`); no export-loss list for docx; the xlsx list lacks charts, objects, names, widths; the pptx list lacks planned time and the notes features that the odp list has; odt lacks lists, page, language, objects and styles.

**C. The fresh-file fallback destroys what a patch would keep.** docx (add/remove a paragraph), pptx (add slide/object), xlsx (add sheet) fall back to a new file and drop tables, pictures and charts of the original, with one `not-patched` line. odt, odp and ods do not have this problem for the same edits.

**D. The composes server does not pass `info` / `change_times` to the odt patch** (D411). docx passes `change_times`, but docx has no metadata path at all.

**E. The test-document library (25 cases) has no case** for lists made in Claudia, page setup, language, style definitions, floating objects of composes, charts or names in computes, widths, or rotation in odp. The cases that exist check that the file's own content survives an edit, not that Claudia's features reach the file.

**F. Related, not import/export:** Format ▸ List is not in the native shells' manifests yet (GTK, Windows, macOS menus do not show it), as the lists note says.

---

## 6. Suggested order to build (for discussion)

1. **A and B first** (general): the "unwritten changes" detector and the missing loss lists. Cheap, and it makes every later gap visible while it is open.
2. **Composes lists**, odt first (D70), then docx: `text:list` + list styles / `numPr` + numbering part, import and export, levels, start numbers; patch included. Add library cases.
3. **Composes page setup, language, palette and style definitions** (one slice: write styles from the `StyleBook` with palette roles resolved, as creates already does; page layout from `PageSetup`; language).
4. **docx patch for add/remove paragraphs** (then C disappears for composes).
5. **Computes names/tables on export**, then widths/heights, then charts (ods first).
6. **Composes objects** (images with alt text first; text boxes and shapes; renderings as pictures), same as creates export.
7. **Creates**: rotation in odp, print setup/paper, language, pptx loss lists; picture import.

## 7. What I could not settle (to verify with a test or a run)

- Computes: rows/columns inserted in an imported file vs. charts, merges, validations; names in exported formulas (`#NAME?`); SQL and spill export; whether `SetRandomSeed` has a loss code.
- Creates: custom shape outlines on export; slide-size handling on import when the file is not 16:9.
- Composes: whether any client-side path (PDF/print) matters for this list (it does not go through these converters).
- All "✅" mean *wired in code and covered by unit tests I could see named in the notes*; I did not run the suites or open exported files in LibreOffice/Word.
