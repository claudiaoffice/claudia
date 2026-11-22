# Implementation notes: Claude as a provider of the `@ai` (E7.11)

Written 2026-11-22, branch `e7-11-claude-provider`, decisions D1490 to D1499 (the range reserved in `ranges.md`). The design
is `notes/e7-11-architecture.md` (read it first); this file keeps what the code does that the note does not say, the
assumptions made while building, and what could not be run.

## Where things are

| What | Where |
|---|---|
| Talking to Anthropic, its failures in words | `claudia_ai.claude` (`ClaudeModel`, `FailureReason`, `ProviderError`, `ModelTimeout`); `Answerer` in `claudia_ai.runner` |
| Which provider answers a question, the last failure, the administrator's approval | `claudia_server.ai_desk.ProviderDesk` (`decide`, `offers_claude`, `answering_now`, `may_ask_claude`, `install`) |
| One decision per question, the shared memory of the chat | `claudia_server.ai_router.AiRouter`, `ModelEngine(memory=ConversationMemory)` |
| Consent per document | `claudia_document_file.consent` (second sealed chain, format 3); `SealedDocuments.record_consent` / `consent_rows`; protocol `ai_consent`, `set_ai_consent`, `ai_consent_changed` |
| Who answered | `claudia_core.Via`, `ChatRecord.via`, `Say.via` |
| Administrator's page | `PUT /api/admin/settings/ai` in `admin_api.py`; `web/app/components/AdminAi.vue`, `web/app/lib/admin-ai.ts` |
| Document's dialog and the badge | `web/app/components/AiConsentDialog.vue`, `SidePanel.vue`; `web/app/lib/ai-provider.ts`; menu entry `config.ai` (*Preferences ▸ AI…*) from the shells' manifest |

## Things that are easy to get wrong

- **The decision is made per question, and again before every round** (D1497, CODE-78). The assistant of a document is
  made once when the document opens, so nothing that follows the owners' switch can be fixed at that moment. The router
  asks the desk; the engine stops at the next step with "Stopped: Claude was switched off." What was done before the stop
  stays (no undo).
- **Consent is a permission, not an order** (D1491). Withheld consent never produces an error: the server's own provider
  answers and the badge says so. The administrator's approval is a second, separate condition; the desk needs both.
- **No silent fallback when Claude fails** (D1492): the person reads "Claude is not available at the moment. The
  administrator can see why."; the reason (key refused, quota, timeout, unreachable) is only on the AI page. A timeout is a
  cause of its own.
- **The key is write-only.** `AiSettings.public()` never holds it; the page shows `key_set` and the last four characters
  (`key_tail`). A key given by the operator (`ANTHROPIC_API_KEY` or `--anthropic-key-file`) is shown as such and cannot be removed on the page.
- **The memory of the chat is shared** (D1498): the earlier chat goes with the next question whichever provider answered
  before, so a switch does not make the AI forget what was said.
- **A copy of a document carries its consent**; the file's format is 3. A file of format 2 opens as before and has no
  consent, which means off. An older server refuses format 3 as "newer".
- **Health is kept in memory** (D1496), not in the state folder: a restart forgets the last failure.
- **Web extractor:** a sentence the server sends and the page shows must appear as a literal `t('…')`; see `NOTES` in
  `ai-provider.ts`, which maps the server's note sentences to literals.

## Assumptions (to be confirmed or changed by the owner)

1. The owner's go-ahead "Start coding" accepted items 3–9 of §7 of the architecture note.
2. A local model is kept loaded alongside Claude, so the fallback of D1491 is instant.
3. Action ids stay `config.*` although the menu is *Preferences* now (D1494); only labels changed.
4. The chord of *AI…* is **Ctrl+Shift+Alt+E**, provisional: Ctrl+Shift+Alt+H, the first choice, is `view.present-here`.
5. The sentences of the AI in the stored chat stay English; the page translates them when it draws them.
6. One owner per document exists today; the consent texts say "owners" (D1499, **undecided**).

## What could not be run

- **The real Anthropic API.** Everything ran against `FakeAnthropic` (`claudia_ai.testing`). The owner does one check with
  a real key before the release.
- **Firefox**, and the **Windows and macOS shells** (neutralino): the menu JSON is generated and tested, not started.
- **Scenarios left without steps** (they skip with their words): the server restart, the settings file edited by hand,
  an unreachable host and an unknown model (the fake cannot be those), and the two-owner scenarios (no second owner).
