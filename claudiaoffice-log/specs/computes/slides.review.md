# Review of `slides.feature` (draft of 2026-11-22)

How to answer: for each question, "ok" accepts my proposal; anything else replaces it. When all are answered I move the
answers into the feature file (and the decision log, in the range of the branch) and delete this file.

**Suggested order of review:** the `@core` rules first (a chart as a slide; Move to Slide; more on a slide; the slide
goes with its last object: 11 scenarios), then the `@extended` ones (8).

**Not in this file:** step 1 of E6.31 (the slide's type, frame and anchor move into the core) changes nothing a person
sees; creates' own browser scripts (`web/e2e/slides.cjs`, `present.cjs`, `print-creates.cjs`) and E2E `@core` are its
check that nothing changed.

## Questions

**Q1 · The name of a slide made by "Move to Slide".** Names are one namespace (D550): a slide and its chart cannot both
be called "Sales". Proposal: **the slide takes the chart's name, and the chart gets the next free "Chart N"**, as a new
chart would. The tab is what people see and look for by name; the chart on it is found through its slide. The same
holds for Edit ▸ Chart…: the name typed there is the slide's, the chart gets "Chart N". Other ways: (b) the slide is
named "Sales (slide)" and the chart keeps its name; (c) the slide gets the next free "Slide N", and the chart keeps its
name.

**Q2 · Which tab is shown when a slide goes with its last object.** Proposal: **the tab before it** (the one after
it, if it was the first). That is what a person who deleted something on the last tab she was on most likely expects
to see.

**Q3 · After Insert as a slide.** Proposal: the new slide is shown and **the chart on it is selected**, so that the next
thing a person does (making it smaller to put a text beside it) needs no click first.

**Q4 · Undo of "Move to Slide".** Proposal: one undo puts the chart back on the sheet at its old cell and in its old
size, removes the slide, and shows the sheet again. Redo moves it again.

**Q5 · A viewer.** Proposal: a viewer sees slides like sheets; in a chart's object menu "Move to Slide" is shown but
cannot be chosen, as every entry of that menu that changes the document (D1225, `object-menu.ts`).

**Q6 · The words when a slide is written to ods or xlsx.** Proposal, in the list of what a file cannot hold:
"The slide “Sales chart” was written as a sheet: a workbook in this format has no slides." German: "Die Folie
„Sales chart“ wurde als Blatt geschrieben: Eine Arbeitsmappe in diesem Format hat keine Folien."

**Q7 · Printing a slide.** Proposal: printing while a slide is shown prints that slide as one landscape page, laid out
as creates lays out a slide (`layoutSlides`), with the chart as a picture. Printing the whole workbook prints each slide
as such a page between the sheets, in tab order.
