# Implementation note: skills and persona per app (E7.2, D1560–D1563, D1567), with CODE-80 to CODE-82

Written 2026-11-24, branch `e7-2-skills-and-persona`. The design is in `notes/e7-2-architecture.md`; the decisions are
D1560–D1568 (D1564–D1566 and D1568 were written with CODE-80 to CODE-82).

## What changed

- **The files.** `claudia_computes/ai/`, `claudia_composes/ai/` and `claudia_creates/ai/` each hold `persona.md` (about 1,100
  characters: the shared lines, then `## In this app`) and `skills.md` (computes 3 recipes, composes 5, creates 5). Together
  they are 2,400 to 3,100 characters per app, the cap is 6,000.
- **The loader.** `claudia_server/ai_guidance.py`: `load_guidance(model_cls)` finds the files by the top package of the model
  class (`importlib.resources`), `parse_recipes` reads `## title`, `Uses: a, b` and the text, `Guidance.skills_for(offered)` keeps
  the recipes whose requests are all offered. A missing folder is no guidance; a recipe without `Uses:` raises.
- **The plumbing.** `ModelParts.guidance` (from `apps._model_parts`) goes into `ModelEngine(…, guidance=…)` for the routed and the
  plain model assistant; `plan_async` puts `persona` and `skills` into the `Request`, the skills for the requests this asker is
  offered (`task.writes`: an editor in suggest mode is offered fewer).
- **The prompt.** `claudia_ai.Agent.messages`: identity, persona, context, how to ask, requests that look, requests that change
  (or "you cannot change this document"), recipes. Empty parts are left out. `SYSTEM_PROMPT` became `IDENTITY` (only who the AI
  is); "answer briefly and in the language you are spoken to" moved into the persona.
- **The help.** `help_search` and `help_topic` are in `look_methods` of the three lenses. `lens.show_help` shows them as plain text
  (not fenced: the product's own words), a topic cut at 4,000 characters.
- **The AI page.** The field "Max answer length (tokens)" edits the chosen provider's own value (Claude's `claude.max_tokens`,
  the local model's `max_tokens` for the local model and the stand-in); under it "About N words" (tokens × 0.75, to the nearest
  ten), linked with `aria-describedby`. Apply waits for a whole number of at least 1. German: "Etwa {words} Wörter".
- **Versions.** claudia-ai 0.5.0 (`Request.persona`, `Request.skills`), claudia-server 0.44.0; both changelogs, the API
  snapshots, the docs entries.

## Tests

- `test_ai_guidance.py`: the parsing; each app ships both files; the size cap; every recipe names requests the app offers a model
  to change; every example is a request the recipe names, with JSON that parses, with exactly the parameters the request takes and
  all it needs; **the server carries out every example** on a document that holds what it names; no app mentions another app's
  requests; the shared persona lines are identical; the persona names `help_search`, `help_topic` and "Never invent".
- `test_server_ai_prompt.py`: through the real `model_assistant_for` and a scripted model, what the model is sent: persona in every
  app, every recipe for an owner who acts, none for somebody who may only look, the twin recipe in suggest mode, the help among the
  looks for both askers, the help flow (search, topic, answer, no data fence), a 300-word story and a text box carried out when the
  model writes the request in the form it was shown.
- `web/tests/admin-ai.test.ts`: the length of the chosen provider, setting it, the words, validity, the payload.

## Assumptions

1. A recipe is shown only when **all** its requests are offered; an owner who acts is offered `suggest_words` too, so she also gets
   "Propose a rewrite" (harmless, and useful when she asks the ai to propose instead of changing).
2. "Somebody who may only look" is an editor in suggest mode in computes and creates (nothing can be proposed there yet, so she is
   offered no change). A viewer cannot write in the chat at all ("chat needs the editor role"), so the feature scenarios about a
   viewer were rewritten that way.
3. The help is trusted text and is not fenced (D1563). It is read in English: the assistant's connection has the default language,
   and the persona has the model answer in the asker's language.
4. The lens `EXAMPLE` constants (one request as an example in the context) stay. They are the only example in suggest mode of the
   app where no recipe applies, and they cost a line. Removing them is a later step if they turn out to be duplication.
5. Claude's `max_tokens` is not capped by the server; Anthropic refuses a value above the model's limit and the administrator's
   test question on Apply shows the reason.
6. The words hint rounds to the nearest ten: 4096 tokens read "About 3070 words".

## What could not be run

- **The real Claude and the local 7B model.** Whether they now use the commands form, look in the help first and stop copying the
  examples is what the owner's real-key test shows; here a scripted model and the fake Anthropic only show that the right text
  reaches the model.
- **First-token time of the local model** with the longer prompt (about 1,000 more tokens per question): not measured here (D1562).
- **The full `@core` E2E run (about 20 minutes).** See the done report for what ran.

## Follow-ups (not done)

- Pass the asker's language to the ai's help requests, if answers from the English help turn out worse than from the German.
- A German speaker's check of "Etwa {words} Wörter".
- Native tool calling with Anthropic's API (story B), a persona per document, an administrator override (D1560 says "not yet").
