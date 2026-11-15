---
id: D461
title: "The print layout and paper go to pptx, the language to pptx and odp; a pptx import says what it does not show of a look"
status: current
applies-to: creates
date: 2026-11-15
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D461 · The print layout and paper go to pptx, the language to pptx and odp; a pptx import says what it does not show of a look

**What a presentation file can hold of how the deck is printed and which language it is in is written and read; what it
cannot is a loss, and the pptx import lists the looks, formattings and links the model leaves out, as the odp one does.**

**Notes.**

* *Print setup (pptx).* The layout is `p:prnPr/@prnWhat` of `presProps.xml` (`slides`, `handouts2`…`handouts9`), the
  paper and its orientation the size of the notes page (`p:notesSz`, long side first when the page lies on its side).
  A file that says nothing, or a notes page of PowerPoint's own size (7.5 × 10 in), reads as the setup of a new
  presentation: it says nothing about how *Claudia* should print it. Margins other than the paper's own and the page
  numbers have no place in a pptx: `not-written` / `print_setup` (also for a patch). A patch writes layout and paper
  into a kept file (both parts it changes are owned, everything else stays byte for byte).
* *Print setup (odp).* ODF has no place for a print layout of slides that LibreOffice would read; still `not-written`.
* *Language.* odp: the default paragraph style of `styles.xml` (`fo:language`, `fo:script`, `fo:country`), through a
  module shared with the odt (`claudia_odf_io.language`: composes-io's code moved there, tags `zxx`/`none` as before),
  written, read and patched. pptx: `lang` on every run of text boxes, shapes and notes (fresh file); a file's language
  is the one most of its runs say. A kept pptx is not rewritten run by run (a deck can mix languages): a changed
  language is `not-written` / `language` for a patch, and not for a fresh file.
* *Import losses (pptx).* `look` (a fill, an outline, a font, a size or a colour other than the ones Claudia writes for
  the default style: compared with a file we write for it), `formatting` (bold, italic or underlined runs) and
  `link`, as `odp_import_losses` reports them; none for what Claudia itself wrote.
