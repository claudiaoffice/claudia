---
id: D2006
title: "A pptx object keeps the name PowerPoint gave it, its automatic name too"
status: current
applies-to: creates
date: 2026-11-25
round: "Bug eater, batch 4 (branch batch-4): CODE-25"
supersedes: []
superseded-by: []
---

# D2006 · A pptx object keeps the name PowerPoint gave it, its automatic name too

**Decided 2026-11-25** by the owner, after the code review of batch 4 asked it.

PowerPoint names every shape it makes ("TextBox 3", "Title 1", "Picture 2"). Since CODE-25 the pptx import reads the
names of slides and objects (`p:cNvPr/@name`, `p:cSld/@name`) into the document's one namespace (D550), made distinct
as "Name (2)" where a file calls two things the same. The automatic names are kept as they come: they are what
PowerPoint shows in its selection pane, so a person who knows the deck finds the same names in Claudia. They are not
told apart from names a person typed.

An odp is different only because LibreOffice names no shape: it names its pages `page1`, `page2`…, and a page so named
is read as having no name (its number is not a name a person gave it).
