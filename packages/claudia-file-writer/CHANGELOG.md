# Changelog of claudia-file-writer

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.1.0] - 2026-11-16

The one way a Claudia server writes a file (CODE-34, D701). Before, seven modules in five packages did it each their
own way, and only two retried on Windows.

### Added
- `write_atomically` and `atomic_file`: a file is written next to its place and moved there in one step, so a reader
  sees the old file or the new one, never a part. Private (0600) unless told otherwise; `durable=True` waits until the
  file and its folder are on disk. A file that cannot be written leaves no temporary file behind.
- `write_once`: for a file named by what is in it (a hash). It is not written again, and losing a race to another
  writer, or to a reader that holds the file open on Windows, is not an error.
- `Replacer`: how the final move is retried on Windows, where antivirus scanning and indexing hold a file just
  written for a moment. Waits that double up to a second, ten attempts; when the last fails, the error names any file
  of this process that still holds the file open.
- `fsync_directory`.
- `PinnedFile`, `fetch_pinned`, `download` and `FetchError`: files fetched by URL and checked against the SHA-256 a lock
  file gives (the fonts' starter set and the hyphenation patterns).
