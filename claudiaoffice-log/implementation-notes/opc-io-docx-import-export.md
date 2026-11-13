# claudia-opc-io, and a first real docx import/edit/export (D217)

A new workspace package, `claudia-opc-io`, and `claudia-composes-io` built on top of it for a first real docx
import-and-reexport path — the design the preceding multi-round discussion settled on: diff model *state* (not
command replay) and patch only what changed onto the original file's own retained bytes, rather than rebuilding
an export from the reduced model alone and losing whatever claudia never modeled.

## `claudia-opc-io`

Dependency-free (stdlib only, deliberately: this is a shared primitive, not an app package), two small modules:

- `package.py` — `read_parts(zip_bytes) -> dict[str, bytes]` / `write_parts(parts) -> bytes`: a zip-as-parts
  boundary. Nothing here knows or cares what any part contains.
- `reconcile.py` — `owns(part_names) -> OwnedTest` (a predicate, so a caller can later use a glob or a format-
  specific rule instead of a fixed list) and `reconcile(original_bytes, regenerated_bytes, owned) -> bytes`:
  takes a library's own freshly-`save()`d bytes, and for every part the caller did *not* claim ownership of,
  restores the original bytes verbatim (added-by-the-library parts are dropped; parts the original had but the
  regenerated file does not are restored too, since a library that silently drops an untouched part is exactly
  the failure this exists to catch).

8 tests (`tests/test_package.py`, `tests/test_reconcile.py`). First version is whole-part granularity only:
reconciling a part means restoring it entirely or not at all. Shared/indexed-table merging (sharedStrings.xml,
a pivot cache, ODF's lack of any such index) is explicitly deferred — noted in `reconcile.py`'s own docstring —
relevant once xlsx/pptx and odfdo are wired to this package, not needed for a single-part-per-paragraph format
like docx's `word/document.xml`.

## `claudia-composes-io`: `docx_to_text` and `apply_edits_to_docx`

- `docx_to_text(docx_bytes) -> TextModel` — one block per paragraph, in document order, ids `b1`, `b2`, ...
  (matching `TextModel`'s own id scheme, so a model built this way composes normally with `fresh_id`). Word's
  four built-in styles this package already exports to (`Title`, `Heading 1`, `Heading 2`, `Quote`) map back to
  their claudia ids; anything else — `Normal`, a different built-in style, a custom style, no style at all —
  becomes body text, mirroring `text_to_docx`'s own fallback the other way. A docx with no paragraphs at all
  cannot actually be produced by python-docx's own blank template (it always has zero `w:p` elements until one
  is added) — the one case this surfaces is a document that, after import, has nothing: `docx_to_text` returns
  the usual `TextModel()` default (one empty body paragraph, `TextModel.empty()`'s own convention) rather than
  a model with no blocks at all, which the rest of the model layer does not support constructing anyway.
- `apply_edits_to_docx(original_bytes, baseline, current, *, track_suggestions=True) -> bytes` — re-export of an
  *edited* import. `baseline` is the model exactly as `docx_to_text` produced it; `current` is what the editing
  session has now. For each block, if neither its text/style nor its open suggestions changed, the paragraph is
  left completely alone; otherwise its runs are cleared and rebuilt the same way `text_to_docx`'s `_fill_paragraph`
  already does (plain text, or a tracked `w:ins`/`w:del` pair per open suggestion with a replacement). The whole
  document is then saved through python-docx as usual and reconciled against `original_bytes` with
  `owns(["word/document.xml"])` — in practice, for this one library, `document.xml` is the only part python-docx's
  own `save()` ever regenerates (it keeps every other part's bytes as it read them), so `reconcile` here is mostly
  a safety net rather than doing heavy lifting — but it is the same call `claudia-opc-io` will need for openpyxl,
  which regenerates the *entire* package on every `save()` regardless of what was touched, so the two libraries
  are handled through one interface rather than two bespoke recovery passes.
- Raises `UnsupportedEdit` if a block was added or removed since `baseline` — inserting or deleting a paragraph in
  the original file is not covered by this slice. Changing an existing paragraph's text or style is.

10 new tests in `tests/test_docx.py` (import order/styles/fallback/round-trip/empty-document; re-export: a
changed paragraph plus an untouched table both come through correctly, a style change, a newly open suggestion
rendered as a tracked change, and the two `UnsupportedEdit` cases). No regression in the 7 pre-existing
`text_to_docx` tests.

Checked against LibreOffice, not just structurally, same as D135's own check: a docx with a title paragraph, one
paragraph that gets edited, a two-row table (`Region`/`Amount`/`North`/`120`), and a trailing untouched paragraph,
round-tripped through `docx_to_text` → edit one block → `apply_edits_to_docx`, then converted headless
(`soffice --headless --convert-to odt`) — the title, the edited text, the untouched paragraph and the entire
table all come through into `content.xml` intact.

## Not done, on purpose

- Adding or removing a paragraph (`UnsupportedEdit`) — needs a real position-mapping strategy once blocks can
  shift, not just be rewritten in place.
- `claudia-opc-io` is not yet used by `claudia-computes-io` or `claudia-creates-io` (xlsx/pptx still export-only,
  from D135) or by anything ODF — this slice is docx-only, by design, to get the primitive and one real
  import/export path working end to end before generalizing it.
- Re-importing an existing tracked change (`w:ins`/`w:del` already in a docx a user opens) — `docx_to_text` relies
  on python-docx's own `paragraph.text`, which already skips tracked content entirely; reading it back as a
  claudia suggestion is future work.
- No test-document-library work yet (next, per the agreed sequencing): this note is deliberately scoped to the
  package and the first format, before revisiting that design with a real import/export path to test against.
