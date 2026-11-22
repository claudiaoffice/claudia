---
id: D1454
title: "Two checks of the specs read the wire, because no person can see them: nothing sent, and what a document no longer keeps"
status: current
applies-to: all
date: 2026-11-22
round: "E2E guard follow-up (E11.8, branch e2e-guard)"
supersedes: []
superseded-by: []
---

# D1454 · Two checks of the specs read the wire

**Made while writing the step code of `specs/objects/the-same-in-all-three-apps.feature`, 2026-11-22; for the owner to
veto.**

Step code works on what a person sees and does (specs/README.md). Two lines of that spec say what no person can see:

- *"…and nothing is sent"* (a viewer, D1432): the step records the requests the page sends and fails on any that the
  server's own protocol description marks as a change (`"write": true` in `/api/<app>/protocol`). Checked to fail for
  the right reason: with Vera as an editor, it names `move_object`, `resize_object`, `rotate_object`, `remove_object`.
- *"…and the document no longer keeps what it showed"* (D1431): the step reads the server's event about what the
  object showed (an image, a shape, a chart, a container); after undo it must forget it (`asset` or `definition`
  `null`), after redo bring back the same.

Everything else in those scenarios is read from the page. `conftest.Person` keeps the methods its page sent
(`sent`) and the events it received (`events`), so later step code can use the same two checks.
