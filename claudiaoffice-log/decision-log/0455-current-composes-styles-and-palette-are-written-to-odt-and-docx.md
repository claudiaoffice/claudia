---
id: D455
title: "The paragraph styles of a composes text are written to odt and docx with the colours of its palette"
status: current
applies-to: composes
date: 2026-11-14
round: "Import and export wiring (branch import-export-wiring)"
supersedes: []
superseded-by: []
---

# D455 · The paragraph styles of a composes text are written to odt and docx with the colours of its palette

**Every paragraph style of the model is written as a style of the file with its own look: the CSS it sets (D62), its palette roles (`@accent`, `@text/82`) replaced by the colours they have in the document's palette, and its parent as the style it is based on. `"styles"` and `"palette"` are written facets of both converters (D450). A property a file cannot say is a `style-property` loss, named `<style id>: <property>`; a style id the model does not have is still a `style` loss.**

**Notes.**

* *Names.* The built-in styles keep the names other programs know them by (`Standard`/`Normal`, `Title`, `Heading 1`, `Heading 2`, `Quotations`/`Quote`); the others are named by their name, made safe for odt, and never the same as another style or one the file already has (`Name_2`, `Name 2`): a file's style is not written over by a new one of the same name.
* *Colours.* A file has no palette roles and no opacity: `@accent/8` is written as the colour it shows on white paper (`#F2F1FA`). The roles are therefore not re-imported; a changed palette colour rewrites every style that names it, in a kept file, and no other.
* *Lengths and fonts.* `em`, `px`, `%` and the generic families are turned into points and a named family (`serif` becomes Liberation Serif...). Fonts are named, not embedded.
* *docx specifics.* Hyphenation is a setting of the document in Word: it is on when the body style hyphenates, and a style that says `none` or `manual` switches it off for itself; a style that hyphenates while the body does not is a `style-property` loss. A border's padding is the distance between border and text, so padding on a style with no border at all is a loss. Writing a style replaces what it set, and keeps where it stands in a document (outline level, keep with next).
* *Patching.* Only the styles whose look changed since the baseline are written again, with a new style that a paragraph now has; a file whose styles did not change keeps `word/styles.xml` byte for byte (docx) and every style element (odt).
* *Not yet.* A style the model has that is not a paragraph style (`box`, `outline`: they are the looks of floating objects, which wait for the objects slice of this round) is not written. Custom paragraph styles are written but not read back: a block with a style the file has under another name is body text (the `style` loss on import is unchanged).
