---
id: composes.asking-ai-to-review
title: How do I ask the AI to review my text?
apps: composes
language: en
tags: ai, assistant, review, suggestions, chat
explains: @ai, suggestions
---
Every document can have one AI user, shown in the toolbox's chat like any other person. Type `@ai` followed by
what you want, the same way you would write `@maria` to get a colleague's attention.

What it does with what it finds depends on the switch above the History & Chat tab, which you set for yourself in
each document. In *suggest* mode it only suggests: each suggestion is shown inline where it applies; accept it to make
the change, or leave it and it stays open for later. In *act* mode it makes the fixes itself, and every one is a step
in the history that undo takes back.

## What it understands

- `@ai review this text` (or `check`, `proofread`, `edit`, `improve`, `polish`, `tighten`, `fix`, `look`) reads the
  whole document and suggests fixes for spelling, wordy phrases, "very", doubled spaces, and flags sentences that
  have grown very long.
- `@ai check this paragraph` (or `here`, or mention "the cursor") narrows the same review to wherever your own
  cursor currently is, instead of the whole document.
- `@ai help` (or `hi`, `hello`, `hey`, or asking what it can do) answers with a short reminder of what it
  understands.
- Anything else gets an honest "I did not understand that" rather than a guess.

## Example

Write a paragraph with a typo and a long, wandering sentence, then send `@ai review this text`. In suggest mode the
assistant answers in chat with how many suggestions it made, and each one appears attached to the exact words it is
about — a strikethrough-and-replacement for a wording fix, or a remark alone for something like a long sentence,
which it cannot fix for you. Nothing in your document changes until you accept a suggestion. In act mode the typo is
fixed at once, and the long sentence still gets a remark.

## Why you choose

Claudia's AI user edits through the very same methods a person does, so it can never do something a person
couldn't also undo. Whether you want its read of the text as a second opinion first or as an edit you can take back
is your choice, the same in the text, the sheet and the slides.
