# E7.11 architecture: Claude as an AI provider

*Draft for the owner's review, 2026-11-22. Nothing here is built. The mocks are agreed (`ai-provider-1` … `-4`, and as
pages of `penpot/claudia.penpot`). The decisions behind this note are D8, D32, D154, D261, D262, D264 and D266; the new
decisions it needs are in §7. Story: E7.11. The branch name and the decision-id range are the next step, not this one.*

Three diagrams, in `notes/mockups/` (SVG with a PNG next to each; same conventions as the E1 diagrams: solid outline =
exists today, dashed = new in E7.11, a bold coloured line in a solid box = a new or changed member of an existing class):

| Diagram | Shows |
|---|---|
| `e7-11-architecture-01-provider` | `ClaudeModel` next to `OpenVinoModel`; `ProviderError` and `FailureReason`; in the server the settings, `AiRuntime`, `ProviderDesk`, `ProviderHealth`, `Decision` |
| `e7-11-architecture-02-one-question` | `Assistant` → `AiRouter` → `ModelEngine` → `GatedRunner`; `ConversationMemory`; `Say.via` and `ChatRecord.via` |
| `e7-11-architecture-03-consent-and-clients` | the consent in the sealed document (`ConsentRecord`, `AiConsent`, the two protocol methods, the audience rule), the admin API, the web components, the shells' manifest and the generated menus |

## 1. The one rule that decides where things go

**A model answers; the server decides who may be asked; the document says whether its owners agreed; the page draws it.**
Each of the four lives in the place that already owns that kind of thing:

| Concern | Lives in | Why there |
|---|---|---|
| How to talk to a model, and how that can fail | `claudia_ai` | It already holds `LanguageModel`, `ModelRunner`, `ModelError`. It knows no document and no server setting, and must stay so. |
| Which provider is chosen, whether the administrator approved, what went wrong last | `claudia_server`, one new `ProviderDesk` | The server settings and `AiRuntime` are already the administrator's side. |
| Whether *this document's owners* allowed Claude | the sealed document | D264: the administrator must not be able to give or fake it. Only something sealed with the document's keys has that property. |
| What the person sees (badge, dialog, menu entry) | the web page; the shells add one menu entry | Every client already shows the same page (`clients/contract`). |

## 2. What I checked in the code

Evidence labels as in `bugtracker.md`: **read** (from reading code). Nothing below was measured: I could not run the server
stack in this workspace.

- **read** · The seam for a second model already exists. `Agent.respond(model, request, …)` takes any `LanguageModel`
  (`generate(messages, max_new_tokens, stop) -> str`); the prompt and the fenced `commands` convention are the same for every
  model. Claude needs a new `LanguageModel`, not a new agent.
- **read** · `ModelRunner` is one worker thread per model, one question at a time. Putting `ClaudeModel` behind a second
  runner gives the thin first slice ("one question at a time") with no change to `ModelEngine`'s loop.
- **read** · The assistant of a document is made **once, when the document is opened**, by the factory that `AiRuntime.apply`
  installs in `hub.assistant`; `ModelEngine` holds its runner for good. A choice that must follow *the owners' switch* and *a
  provider that changes* cannot be fixed at that moment. This is why the router (§4.3) decides per question.
- **read, possible bug (not measured)** · `AiRuntime.apply` closes the old runner, but a document that was opened earlier keeps
  an assistant whose `ModelEngine` still points at it, and a closed runner raises "the server is shutting down". If that is so, a
  document that was open when an administrator changed the model cannot be answered by the AI until it is closed and reopened.
  The router removes the cause (engines ask the desk for the current runner at the time of the question). I would add a
  failing scenario for it first, as the process requires, and report it with a size once measured.
- **read** · Per-document owner-only changes already exist (`set_role`, `propose_owner`: `ctx.account.role != "owner"`), and
  the document file already has a sealed, tamper-evident list that is not part of the command log: the **exit record** (glossary;
  the code calls it the audit chain: E2.9, D1271). It is the list of what *left* the document, written with `ctx.record_audit`,
  sealed with the history key and covered by the file's head. The administrator holds no document key.
- **read** · Owners and editors hold all three part keys; a viewer holds the content key only (`ROLE_PARTS`). Only owners and
  editors can chat, so whoever asks `@ai` holds every key.
- **read** · The administrator's settings live in `settings.json`, written private (`write_private`) like the access secret;
  an operator's command-line value wins over a saved one (D154), resolved once in `cli.py`.
- **read** · The shells draw native menus from `clients/linux/.../manifest.py` (one action list per app);
  `clients/neutralino/tools/generate_menu.py` generates `menu.<app>.json` from it, and `--check` runs in CI. A new action id is an
  additive change of the contract. The shells draw **no dialogs**: the page does, so one dialog serves all three apps and all
  three clients.
