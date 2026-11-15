---
id: D550
title: "Every object, slide, sheet and chart tab has one name, unique in the document"
status: current
applies-to: all
date: 2026-11-15
round: "The dock: names, scrubbing and tags (branch dock)"
supersedes: []
superseded-by: []
---

# D550 · Every object, slide, sheet and chart tab has one name, unique in the document

**Things people point at have a name, and the names of one document are one namespace.** Objects (of every kind), slides, sheets and chart tabs share it: "Figure 1" is one thing, whatever it is. Two names are the same when they are the same cleaned and case-folded: spaces around a name go, runs of spaces become one, and `Straße` is `STRASSE`. A name is 1 to 60 characters with no control characters; `#`, umlauts and spaces are fine, because a tag in the chat is made by picking a thing, not by parsing text (D551). Named ranges, styles and number formats keep their own namespaces: they are not things a person points at on a page.

**The id is not the name.** Ids stay server-made, random and never reused; a name is for people, may change, and may be taken again once its holder is gone. Everything that points at a thing (a tag, an undo step, a command) holds the id.

**The server names new things.** A new thing gets the first free "Text box 1", "Shape 2", "Picture 1", "Chart 3", "Diagram 1", "Slide 4" in the language of the person who made it. A thing made through `add_sheet` or `add_chart` has the name the caller gave. A document from before names has things without a name (`""`); `name_unnamed` names them in one step of the history, when somebody first needs to point at them (the `#` list offers it).

**Renaming is a command.** `RenameThing(id, name)` has an exact inverse, so undo gives the old name back; it is refused with a sentence that says who has the name ("There is already a text called “Intro”"). `rename_thing` is the wire method; it refuses an empty name, which only a document from before names ever has. A rename is a change to the thing it names, so a replay follows it there (D551).

**Documents are forever.** `AddObject` goes to schema 4, `AddSheet` and `AddChart` to schema 2, and the state of a presentation to 11. Old entries read as having no names, and old `AddSheet` and `AddChart` entries carry `legacy_names`: they keep the old rule (no second sheet, no second chart of one name), so a document that has a sheet and a chart tab called "Sales" still replays. Only new commands meet the shared rule. Undoing the removal of a sheet or tab that had a clashing name puts it back as it was.

**Not built yet.** Renaming a sheet: formulas write sheet names (`Sheet1!A1`), so a new name needs the formulas rewritten and undone with it (E6.24). Until then a sheet keeps the name it was added with.

**Why.** The owner wanted every object to have a name, so that "#figure 1" in the chat can point at one thing (D551), and asked that names be unique. A shared namespace is the only way "figure 1" means one thing; per-kind namespaces would make a slide and a picture of one name ambiguous in the chat.
