---
id: D305
title: "A style has a `kind` that names the slots it can be used in, and its properties are restricted to the facets of those slots"
status: current
applies-to: all
date: 2026-11-10
round: "Styles as facets, slots and bundles (styles round)"
supersedes: []
superseded-by: []
---

# D305 · A style has a `kind` that names the slots it can be used in, and its properties are restricted to the facets of those slots

**`StyleDef` gets a `kind`: the slots the style can be used in** (`paragraph`, `box`, `outline`, and the combinations the built-ins need), and a style's properties are checked against the facets of its kind. A menu that offers styles for a slot offers only those whose kind fits it. A style made by deviating inherits the kind of its parent.

**Notes.** Replaces composes' filtering of `plain-shape` and `plain-image` by id (`OBJECT_STYLE_IDS` in `TextWorkspace.vue`, which said itself that the real fix is a `kind` on the style) and closes the "Not done: kind on a style" item of E1.10. A style that sets a property outside its kind's facets is refused with a sentence that names the property, the way `validate_css` already refuses an unknown one.
