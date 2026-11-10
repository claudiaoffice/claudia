---
id: D200
title: "A document carries a palette: colours named by what they mean, and a style names a role rather than a colour"
status: current
applies-to: all
date: 2026-11-08
round: "Colour roles: the document's palette (thirty-third round)"
supersedes: []
superseded-by: []
---

# D200 · A document carries a palette: colours named by what they mean, and a style names a role rather than a colour

**A document carries a palette: colours named by what they mean, and a style names a role rather than a colour.** `claudia_core.palette` holds `ColourRole` (id, name, purpose, colour) and `Palette`, an ordered mapping of them. A style writes `color: @accent`, or `@accent/55` for that role at 55% opacity; `CSS_VERSION` goes to 2 and `_color` is the only value check that accepts the form, so a role can land only where a colour belongs. The palette is **part of the document** (`state_schema` 5 in composes and computes, 6 in creates), so a document looks the same on whichever server it is opened; it is changed only by `core.SetRole` and `core.ReplacePalette`, so a change is in the log, can be undone and is seen by everybody. A client never sees the role grammar: `StyleBook.views(colours)` sends `css`, `computed` **and** `resolved`, and the client draws with `resolved`. `ReplacePalette` is refused while a style names a role the new palette has not.

**Notes.** The owner's request, in his words: colours should carry meaning the way a paragraph style does, be applied as a whole, and changing the signifying colour should change everything that signified it — which is an axis `StyleBook` cannot express, because one accent is a shape's `fill`, another style's border and a heading's `color` at once. The four questions he settled: fixed roles to start but a set that will grow; the palette is part of the document, and may later come with a template; a raw hex stays allowed; it reaches composes' paragraph styles from day one. **`@accent` and not `var(--accent)`:** the allow-list refuses `var()` and `calc()` on purpose, so that the CSS reaching a browser is always literal — a role is resolved before any CSS is produced, and that rule stays exactly as it is. The one thing the allow-list had to give up is the blanket ban on `@` in a value; every other value check refuses it anyway, so the narrowing was free. Changing a role re-sends the styles as well as the palette, because a client is deliberately unable to resolve a role itself.
