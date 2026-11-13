# Changelog of claudia-render

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.1.0] - 2026-11-13

First release: rendered text containers (D340-D346). LaTeX, Mermaid and Typst are the first three types.

### Added
- `RenderService`, `RenderPolicy`, `Rendered`: a text in, a checked SVG out. The service finds the tools, caps a
  plugin's limits by the administrator's policy, enforces the manifest's `forbid` patterns, bounds how many jobs run
  at once and caches results by text, settings and tool identity.
- `ToolRegistry`, `ToolEntry`, `ResolvedTool`, `ToolStatus`, `ToolUnavailable`, `HELP_TOPIC`: the administrator's
  table from logical tool names to installations, resolved lazily; a failure is never remembered.
- `Manifest`, `parse_manifest`, `API_VERSION` (1) and the parts of a manifest (`ToolRequirement`, `ParamSpec`,
  `CliSpec`, `LimitSpec`, `EditorHints`, `Forbidden`): what a plugin says about itself, checked before anything runs.
- `Plugin`, `CliPlugin`, `LatexPlugin`, `PluginRegistry`, `LoadReport`, `UnknownType`, `RenderRequest`,
  `RenderResult`, `RenderFailed`: a plugin that is only data (argv templates, structured config files) and the
  LaTeX adapter over `claudia_typeset`.
- `Diagnostic`, `read_diagnostics`, `DIAGNOSTIC_READERS`: a tool's complaints as messages with a line of the
  person's text (`plain`, `typst-short`, `mermaid-parse`).
- `svg_size`, `default_alt`: the size of a picture and a sentence for somebody who cannot see it.
- `builtin_registry`: the Typst and Mermaid manifests (`plugins/*.json`) and the LaTeX adapter.
- Help topic `render.configure-tools` (English and German).