- **read** · `claudia-menus.xlsx` is where entries and keys are agreed centrally; it does not have the AI… row yet.

## 3. Where each piece goes, and why

### 3.1 The provider (diagram 1)

- `claudia_ai.ClaudeModel(LanguageModel)`. Posts to `/v1/messages`; system messages go in `system`, the rest in `messages`
  (consecutive messages of one role are merged: the API wants them to alternate). It reads the answer as a **stream** internally,
  so that `stop` (timeout, shutdown, switch-off) is honoured while the request is running; nothing is streamed to the person (out
  of scope). HTTP goes through a one-method seam, using the standard library: no new dependency (to confirm, §7).
- `LanguageModel.remote: bool = False` (`True` for Claude). It is how the server knows a model sends content out, instead of
  asking the provider's name.
- `ProviderError(ModelError)` with `reason: FailureReason` and `detail`. `ModelError.message` is "meant for the person using the
  assistant", so the person's sentence stays there and the administrator's reason goes beside it (two audiences, two fields).
  `FailureReason.admin_sentence` holds the six sentences of mock 2 D, so they are written once, in one place, and translated once.
- **Not** in `ModelRunner`: it would learn what a provider is. It stays as it is; the `Answerer` protocol (just
  `answer(request) -> Turn`) is what `ModelEngine` is typed on, so a runner and the gate below are interchangeable.

### 3.2 Settings, the key, the desk

- `AiSettings` gains `provider` (`stand-in | local | claude`) and `claude: ClaudeSettings(model, key, confirmed)`, nested like
  `typeset` and `render`. `max_tokens` and `timeout` stay shared (mock 1). An old `settings.json` loads unchanged: with no
  `provider`, it means `local` when there is a `model_dir`, else `stand-in`.
- The **key** is stored in `settings.json` (private file, like the access secret) and **never returned**: `to_public_dict` gives
  `key_tail`, `GET` the same. The operator can give it as `ANTHROPIC_API_KEY` or `--anthropic-key-file`, which wins over the saved
  one (D154). It travels only in a request header from the server to Anthropic; it is never logged.
- `confirmed` is the administrator's sentence with `Changed(by, at)` (the type `ServerSettings.changed` already uses).
- `ProviderDesk` is the one place that knows both providers: the runners, the approval, and `ProviderHealth`. It answers two
  questions, `decide(consent) -> Decision` (who answers *this document* now, and why not Claude) and `answering_now()` (what the
  settings page and the badge say). `AiRuntime` stays the admin API's facade (`enabled`, `apply`) and owns the desk; **`apply` asks
  Claude one test question first** and refuses with the reason if it fails, so a wrong key is found where the administrator is
  looking (mock 1, note 5). The hub's assistant factories are installed once and point at the desk, not at a runner.
- `ProviderHealth` keeps the last failure (provider, reason, time) and clears it on the next answer from that provider. **In
  memory**: a restart forgets it (assumption, §7).
- `--anthropic-base-url` exists for the fake and for tests, **hidden, operator-only, never a field of the page**: a page field
  would let an administrator send the key to any address.

### 3.3 One question (diagram 2)

- `Assistant` stays provider-agnostic: its engine is already the seam. `AiRouter` is an `AsyncEngine`, so `Assistant` changes in one
  place only: `Say` carries an optional `via`, and `_say` passes it to `post_chat`.
- `AiRouter.plan_async(task)`: ask the desk to `decide` with this document's `AiConsent`; hand the task to the stand-in, the local
  `ModelEngine` or the remote one; turn the outcome into a `Say` with its `Via`. **It never falls back**: a failure of Claude is the
  one sentence for the asker and a note in the health, not a silent answer from another model (agreed: Q11).
- The two `ModelEngine`s of a document share one `ConversationMemory` (extracted from `ModelEngine`, no new behaviour). That makes
  "the earlier chat between the person and the ai", which the consent dialog says is sent, true whichever model gave the earlier
  answers.
- `GatedRunner` wraps the remote runner and checks `still_allowed()` before **every round** of the loop. Consent withdrawn or the
  provider switched off → `Withdrawn`, the router says "Stopped: Claude was switched off." and nothing more is sent. This is where
  "before its next round" (agreed) is enforced, because rounds are the only place the loop calls out.

### 3.4 The owners' consent (diagram 3)

*Revised after your answers of 2026-11-22.* In my first draft I proposed to put the consent into the exit record and called it
"the sealed audit chain", which is the code's word, not the glossary's. The glossary says the exit record is "the sealed list of
everything that **left** a document" and that "nothing removes an entry"; a consent is not something that left, and it can be
withdrawn. So the exit record stays exactly as it is, and the consent gets a list of its own.

Where it can live:

