---
id: D554
title: "A paragraph is a thing: headings, list items and paragraphs can be named and tagged, named when first pointed at"
status: current
applies-to: composes
date: 2026-11-15
round: "QA of 2026-11-15"
supersedes: []
superseded-by: []
---

# D554 · A paragraph is a thing

**Every paragraph of a text can have a name in the document's one namespace (D550), so that a tag in the chat can
point at it, as named ranges became things in computes (D552). Its kind is what it is: `heading` (its style is the
title or a heading, or is based on one), `item` (of a list) or `paragraph`. A paragraph is named when somebody first
points at it — `name_thing` over the wire: a heading by its own words when nothing else has them, anything else by what
it is ("Paragraph 1", in the language of the one who points), one step in the history — and renamed with
`rename_thing` like any thing. `#` in the chat offers the named paragraphs, every heading and the paragraph with the
caret; Edit ▸ Reference in Chat writes a tag for the paragraph with the caret. A tag to a paragraph scrolls the text to
it and outlines it.**

**Notes.** Owner, 2026-11-15: "in composes, lines that are marked as headers, lists, and paragraphs are not registered
as taggable in the chat. They should have a name and be taggable." Not named when made: a text has hundreds of
paragraphs, a name for each would be noise in every list, and `name_unnamed` (which names everything a document from
before names holds) leaves paragraphs out for the same reason. The name is kept by the paragraph's id in the text's
state (`TextModel.block_names`, state schema 11), not in the paragraph: ids are never given twice, so the name follows
the paragraph through every edit, a paragraph joined away holds no name while it is gone, and undo of the join gives it
back. A split leaves the name with the paragraph that keeps the id (the first part). Lists themselves (the `ListDef`)
and styles are not things: a list is reached through its items, and a style has a name of its own outside the
namespace. Not built: names of paragraphs in docx and odt (bookmarks would carry them), and a way back after a tag took
the view to a paragraph (the caret stays where it was).
