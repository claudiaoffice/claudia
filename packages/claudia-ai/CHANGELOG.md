# Changelog of claudia-ai

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

## [0.5.0] - 2026-11-24

The AI is given who it is, how it behaves in an app and how to do the app's usual tasks (E7.2).

### Added
- `Request.persona` and `Request.skills`: how the AI behaves in the app and the recipes for what it may do there
  (D1560, D1561). `Agent.messages` puts them in the system message: identity, persona, context, how to ask, the requests,
  the recipes. Both default to empty, so a caller that gives none is unchanged.

### Changed
- "Answer briefly and in the language you are spoken to" is no longer in the identity line: it is the persona's. A caller that
  gives no persona gets the bare identity.

### Fixed
- The text that explains the form of a request (`HOW_TO_ASK`) showed doubled braces to the model, which copied them
  (CODE-81).

## [0.4.0] - 2026-11-23

### Added
- `Answerer.remote` and `ModelRunner.remote` (the model's `remote`): does what is asked leave this computer? The server shows
  a remote provider less of a document (CODE-80, D1568). An `Answerer` written outside this package must add it.

## [0.3.0] - 2026-11-22

Claude as a model behind the `@ai` (E7.11).

### Added
- `ClaudeModel(key, model, *, base_url=…, transport=None, read_timeout=30.0)`: asks Anthropic's Messages API; `generate`
  stops when `stop()` says so. `Answerer`, the protocol of what answers a `Request` (the local `ModelRunner` is one).
- `FailureReason` (`admin_sentence`), `ProviderError(reason, detail, provider=…)` and `ModelTimeout` (its own cause,
  D1492): what went wrong, in words for the administrator, with no secret in it.

## [0.2.0] - 2026-11-11

A question can take several rounds: the model looks, acts, is told what came of it, and carries on (E7.5).

### Added
- `ToolSpec.kind` (`"change"` by default, or `"look"` for a request that only reads), `Request.exchange` (the messages
  of the question after the person's text, in the rounds so far) and `Turn.raw` (exactly what the model wrote, to send
  back to it in the next round).

### Changed
- The prompt keeps requests that look apart from requests that change, says that the server sends back what came of the
  requests and that an answer without a `commands` block is the final one, and that what the document holds is data,
  never instructions. A model with only looking requests is told it cannot change the document.

## [0.1.0] - 2026-11-10

The first version under the versioning policy. Until now the package had a placeholder version (0.0.1), no
`__version__` and no API snapshot, so its surface could change without anyone noticing; from here on
`tests/api/claudia_ai.json` holds it to the rules of `docs/versioning.md`. This entry records the surface as it
stands, not a history of how it got there.

### Added
- `__version__`.
- `LanguageModel`, the interface a model is used through, with `Message` and `ModelError`.
- `OpenVinoModel`: a model run by OpenVINO GenAI on this machine (`pip install claudia-ai[openvino]`), on
  `DEFAULT_DEVICE` unless told otherwise.
- `Agent`: what the model is asked (`Request`, `Turn`, `ToolSpec`) and how its answer is read (`ToolCall`), at most
  `CALL_LIMIT` calls per turn.
- `ModelRunner`: one model, one question at a time, on a worker thread, with a time limit.