| Option | Administrator can forge it? | Viewers can read it | Cost |
|---|---|---|---|
| **A. A second sealed list in the document file** (`ConsentRecord`), beside the exit record, sealed with the *content* key | No: no key | Yes, through the server | A new file entry: the file schema is raised (your answer) |
| B. A command in the document's own log | No | Yes | Needs a per-app model attribute; computes has none; undo and history interplay |
| C. A file beside the documents (server state) | **Yes** | n/a | Defeats D264's purpose |
| D. The plain manifest | **Yes** (plain) | Yes | Same |
| E. The exit record with two new kinds | No | No (history key) | Changes what the glossary says the exit record is |

Why A, and why the content key: the record is not history or chat, and a viewer must be able to see whether Claude is allowed
(mock 3, screen 3). Sealing it with the content key also removes a risk I had listed: a viewer who opens a document first leaves
the server with a key it can use. It reuses the block writer and the head of the exit record's mechanism; only the list is new.

An honest limit: owners **and editors** hold all part keys, so "only owners may change it" is enforced by the server's method,
not by cryptography. What the seal guarantees is what D264 is for: the **administrator** cannot give the owners' consent.

- `ConsentRecord(provider, allowed, who, when)`. `AiConsent` is a plain value folded from the list when the document is hosted:
  the latest record per provider wins, no record means off. A document with no such list (a server that keeps none) is always
  **off**: failing safe.
- `HostedDocument.ai_consent` holds it live, so the gate and the router read the current state, not the state at opening.
- Wire: `ai_consent()` (any role, content level) returns `{allowed, by, at, answering, owners}`; `set_ai_consent(allowed)` is
  owners only, writes the record, publishes `ai_consent_changed`. The event is classified `CONTENT` in `audience.EVENT_RULES`
  so viewers see it; the test that fails for an unclassified event keeps us honest.
- **A copy carries its consent** (your answer: no recording which server gave it). The owners agreed to "Claude (Anthropic)" for
  this document; on another server with Claude set up, that agreement still holds, and the dialog there says who gave it and when.

### 3.5 Provenance in the chat

The badge and "answered by …" line need the chat to say who answered. `ChatRecord` gets an optional `via`
(`Via(provider, label, remote, note)`). Optional and absent when empty, so existing files and clients load unchanged. The
alternative, carrying it in the text, would make the history unreadable for a machine and impossible to translate.

### 3.6 Clients

- **Web:** `AdminAiModel.vue` becomes `AdminAi.vue` (provider switch, the three panels, answering-now and last error);
  `AiConsentDialog.vue` is new; `document-menus.ts`: `configMenu` becomes `preferencesMenu`, label "Preferences", entry
  "AI…" (`ai.preferences`, Ctrl+Shift+Alt+E); `SidePanel.vue` shows the badge and the line under the bubble.
- **Shells:** `manifest.py` gets the action and the new label; `generate_menu.py` regenerates the Neutralino menus; the contract
  README and the Linux `CHANGELOG` get a line. The macOS app-menu placement stays open points 14/15 of the matrix.
- **i18n:** every string through the catalogues; the sentence for the asker is one string whose only variable is the
  provider's name.
- **Rename:** "Config" → "Preferences" touches the three workspaces' menu code, the manifest, the generated menus, the Neutralino
  menu tests (`macos-menu.test.ts`), the help texts and `claudia-menus.xlsx`. It is mechanical but wide; I would make it its own
  commit so it can be read apart from the feature.

### 3.7 The test double

`claudia_ai.testing.FakeAnthropic`: a local server that speaks the Messages API including the stream, and each failure
(401, 402, 404, 429, 529, and no network). It is what the unit tests, the E2E scenarios and the "use it before delivery" run talk to,
through `--anthropic-base-url`. The real API is not reachable from the workspace or CI: the owner makes **one real-key check**,
and the patch says "real API not run".

## 4. One question, step by step

1. `@ai …` arrives; `Assistant` queues it as today.
2. `AiRouter` asks `desk.decide(consent)`:

| Chosen provider | Administrator approved | Owners allowed | Answers | Chat says under the answer |
|---|---|---|---|---|
| Claude | yes | yes | Claude | `answered by Claude (remote)` |
| Claude | no | any | local model, else stand-in | `answered by Qwen2.5-7B · this server` and "Claude is not allowed in this document…" |
| Claude | yes | no | local model, else stand-in | the same |
| local / stand-in | n/a | n/a | that provider | its own name, no remote badge |

3. The engine runs its loop. Each round goes through the gate; a switch-off ends it with `Withdrawn`.
4. A `ProviderError` becomes "Claude is not available at the moment. The administrator can see why." and the desk notes the
   reason; the next success clears it.
5. The `Say` goes out with its `Via`.

## 5. What I would not do

