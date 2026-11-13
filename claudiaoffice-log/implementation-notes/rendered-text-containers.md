# Rendered text containers: LaTeX, Mermaid and Typst as the first three types (D340-D346)

Branch `containers`. The idea: a container keeps a text, and a picture made from it is shown; the text is the truth.
This note records how the pieces fit, what the three real tools taught, and what is not built yet.

## The pieces

- `claudia_core.renderings.RenderedDefinition` and the object kind `rendered` (`claudia_core/objects.py`): the
  definition is kept by id and shown by objects, like a chart (D340). Creates, computes and composes each store the
  definitions in their state (`state_schema` raised).
- `claudia_render` (new package): `ToolRegistry` (the administrator's logical tool names), `Manifest` and `CliPlugin`
  (plugins as data), `LatexPlugin` (the one adapter), `RenderService` (limits, `forbid`, concurrency, cache),
  `builtin_registry` (the manifests under `plugins/`).
- `claudia_server.rendered.RenderDesk` renders one definition into a document as an edit; the hub schedules it when
  `RenderingsChanged` arrives; `rasterise.py` draws SVG as PNG for Office files.
- `claudia_creates_io`: ODP and PPTX write `model.picture_of(body)`.

## What the three tools taught the contract

- **Typst** needs a page and text prefix before the user's text (so the diagnostics' line numbers are shifted back),
  a project root, and no network: `@pkg/` imports are refused by a `forbid` pattern and a dead proxy is set.
- **Mermaid** needs a browser. `mmdc` reads two config files, so the manifest has `files` with structured JSON and
  `${tool.mmdc.chrome?}` options. Chromium cannot start under `RLIMIT_AS` (D346) and refuses socket paths over 107
  characters, which is why a job folder has a short path.
- **LaTeX** is the existing typesetter and is better as an adapter than as a manifest.
- All three return SVG that the core sanitiser first mangled: it dropped `<use>` (a typeset page is made of them) and
  renamed the `xlink` prefix. Both fixed in D344. LibreOffice also draws Mermaid's SVG as black blocks, so Office
  export prefers a PNG when `rsvg-convert` exists.

## What stays as it is

- Undo follows history: the render is its own undo step, so after one undo the text may show the older picture.
- Wire methods are synchronous; rendering is a hub job (D345). The submit/status job API (D92, E3.4) is not built.
- Composes has no object add on the wire. Its model holds definitions, and its server methods only read.
- The tool settings are read at start-up; changing them while the server runs needs a restart.

## Tests

Each package is run on its own (`uv run pytest packages/<name>/tests`); several packages' `conftest.py` in one process
collide. The render tests run the real tools where they are installed and skip otherwise (`CLAUDIA_TEST_TYPST`,
`CLAUDIA_TEST_MMDC`, `CLAUDIA_TEST_CHROME` name them), including hostile inputs.
