# Implementation note: one owner in the consent texts (D1499)

Written 2026-11-23, branch `d1499-one-owner` (from `main`). No new decision: D1499 (option b) covers it.

## What changed

- Eight English source strings say "the owner" where they said "the owners": the note under an answer
  (`ai_desk.NOTE_NOT_ALLOWED`), the two refusals in `protocol._set_ai_consent`, and in the web app the AI page of the
  server settings (`AdminAi.vue`) and the dialog "AI in this document" (`AiConsentDialog.vue`, `ai-provider.ts`). The
  dialog's placeholder is `{owner}` now (was `{owners}`); `DialogModel.ownersLine` is `ownerLine`.
- German: "die Eigentümerin oder der Eigentümer" (singular, as agreed). `po/claudia.pot`, `po/de.po`, `po/xx.po`, both
  compiled `.mo` and `web/public/i18n/de.json` and `xx.json` were regenerated with the scripts.
- Comments and docstrings about the consent say "the owner"; `docs/server.md` too.
- The three feature files (`ai-consent`, `claude-answers`, `claude-as-ai-provider`) and the mockup texts
  (`ai-provider-1`, `-2`, `-3`, `-4`) say the same. The scenarios that needed a second owner now use one owner plus an
  editor who is refused ("Only the owner can change this: Anna."), or Anna as the one who switches Claude off.
- The E2E step text "the owner of each document must also allow Claude there" follows.

## What did not change

- The wire format: `ai_consent` still answers `owners` (a list), and the dialog still formats a list of names, so a
  later story for co-owners needs no protocol change.
- Strings about owners that are not about Claude's consent (export of history and chat, redaction, ownership handover):
  they are about roles, not consent.

## Assumptions

1. "The owner" in the dialog line is followed by the name from the list the server sends; with one owner that is one name.
2. The glossary term is **Owner's consent** now ("until the owner turns it on"), approved by the owner 2026-11-23.
3. The penpot page is still called "E7.11 Owners' consent"; `penpot/generator/src/aiprovider.mjs` and `penpot/claudia.penpot` still show the old plural; the generator was not
   run here.

## What could not be run

- The full `@core` E2E run (about 20 minutes). Run here: all Claude spec files with Chromium (no failures; the scenario
  "An editor sees what is allowed and cannot change it" runs now instead of skipping). Scenarios whose steps do not
  exist yet still skip with their words, as before.
- A check by a German speaker of the new wording.
