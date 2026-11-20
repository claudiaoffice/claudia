---
id: D1284
title: "`change_role` and `remove_person` are the wire methods; owners are neither lowered nor removed"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round, slice C (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1284 · `change_role` and `remove_person` are the wire methods; owners are neither lowered nor removed

**Made while building slice C; the owner has not seen it yet (proposal, built).**

- `set_role` was already a wire method (it gives a style role another colour); the people method is `change_role {name,
  role}` with `role` editor or viewer. `remove_person {name}`. Owners only.
- An owner is refused with a `command_error` sentence: ownership is handed over (`propose_owner`), not taken away.
- The person's open windows get the new role at once (`role_changed`), or are closed (`person_removed`): the hub applies
  the role before the event is delivered, and a removed person's requests are answered `forbidden`.
