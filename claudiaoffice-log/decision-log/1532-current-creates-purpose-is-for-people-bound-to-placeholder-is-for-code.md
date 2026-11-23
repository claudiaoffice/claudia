---
id: D1532
title: "A placeholder's purpose is what it is for in a person's words; which placeholder an object is bound to is a technical field of its own"
status: current
applies-to: creates
date: 2026-11-23
round: "E10.4 Templates, layouts and placeholders (branch e10-4-templates-and-layouts)"
supersedes: []
superseded-by: []
---

# D1532 · Purpose is for people, bound_to_placeholder is for code

`SlideAnchor.purpose` is on a layout's object that is a placeholder: "Title", "Body", "Left list". It is what a person sees
and what changing the layout of a slide goes by (an object follows the placeholder with the same purpose on the new
layout, else it becomes free where it stands). `SlideAnchor.bound_to_placeholder` is on a slide's object and says which
placeholder it keeps the place of. They are two fields because one is meaning and the other mechanics, and a purpose
copied onto a slide object would have to be kept equal to the layout's by hand. Neither is written when empty. A purpose
is unique within its layout.
