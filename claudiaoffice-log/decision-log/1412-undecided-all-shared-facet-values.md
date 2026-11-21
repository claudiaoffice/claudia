---
id: D1412
title: "Whether the values of a facet can be shared by several styles"
status: undecided
applies-to: all
date: 2026-11-21
round: "Glossary session: domain notions (glossary.md)"
supersedes: []
superseded-by: []
---

# D1412 · Whether the values of a facet can be shared by several styles: open

**Open.** A style holds its own values for the facets it uses (glossary: Facet, Style kind, Slot). Today values are
shared in two ways only: a style is **based on** one other style and inherits what it does not set, and a style
names **palette colours**, which every style using them follows. The question is whether the values of one facet
could also stand on their own, named, and be pointed at by several styles.

**Example.** "Quote" and "Explanatory note" should read alike (the same text facet) but differ in their box;
"Warning" has a red box. Note based on Quote gives Note Quote's text, but Note cannot also take Warning's box,
because a style has one parent. With shared facet values, a text facet "Reading text" would be used by Quote and
Note, and changed once for both.

**Against, for now.** A second set of named things a person has to manage, where D306 wants a clean style
language without micromanagement. The likelier next step is a palette of type (named fonts, as palette colours
name colours), which would cover the most common sharing with less to manage.

**Notes.** Asked of the owner in the glossary session, 2026-11-21, after a sketch of a text box's slots and the
facets they read; the owner kept values a style's own for now and asked to keep the question. Storing a style's
values grouped by facet (E1.19) is independent of it.