- **Not** put the choice in the hub factory (fixed at opening: cannot follow consent or a changed provider).
- **Not** teach `ModelRunner` about providers or documents; **not** teach the loop about providers.
- **Not** store consent in server state or the manifest (the administrator could forge it).
- **Not** let the page set the base URL.
- **Not** fall back silently to the local model when Claude fails.
- **Not** use the native tool-use API or concurrency: E7.3 a/b. This slice keeps today's prompt and `commands` block, so Claude and
  the local model behave the same way.

## 6. Touch list

| Package or place | Change | Size |
|---|---|---|
| `claudia_ai` | `ClaudeModel`, `ProviderError`, `FailureReason`, `Answerer`, `remote`, `FakeAnthropic` | M |
| `claudia_core` | `Via`, `ChatRecord.via` (optional) | S |
| `claudia_document_file` | the consent list (`ConsentRecord`), file schema raised | M |
| `claudia_server` | `ClaudeSettings`, `ProviderDesk`, `ProviderHealth`, `Decision`, `AiRouter`, `GatedRunner`, `ConversationMemory`, `AiConsent`, two protocol methods, audience rule, admin API, `cli.py` | L |
| `web` | `AdminAi`, `AiConsentDialog`, menus, `SidePanel` | M |
| `clients` | manifest, generated menus, contract note, rename in tests | S |
| rename "Config" → "Preferences" | all of the above, mechanical | M |
| `po/`, `claudia-menus.xlsx`, glossary, help, privacy text (D264 asks for it) | text | S |

## 7. Decisions for you

Each has my recommendation; "yes" accepts it.

1. ~~Consent store.~~ **Settled with your answers:** a second sealed list in the document file (§3.4 A), not the exit record. *Please confirm that this replaces my earlier proposal.*
2. ~~A copy carries its consent?~~ **Decided:** no recording of which server gave it. **Open, one question:** on a server where Claude
   is not set up, what exactly happens when someone asks `@ai` in a document whose owners allowed Claude? See the end of this note.
3. **`ChatRecord.via`.** Optional field in the chat record (§3.5). *Recommended.*
4. **Stream inside `ClaudeModel`.** So `stop` is honoured; nothing visible changes. *Recommended.*
5. **Health in memory.** A restart forgets the last error. *Recommended* (the page shows what is true now).
6. **Shared `ConversationMemory`.** *Recommended.*
7. **Nothing recorded per remote question for now.** The document could also keep "a question went to Claude, asked by X, at T" for
   the owners to read (it would belong to the exit record, since it is something that left). It is new product and a privacy
   statement, so not in this slice; I would log it in the backlog. *Recommended.*
8. **Test before apply inside `PUT /settings/ai`.** A refused key never becomes the saved setting. *Recommended.*
9. **No new dependency** for HTTP (standard library behind a seam). *Recommended.*

## 8. Not verified, and risks

- **Older servers.** Settled: the new list raises the file's schema. An older server then refuses such a file in its usual way
  instead of failing in the middle of it; the implementation has to check what that refusal says.
- **The possible bug of §2** (closed runner after a settings change): to be measured with a failing scenario.
- **Anthropic's API:** the request shape, the stream format and the error mapping come from the documentation, not from a
  run. The fake encodes my reading; the real-key check is the safety net.
- **`stop` and a hung connection.** Streaming bounds it by the read timeout of each chunk; the total is bounded by the runner's
  timeout. Worth one scenario with a stalled fake.

## 9. Next

On your word: the Gherkin scenarios (`@core`: ask Claude and read the badge; not allowed here answers locally; Claude fails;
switch-off stops a running question; the consent is owner-only; administrator approval alone is not enough; `@extended`: key
write-only, test refuses a bad key, the six failure sentences, a copy on another server), then the branch name and a decision-id
range (the new decisions above plus the Preferences rename and the D264 screen reference).

## 10. One question left

You said: *if the target server has no Claude setting open, the users get an error response in the chat.* I read it as:

- the document says "Claude allowed" (it came from another server), but this server has no Claude provider set up, **and**
- somebody asks `@ai` → the asker gets an error line in the chat, not a quiet answer from the local model.

Two readings give different behaviour, and I do not want to guess:

**(a) Error only when the document and the server disagree about Claude.** The owners' consent names Claude, but this server's
provider is the local model or the stand-in: the question is not answered, and the chat says so. This would also happen at home
when an administrator switches from Claude to the local model while documents still carry the owners' consent.

**(b) No error; the server's provider answers, as in mock 3, screen 4.** A consent for Claude simply does nothing where Claude is
not the provider; the local model answers and the chat says who answered.

I recommend **(b)**: the consent is a permission, not a request. Making it an obligation would stop `@ai` in every document the
moment an administrator moves away from Claude, which is the opposite of what the administrator chose. Error lines stay for what
fails when Claude *is* the chosen provider (the one sentence of your Q11). If you meant (a), I'll write that into the scenarios.

Agreed (b), the owner