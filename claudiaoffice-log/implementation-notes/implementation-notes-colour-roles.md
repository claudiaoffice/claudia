# Colour roles: the document's palette (D200–D203)

Branch `shapes-n-images`, the model half of the round whose UI half is the object style menu. The owner's ask, in
his words: colours should carry meaning the way a paragraph style does, be applied as a whole to a document, and
changing the signifying colour should change everything that signified it.

Four questions he settled before the work started: **fixed roles to start** but a set that will grow; the palette
is **part of the document**, so it looks the same on whichever server it is opened, and may come with a template
later; a **raw hex stays allowed** and is only warned about, never blocked; it reaches **composes' paragraph styles
from day one**.

Three more that the code forced, and that he settled during it: model first and UI in a second patch; the built-in
styles get converted now; **nine** roles rather than the seven in the mockups.

## What the shape of it is

```
ColourRole   = id, name, purpose, colour        (claudia_core.palette)
Palette      = an ordered mapping of them, plus readings()
Reading      = foreground, background, ratio, floor, ok, words
```

A style names a role instead of a colour:

```
color: @accent                     the role
color: @accent/55                  the role at 55% opacity
border-left: 3px solid @highlight  inside a shorthand, like any other colour
```

`CSS_VERSION` goes to **2**. The role form is accepted by `_color` and by nothing else, so a role can land only
where a colour belongs — not because a rule says so, but because every other value check refuses `@` anyway (a font
name may not hold one, nor may a length or a keyword). The one thing the allow-list had to give up is the blanket
ban on `@` in a value, and that narrowing was free.

### Why `@accent` and not `var(--accent)`

`ALLOWED_CSS` refuses `url()`, `var()` and `calc()` on purpose: whatever reaches a browser must be literal, because
a style is something a stranger's document brings along. A role would have broken that if it travelled as CSS. It
does not. `resolve_css` replaces the roles with colours on the server, and `StyleBook.views(colours)` sends three
forms of every style:

| field | holds | who reads it |
| --- | --- | --- |
| `css` | what the style sets itself, roles included | the style menu, to edit |
| `computed` | the parents resolved, roles still named | the style menu, to show |
| `resolved` | the same with roles replaced by colours | the client, to draw |

So the ban stays exactly as it was, and a client never learns the role grammar. The consequence is that a palette
change has to **re-send the styles as well as the palette** — `palette._tell` emits `PaletteChanged` and
`StylesChanged` together — because the client cannot work out the new `resolved` for itself. That is the same
reasoning `StylesChanged` already used for a parent style whose children follow it.

The web client follows this in four places: `cssOf`, `TextEditor.vue`, `StyleMenu.vue` and `StylesDialog.vue` draw
from `resolved`. `StyleEditor.look` does too, so that a colour swatch has a colour it can paint; picking a hex
there therefore writes a literal, which is precisely what leaving the palette means.

## The nine roles

`text`, `muted`, `page`, `surface`, `structure`, `accent`, `accent-text`, `attention`, `highlight`.

Seven were drawn in the mockups. The code said nine: composes' Quote, Remark and Definition carry three distinct
accent hues (apricot, rose, iris), and flattening them onto one accent would have lost a distinction the design has
today. The owner chose the ninth-and-tenth-role option over flattening and over leaving those three styles holding
literal hexes.

The colours are the suite's own — ink, paper, iris, rose, apricot — so writing the built-in styles in terms of roles
changed what they *mean* and not what they look like. A document opened yesterday is the same colour today.

### Where the conversion is exact and where it is not

Exact: every flat hex, and the softer inks, which become `@text/82` and `@text/78` instead of
`rgba(31, 26, 51, 0.82)`. A tint now follows the ink it is a shade of.

Not exact, deliberately: the pale washes that were written as the suite's "mist" (`#E7E1F4`, and `#E3EFED` in
computes) are now `@accent/14` — `@accent/8` in composes, whose shapes float over text. No opacity of iris
reproduces mist exactly, because mist is bluer than paper and iris is not: the result is within about 3 of the old
colour on white and about 12 on paper. That was accepted rather than worked around. A wash that follows the accent
is the behaviour a palette exists for, and a pale lilac wash is what "mist" meant in the first place.

Also changed on purpose: computes' plain shape was teal where a slide's and a text's were iris. All three now say
`@accent`, so a shape carried between the apps keeps looking like itself — which was the point of the shared object
layer.

## Contrast: checked, reported in plain words, never prevented

`PAIRINGS` says which roles are read against which and the floor each has to clear: 4.5:1 for words, 3:1 for a
border or a rule. A `Reading` carries no verdict text, so each client says what a failure means in its own words
and its own language. The warning a person sees is "White on this yellow will be hard to read", not "1.42:1" — the
owner's judgement on the mockups, that a ratio will not be understood by ordinary users.

`attention` and `highlight` are **not** paired. They are ornament in the built-in styles (the bar down the side of
a Remark, of a Quote), and WCAG's 3:1 is for what a reader must make out to use or understand a page. Pairing them
anyway had a brand-new document reporting its own Highlight as too faint — apricot on paper is 1.99:1 — which is how
a warning teaches people to ignore warnings. The day either role carries words or a boundary it gets a pairing, and
the check comes with it.

## Two things the mocked menu could not have done

`core.SetObjectStyle` did not exist. An object's `style` was settled by `AddObject` and could never be changed
again, so the most ordinary act the style menu offers — picking a style for the shape you have selected — was
impossible. `replace_object` already checks that a style exists, so the command needed nothing new of its own.

`change_style`, `rename_style` and `check_css` lived in `composes_methods` alone, so creates and computes could
read their styles and not change them. `claudia_server.styles.add_style_methods(table, guard=...)` now registers
`styles`, `palette`, `set_role`, `replace_palette`, `set_object_style`, `change_style`, `rename_style` and
`check_css` into an app's table. composes passes `_people_only` as the guard, keeping its own rule that the
assistant suggests and does not write (D63, SEC-10), and keeps only `set_style` and `deviate_style` — the two that
name paragraphs.

## What this cost

Snapshots: `state_schema` 5 in composes and computes, 6 in creates. Old logs break, as agreed in D177.

Numbering: this round is **D200–D203**. `worker-pool` has independently allocated D177–D179 for unrelated
decisions while this branch used the same numbers, so the gap is deliberate — the owner chose it over adding a
third collision to the two this log already carries (D151, D160).

Removed: `shapes-n-images.patch`, a patch file committed to the repository root by accident, and
`claudiaoffice-log/decision-log/decision-log.md`, a 263-line copy left over from "Backlog transfer step 1" and
superseded by the one beside it.

## Still open

The UI half: the object style menu, the palette panel, the role rows in place of bare swatches, and the contrast
warning — all four artboards are mocked and agreed. Nothing offers a person a role of their own yet, and no command
adds one: `ReplacePalette` can bring a different set, which is what a template will use, but a "+ New role" button
has deliberately not been drawn for something that cannot be done. composes' web client still has no `objects`
event handler at all. Cell styles in computes (E6.13) will take their colours from this same palette when they
arrive.
