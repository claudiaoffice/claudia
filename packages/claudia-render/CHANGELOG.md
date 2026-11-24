# Changelog of claudia-render

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [Unreleased]

### Changed
- `ToolRegistry` takes its settings as a mapping or as a function that returns one. A function is asked again on
  every use, and the tools found under a table that has changed are looked for again, so a setting changed while a
  server runs takes effect at once (CODE-55).

## [0.3.0] - 2026-11-24

### Added
- `Plugin.cache_token()`: what a picture depends on besides its text, settings and tools; part of the key under which
  `RenderService` keeps it. `LatexPlugin` gives the font catalogue's digest, so a formula is drawn again after a font
  is replaced (CODE-54).

## [0.2.0] - 2026-11-17

Fonts added while a server runs reach the LaTeX container (CODE-50).

### Changed
- `builtin_registry` and `LatexPlugin` take a function that gives the font catalogue (`Callable[[], Catalogue]`)
  instead of a catalogue: the container asks for it on every job and makes a new typesetter when the fonts changed.
  A server passes `lambda: fonts.catalogue`; a caller with fixed fonts passes `lambda: catalogue`.

### Fixed
- Fonts added in Server settings ▸ Fonts while the server ran were not used by LaTeX formulas until the server was
  restarted: the container kept the catalogue it was built with, and said "the font 'Latin Modern Roman' is not
  available" for fonts the page listed (CODE-50).
- On macOS a job folder is made in `/tmp` when the system's temporary folder is too long for it (`/var/folders/…/T`,
  which resolves to the longer `/private/var/folders/…/T`): Chromium refuses a profile whose socket path passes about
  104 characters. The length that counts is the resolved one.
- The API reference builds again with warnings as errors (`sphinx-build -W`): `ResolvedTool.identity`'s docstring
  no longer starts like a type, the server's `RenderDesk` and `RenderSettings` and the kernel's rendering classes are
  documented, and a built-in such as `type[...]` in a signature is no longer linked to a field that happens to share
  its name (`Manifest.type`, `ParamSpec.type`; `docs/conf.py`). No API change.

## [0.1.0] - 2026-11-13

First release: rendered text containers (D390-D396). LaTeX, Mermaid and Typst are the first three types.

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
