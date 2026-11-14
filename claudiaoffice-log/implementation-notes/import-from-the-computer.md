# Opening files from the computer: import, the kept original, the round trip (D438–D442)

Branch `one-server`, the import patch (between the server patch and the web patch). Sheet 10 of the file-management
mock-ups needs "Open a file…": Word, Excel, PowerPoint, OpenDocument and Claudia files from the person's computer.
The readers (`docx_to_text`, `xlsx_to_workbook`, `pptx_to_slides`, `odt_to_text`, `ods_to_workbook`,
`odp_to_slides`) and the patching writers (`apply_edits_to_*`, D217, D371, D402, D403, D412, D413, D219) existed;
nothing made a document of a file, and nothing kept the file they patch.

## What was built

* `claudia-core` 0.22.0 — `Import` (`core.Import`) and `DocumentModel.load_state` (D438); `claudia-computes` 0.7.0
  rebinds its calculator in `WorkbookModel.load_state`.
* `claudia-container` 0.5.0 — `write_original`/`read_original`: the entry `content/original.bin`, sealed with the
  content key and bound to the id (D439). Packing and changes of the people carry it along (they keep unknown entries).
* `claudia-server` 0.31.0 — `packages/claudia-server/src/claudia_server/formats.py` (`sniff` by bytes,
  `import_state` run in the worker pool), `packages/claudia-server/src/claudia_server/uploads.py` (`UploadDesk`,
  limits), `POST /api/uploads`, `hello` with `upload` and `keep_original`, `POST /api/uploads/{token}/place`
  (`Hub.place`, `SealedDocuments.place`), and `export_with_original` in `office_export.py` used by all three apps'
  `export_office` (D441).
* Tests: `test_server_formats.py`, `test_server_import.py` (every format imported and given back patched; the kept
  file across packing and a restart; refusals), `test_import_entry.py` in the kernel, the container's own.

## Things to know

* The round-trip tests use files written by Claudia's own writers plus an extra part; the real-world library
  (`test-documents/`) is not run through the upload path yet.
* `docx` and `pptx` have no import-losses function yet, so their welcome lists no losses.
* The first import starts the worker pool's processes (about a second); later ones reuse them.
* Uploads are held in memory (at most 16 × 64 MB). That is the ceiling for a small server; a larger one will want them
  on disk.
