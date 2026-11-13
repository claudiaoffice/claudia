---
id: D201
title: "Nine roles to start, and the apps' built-in styles hold no literal colour at all"
status: current
applies-to: all
date: 2026-11-08
round: "Colour roles: the document's palette (thirty-third round)"
supersedes: []
superseded-by: []
---

# D201 · Nine roles to start, and the apps' built-in styles hold no literal colour at all

**Nine roles to start, and the apps' built-in styles hold no literal colour at all.** `BUILTIN_ROLES`: text, muted, page, surface, structure, accent, accent-text, attention, highlight. Every built-in style in all three apps is written in terms of them, so replacing a new document's palette really does recolour it. The colours are the suite's own (ink, paper, iris, rose, apricot), so the conversion changed what the styles *mean* and not what they look like. Two consequences worth stating: composes' softer inks are now `@text/82` and `@text/78` rather than `rgba(31, 26, 51, 0.82)`, so a tint follows the ink it is a shade of; and the pale washes that were written as "mist" are `@accent/14` (`@accent/8` in composes, which floats over text), a tint *of* the accent. computes' plain shape was teal where a slide's and a text's were iris — all three now say `@accent`, so a shape carried between the apps keeps looking like itself.

**Notes.** Seven roles were drawn in the mockups; the code said nine. composes' Quote, Remark and Definition carry three distinct accent hues, and flattening them onto one would have lost a distinction the design has today — the owner chose the ninth-and-tenth-role option over flattening or over leaving those three styles holding literals. The mist tints are the one place the conversion is approximate rather than exact: no opacity of iris reproduces mist exactly (mist is bluer than paper, and iris is not), so `@accent/14` is within about 3 of the old colour on white and about 12 on paper. That was accepted deliberately: a wash that follows the accent is the behaviour a palette is for, and a pale lilac wash is what "mist" meant in the first place.
