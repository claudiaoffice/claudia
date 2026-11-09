# The styling dialogs: one menu, three apps (D204–D206)

Branch `shapes-n-images`, the UI half of the colour-roles round. The model half (D200–D203) shipped first by the
owner's choice; the four artboards it is built from were agreed before either.

## What was already there, and what it cost to reuse

`style-host.ts` had said since it was written that "a text is one host; cells and shapes will be others". Taking it
at its word is most of this round: the style menu, the look panel, the all-styles dialog and the CSS editor are the
ones composes has used all along, and creates and computes reach them through one adapter each.

What the interface needed:

```
parts: { words, box }   what the thing being styled actually has
roles, readings         the document's palette, and how it reads (D200, D202)
setRole(role, colour)   the one write the palette dialog makes
```

`parts` is why a picture shows no fill and no font controls, a chart shows a border but no words, and a shape and a
text box show both. They are **left out, not greyed out** — the rule already written for an image's context menu:
an empty control that can never do anything is worse than no control. Different from the per-object Format items,
which *are* disabled when nothing is selected: those will work the moment there is something for them to be about.

New on the server: `deviate_object_style`, the mirror of composes' `deviate_style`. "Change this shape only" makes a
style from the one the object has and points the object at it, provisionally named and `to_name` until somebody
names it (D75). Verified in a browser: the gallery gained "Plain shape (changed) · to name · 1".

## Colour by meaning

The picker lists the roles by name and purpose, with how strong a wash for a fill. "Off the palette…" is one step
further in, and a literal colour then reads as a deviation: it says a palette change will leave it behind and offers
the nearest role in one click. Never blocked. Measured: picking `#C0392B` for a border offered "Use Attention
instead", Attention being rose.

The palette dialog shows each role with its purpose and how many styles name it, what it is read against in plain
words, what a change *would* cost before it is made, and which styles will move with it. The verdicts under "Read
against" are about the colour the role has now, so while a different one is typed above the heading says "as it is
now" — otherwise the two read as contradictions.

**No ratio is ever shown to a reader** (D202). The server sends them so a client can decide whether to warn; what
the client says is "Accent text on Accent will be hard to read."

The palette a document started with comes from the server's own `palette` answer (`builtin`), not a copy of the nine
roles in TypeScript. A second list of the same colours is a thing to keep in step, and the one that drifts is always
the copy.

## Two defects the browser found that the tests did not

**A warning that fired on a brand-new shape.** The readability note compared the words against the fill, and
`toHex('rgba(91, 75, 196, 0.14)')` gives `#5b4bc4` — it drops the opacity. So a pale wash a shade off the page was
read as full-strength iris, and every new shape was reported unreadable. `flatten()` now lays a translucent colour
over what is behind it (the palette's `page`) before the check. This is the same mistake the pairings table avoided
in D202, arrived at from the other direction: a warning that fires on the defaults is how a warning gets ignored.

**A dialog disabled for its owner.** `objectStyleHost.readOnly` returned true when nothing was selected, which was
reasonable for the look controls and wrong for everything else: it disabled the whole Colours dialog for an owner
who simply had no shape selected. `readOnly` now means only "you may not write to this document"; what needs a
selection is `current`, which is undefined without one, and `apply`/`deviate`, which say so themselves.

Both were found by driving a real browser. Neither could have been caught by the unit tests as they stood, because
both were about what the page *showed*, not what the functions returned — the same lesson as UX-10.

## What a merge broke, and what that cost

The branch had `claudia_creates_io.pptx` dead on arrival: `ImportError` on a name the object-layer refactor had
removed. Behind it, the importer called a type alias, `apply_edits_to_pptx` read the flat object, and the exporter
dropped every colour because a built-in style now names a role rather than a hex. Nine package tests, six catalogue
entries, three `ruff` errors and one `mypy` error, all from two branches that were each green on their own. Written
up as UX-11; the colour-flattening decision is D206.

The catalogue's `spec.py` files now share `claudia_test_documents.edits`, so there is one correct way to retext and
move an object instead of four chances to get it wrong.

## Still open

`StyleDef` has no `kind`. composes' Format menu therefore leaves out `plain-shape` and `plain-image` **by id**,
which is honest but not durable: a style somebody makes by deviating from one of them would want the same treatment
and there is nothing to test for. `kind` is already on the backlog under E1.10 and is the real fix.

Cell styling (E6.13) is untouched: computes' Format menu says plainly that its styles are for the object you
select. Those cells will take their colours from this same palette when they arrive.

Nothing yet lets a person define a role of their own. `ReplacePalette` can bring a different set, which is what a
template will use and what "the colours it started with" uses today, but no "+ New role" button is drawn for
something that cannot be done.
