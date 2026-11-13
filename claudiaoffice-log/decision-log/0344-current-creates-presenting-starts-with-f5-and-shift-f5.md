---
id: D344
title: "Presenting starts with F5 (from the start) and Shift+F5 (from this slide), and on a Mac with Ctrl+Alt+P / Ctrl+Alt+Shift+P; the browser's reload does not happen on these keys"
status: current
applies-to: creates
date: 2026-11-13
round: "Presenter mode in creates (E10.2, branch `presenter`)"
supersedes: []
superseded-by: []
---

# D344 · Presenting starts with F5 (from the start) and Shift+F5 (from this slide), and on a Mac with Ctrl+Alt+P / Ctrl+Alt+Shift+P; the browser's reload does not happen on these keys

**F5 starts the show from the first slide, Shift+F5 from the current one**, as every presentation program does, and **both actions also have a chord on a letter, Ctrl+Alt+P and Ctrl+Alt+Shift+P** (by the physical key, `code: KeyP`: Option+P types "π" on a Mac), which every system leaves alone. The page takes all four; F5 does not reload the page, also not in the notes field. Every menu entry has a key (project rule): the speaker notes toggle is Ctrl+Alt+N, the planned time of a slide Ctrl+Alt+M ("minutes"). A menu names the chord that works on the keyboard in front of the person: F5 where there is one, `Ctrl+Option+P` on a Mac. There is no separate key for "with presenter view": `P` swaps the views in the show (D345).

**Notes.** The owner's answer to question 5, 2026-11-13 ("yes, nice"); the second half is the owner's finding of the same day from Safari 27.2 on macOS: any combination with F5 is a system key there and cannot simply be reused (it reaches a page only with Fn held, and not every combination at all). In that report Ctrl+Alt+N and Ctrl+Shift+P did arrive, so Ctrl+Alt is the modifier pair a Mac keyboard can send to a page; `matches()` takes Cmd for Ctrl as everywhere in the app, but only Ctrl was seen, so only Ctrl is named. GNOME has Ctrl+Alt+T for a terminal, and main took Ctrl+Alt+D for Format ▸ Describe Object (BITV, D31x) before this work was merged, so the time chord is Ctrl+Alt+M. `lib/present-keys.ts` is the table; `tests/present-keys.test.ts` and `e2e/present.cjs` cover it. The desktop shells list the same chords as accelerators (`manifest.py`: `F5`, `<Primary><Alt>p`, …). Alt+F5 in the mock-up is a placeholder. The spike is `spikes/e10-2-presenter-window/`; its section 5 records which of F5, Shift+F5, Ctrl+F5, Alt+F5, Ctrl+Alt+N, Ctrl+Shift+P and F11 arrive.
