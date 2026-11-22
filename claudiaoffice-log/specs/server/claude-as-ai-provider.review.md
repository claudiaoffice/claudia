# Review of `claude-as-ai-provider.feature`, `claude-answers.feature` and `document-file/ai-consent.feature` (draft of 2026-11-22)

Story E7.11, architecture note `notes/e7-11-architecture.md`, mock-ups `notes/mockups/ai-provider-1..4-*.svg` and the
Penpot pages "E7.11 …". How to answer: for each question "ok" accepts my proposal; anything else replaces it. When all are
answered I move the answers into the feature files (and the decision log, with the id range you give me), remove `@draft`
and delete this file.

**Suggested order of review:** the `@core` scenarios first (see the table), then the questions below. `@extended` and
`@needs-decision` can wait for the answers.

| File | Scenarios | `@core` | `@extended` | `@needs-decision` |
|---|---|---|---|---|
| `server/claude-as-ai-provider.feature` (the administrator's page) | 24 | 10 | 14 | 0 |
| `server/claude-answers.feature` (what @ai does) | 24 | 11 | 12 | 1 (timeout reason) |
| `document-file/ai-consent.feature` (the owners' consent) | 29 | 15 | 13 | 1 (History & Chat line) |

No step code exists yet and the scenarios are `@draft`, so `tests/test_specs_are_bound.py` ignores them. Nothing in these
files was run.

## A. Questions about behaviour (proposal first)

| Q | Question | Proposal |
|---|---|---|
| 1 | Is a timeout a cause of its own on the AI page ("Anthropic did not answer within 60 seconds.") and is 60 seconds the number? The person still sees the one sentence. | Yes, its own cause; 60 seconds as the default of the AI page, not configurable now. The number is measured later against real answers, then pinned. (`@needs-decision` in `claude-answers`.) |
| 2 | When the owners change the consent, does the History & Chat panel show a muted line ("Jonas switched Claude off for this document.")? The consent is not a history step, so the line would be a chat note, not a step. | Yes, a muted chat note only, also for "allowed". It is the only way the other people see why the next answer comes from another provider. (`@needs-decision` in `ai-consent`.) |
| 3 | The administrator applies another provider or removes the key while a question to Claude is running. | The question ends with "Stopped: Claude was switched off." (same words as the owners' switch-off). Whatever Claude changed before stays. |
| 4 | "Remove" on the key while Claude is the chosen provider. | The page asks first and, on yes, falls back to Local model in the same step; the approval sentence stays recorded. No half-state with Claude chosen and no key. |
| 5 | Local model name in the "answered by" line: the model's file name or a friendly name? | The name the administrator sees on the AI page; for the stand-in "Scripted stand-in". Wording in the steps stays generic. |
| 6 | How do I test "only what the dialog says is sent" without looking into the engine? | The fake Anthropic records what it received. A second sheet ("Salaries") that the question has nothing to do with must not be in it. |
| 7 | A document that was allowed for Claude and is opened on a server where an administrator later changed the provider to another remote provider. | Not testable yet (there is only Claude). The consent names "Claude (Anthropic)", so another remote provider starts at "not allowed". Written down in the decision, no scenario. |
| 8 | German wording. | I write the German sentences as strings for the translator; the scenarios only check that they are German, not the words. |
| 9 | Do the chat scenarios run in all three apps? | One outline (`@extended`) over workbook, text and presentation; the `@core` scenarios run in the workbook only, as the other `@core` AI scenarios do. |
| 10 | The badge for a person who joins while a question is running. | She sees the same row with "Claude · remote" and the running state; nothing special. Not a scenario. |

## B. What I assumed (please correct)

1. "answered by X" appears under every answer of the ai, not only of Claude, so the chat always says who answered (decided
   2026-11-22, reading b).
2. The fake Anthropic is the only Anthropic in all scenarios. No real network, no real key.
3. "A copy" means Save as / Copy of the document file; the consent goes with it (decided: no server recorded).
4. The consent dialog is drawn by the page only; the Linux and Neutralino shells just open the page's dialog by the action `ai.preferences`.
5. "Preferences" replaces "Config" in the menu bar of all three apps; `claudia-menus.xlsx` gets the row "AI…" (Ctrl+Shift+Alt+H, macOS Cmd+Shift+Option+H) when you accept.

## C. Things I saw while reading the code, not measured

| # | What | Size |
|---|---|---|
| X1 | `AiRuntime.apply` closes the old runner while documents that are already open keep an assistant whose engine still holds it. After Apply, a question in an open document may go to a closed runner. I have **not** run this. It needs a failing scenario first; `claude-answers` has the one for "changing provider mid-question". | 2 (medium), unsure |

I will give it an id from `bugtracker.md` when you say "log" or "fix".

## D. What could not be run

Everything: the scenarios have no step code yet and the server code for the provider is not written. I only checked
that the three files are consistent with each other, with the glossary (exit record, sealed, part, document, owners'
consent, remote provider) and with the mock-ups.
