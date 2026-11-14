---
id: D448
title: "Every password field has an eye that shows what was typed; a person can change their own password for a document, nobody else's"
status: current
applies-to: all
date: 2026-11-14
round: "One server for all three apps (branch one-server)"
supersedes: []
superseded-by: []
---

# D448 · Every password field has an eye that shows what was typed; a person can change their own password for a document, nobody else's

**All twelve password fields of the web client (the front page, "I forgot my password", Open a File…, Share…,
Change Password…, the four confirmations of File ▸ Manage, and the server administration) are one component,
`PasswordInput.vue`: an eye at the right end shows and hides what was typed. It is a toggle button of its own
("Show password", `aria-pressed`), never submits the form, and every field starts hidden, Share's password for a
colleague too. File ▸ Manage ▸ Change Password… (Ctrl+Alt+Shift+W, every role) changes the person's own password
for the document after they give their current one; there is no "repeat the new password", because the eye shows it.
Nobody can set another person's password: somebody who forgot theirs gets back in with the recovery key.**

**Notes.** Owner, 2026-11-14, on sheet 12. A password does not encrypt the document: it unlocks the person's own key
slot, which holds the document's keys. Changing it seals the same keys again under the new password
(`claudia_container.change_password`, which existed but was never offered); nothing is re-encrypted and the others keep
their passwords. The protocol method is `change_password`. An owner who mistyped a colleague's password cannot
invite the same name again (nobody can be removed yet): the recovery key ("I forgot my password", with the colleague's
name) gives that person a new one, or the colleague is invited under another name.
