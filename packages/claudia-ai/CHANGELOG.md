# Changelog of claudia-ai

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

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
