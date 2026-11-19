---
id: D1232
title: "Turning an object and writing in a text box or shape are the same in all three apps (proposal, tests first)"
status: undecided
applies-to: all
date: 2026-11-19
round: "Object interaction in the three apps (branch object-interaction)"
supersedes: []
superseded-by: []
---

# D1232 · Turning an object and writing in a text box or shape are the same in all three apps

**Proposal. The server's work is shared and already there; what is missing is the same few entries in the clients.** The tests
come first (`web/e2e/objects.cjs` with `D1232=1`, `packages/claudia-server/tests/test_server_object_words_and_turns.py`,
`xfail(strict)`), and are reviewed before any of this is built.

**Turning.**
- *Server.* `rotate_object` is one implementation for all three apps (`object_methods.py`, `turn_command` in the kernel). It
  refuses a chart. **It also turns a table, which the contract (D1224) says has no rotation: the server refuses it too**
  (`can_turn` is false for the kind `table`, with a sentence).
- *Menus.* **Format ▸ Rotate ▸ Rotate Right 90° (Ctrl+Alt+.), Rotate Left 90° (Ctrl+Alt+,), Rotate By… (Ctrl+Shift+Alt+Z) in
  composes and computes as in creates** (D1024 says "one shape wherever an app turns objects"; only creates has it). The
  entries act on the selected object, are off with nothing selected, for a chart and in a read-only document; the context
  menu's *Rotate by…* then shows the key as it does in creates. The desktop menus come from the same manifest.
- Neither the turn handle nor the menu is new: the gestures of D1221 and the popover of D1024 are shared already.

**Writing in a box.** A paragraph of a text and the words of a text box are one entity (D181); composes' model already types
into the words of its floating objects (`TypingHost`). **`set_text` and `write_words` move from `creates.py` to
`shape_methods` (with `add_object`, where both apps get them), and composes' text boxes and shapes are written in with the
editor creates uses (`ParagraphEditor.vue`):** Edit text in the object's menu, Enter or F2 on the selected object, a double
press; Enter keeps the words, Shift+Enter breaks the line, Esc leaves them; one history entry "Edit text", and the words
that stay keep their writer. Computes has no text boxes or shapes; a container is written in with its own editor in all three.

**Not in this decision.** The key of *Delete* (a selected object or table) in composes and computes: logged as UX-47.

**State 2026-11-19.** Writing in a box is built (patch 9: server, editor, E2E step, specs in `specs/object-words.md`); turning
(table refused, Format ▸ Rotate in composes and computes) follows in the next patch.

**Notes.** Applies D181, D1024, D1221, D1224, D1225.
