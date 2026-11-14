# Templates, layouts and slots in creates — screens and a model for discussion (E10.4, E10.5, E10.3)

Written 2026-11-13 on branch `real-world-docs`, second patch of three. **No code**: E10.4 says it needs a design
discussion with a mock-up before it is `ready`, and the owner chose mock-ups first. Everything here is a proposal; the
four questions at the end are D373–D376, all `undecided`.

## Why now

A real PowerPoint deck the owner supplied (kept out of the repository) imports as nineteen empty slides: all of its text
and pictures sit in placeholders inherited from layouts, which `pptx_to_slides` does not read. The same deck has 14
slide masters, each with one layout and a copy of the same theme — the trace of slides pasted with "Keep source
formatting". The import fix needs a place to put a placeholder (a slot) and a master (a template), and the second
finding is the confusion the product vision names: *in PowerPoint one is often unsure where the slide in front of you
was derived from*.

## The screens

| File | Panels |
|---|---|
| `mockups/creates-templates-slide.svg` (`.png`) | **A** a slide that names its layout (a chip beside the style picker) and its template (a line above the slide); empty slots say their kind; the footer and number carry a lock. **B** clicking the footer explains it instead of selecting it: *Change it in the template…* or *Make a named variant…*. **C** choosing another layout, with a preview of the re-flow. |
| `mockups/creates-templates-editor.svg` (`.png`) | **D** the template editor: the same window with an apricot band ("Editing the template Workshop — changes apply to all 7 slides"), layouts on the left, the layout's slots on a grid, the selected slot's kind, styles, hint and position on the right. **E** page format and running items (footer, number, date, and the layouts they are not shown on). **F** a named variant. |
| `mockups/creates-templates-import-and-new.svg` (`.png`) | **G** the templates step of opening a pptx: 13 identical masters proposed as one template, one different master kept apart, unused layouts not brought over, a missing font named. **H** slides that differ from their layout, each with *Put it back*, *Make the layout so…*, *Variant…*. **I** File ▸ New: a template, or "What would you like to achieve?" (D71) suggesting one and an outline. |

## The model behind them (proposal, D373)

* **A template** is what slides share and no slide can change: the page format, a palette (D200), the fonts, the named
  styles (D300–D318), a set of **layouts**, and the **running items** (footer text, slide number, date, and the
  layouts that do not show them).
* **A layout** is a named set of **slots** plus which running items it shows. A **named variant** is a layout with a
  base and a named difference; it inherits everything else.
* **A slot** has a kind (`title`, `text`, `picture`; later `chart`, `table`, `formula`), a name, a frame on the 50-unit
  grid of E10.15, the style its words take and the style its box takes (the two slots of D304), and a hint for when it
  is empty. One `title` slot per layout at most: the slide's name in lists and outlines.
* **A slide** is the name of its layout, the content of each slot, and free objects. Content in a slot is an ordinary
  object of the shared object layer (D177) that says which slot it is in; its frame and styles come from the slot
  until it *differs*. Only place and size can differ — a look that differs is a named style (D75, D306) — and a slide
  that differs is listed (panel H), never refused.
* **Notes** are not a slot: every slide has them (presenter mode, E10.2).
* **Every change is one command** with its inverse, in the history: `SetSlideLayout`, `EditLayout` (add, move, change,
  remove a slot), `SetRunningItems`, `SetPageFormat`, `CreateVariant`, `PutBackInSlot`. Changing the template restyles
  every slide in one step.

**Changing a slide's layout** (panel C): each slot takes the content of the same kind, in order (title to title, the
first text to the first text...). Content with no slot of its kind becomes a free object where it was, and the
command's result says how many. Free objects never move.

## Import and export (the real-world fix, D375)

| pptx | claudia | odp |
|---|---|---|
| slide master + theme | template | master page (`style:master-page`) and its styles |
| slide layout | layout | `presentation:presentation-page-layout` |
| placeholder `type`/`idx` | slot of that kind (`title`/`ctrTitle` → title, `body`/`obj`/no type → text, `pic` → picture) | `presentation:placeholder` / `presentation:class` |
| `dt`, `ftr`, `sldNum` placeholders | running items | `presentation:footer`, `date-time`, `page-number` |
| a slide's placeholder shape | the slot's content, with the text and the inherited formatting resolved | `presentation:class` on the frame |

**Masters that are the same design are proposed as one template** (panel G): two masters are the same when their
theme colours, fonts, background and the frames and text styles of their layouts' placeholders are equal after
normalising (ids and names left out). The person confirms; a master that differs stays its own template or becomes a
named variant. Layouts no slide uses are not brought into the model and stay in the file, as an edited pptx keeps
everything the model does not hold (D219).

Export writes a template as one slide master with its layouts, and a variant as a layout of its own, named after it.

## Menus, keys, languages, access (D376)

* **Format ▸ Layout…** (Ctrl+Alt+L) opens panel C; **Format ▸ Template…** (Ctrl+Alt+E) opens the editor. Both follow
  the house pattern Ctrl+Alt+letter (D, F, O, R are taken). To check before building: Ctrl+Alt+L locked the screen on
  older Ubuntu releases, and ⌘⌥L / ⌘⌥E on macOS (generated menus in `clients/macos`, `clients/windows`, the Linux
  manifest).
* **Every label goes through gettext** (D31). Layout and template names of built-in templates are translated;
  imported names are kept as the file has them.
* **BITV.** The layout picker is a grid of options navigated with the arrow keys; popovers follow the dialog focus
  rules (`mockups/dialog-focus-trap.svg`); the template line is the slide's accessible description ("Slide 4 of 7,
  layout Content and picture, template Workshop"); inherited items keep full contrast and are announced as "from the
  template"; a slide that differs is announced as such. The template editor's band is a landmark, so F6 reaches it.
* **Desktop clients** show the web content; only their generated menus need the two new entries.

## Questions for the owner (undecided)

1. **D373 — the model above:** template → layouts → slots, slides hold slot content and free objects, only place and
   size may differ.
2. **D374 — where a template lives.** Proposal: inside the presentation, as its own copy (a document stays
   self-contained and private, D72's "no server reads another document by itself"). A template *file* (`.potx`,
   `.otp`, or a claudia presentation used as one) is a source to copy from at File ▸ New and, later, to *pull* an
   update from on request, as embeds do (D72). Not a live link.
3. **D375 — importing masters:** identical masters proposed as one template, after the person's yes; unused layouts
   left out of the model.
4. **D376 — menus and keys:** Format ▸ Layout… (Ctrl+Alt+L) and Format ▸ Template… (Ctrl+Alt+E), the layout chip
   beside the style picker.

## A proposed order of work once agreed

1. The model, the commands and the layout chip and picker (A, C), with the built-in templates.
2. **The pptx and odp mapping of masters, layouts and placeholders, with G** — the step that makes the real deck open.
3. The inherited-item popover and the template editor (B, D, E).
4. Variants and the list of slides that differ (F, H); File ▸ New (I) with E12.1.
