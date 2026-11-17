# CODE-33 and CODE-34: no claudia-client, one way to write a file (D700, D701)

2026-11-16, against local `main` at `9c58e72` ("Composes gets AI, part 2").

## What moved where

```
claudia-file-writer   stdlib only (new)
  atomic.py   write_atomically, atomic_file, write_once, Replacer, fsync_directory
  pinned.py   PinnedFile, fetch_pinned, download, FetchError
    ^
    |-- claudia-container  container._write_file (atomic_file, durable), journal.JournalWriter.replace (durable)
    |-- claudia-fonts      starter.fetch (fetch_pinned + collection.json), webfonts.WebFontCache.get (write_once)
    |-- claudia-typeset    cache.ResultCache.put (write_atomically: a garbled file must be replaceable)
    '-- claudia-server     state.write_private (durable), hyphenation.fetch (fetch_pinned)
claudia-core          unchanged: no I/O (test_purity.py)
```

`claudia-client` is gone (D700): package, API snapshot, docs page and changelog page, coverage floor, root
`pyproject.toml` entries, `uv.lock`. Notes that describe history keep the name; current descriptions say it was
removed.

## Behaviour that changed

* **Windows retry everywhere**, with the journal's policy (it was the more careful one): ten attempts, waits doubling
  from 0.05 s up to 1 s. `state.py` had five attempts, doubling without a cap; the fonts, the web fonts, the typeset
  cache and the hyphenation patterns had none.
* **Temporary names** come from `mkstemp` (`.<name>.<random>.tmp`), not `.<name>.<pid>.tmp`: two threads of one process
  writing the same file no longer share a temporary file.
* **Modes** are set with `chmod` before the move, so `mode=0o644` holds whatever the umask (the Docker image's fetch).
* **Web fonts are written once.** A second request for the same font found the file there before and returned it; now
  also a request that loses the race, or is refused on Windows because the file is being sent, returns it instead of
  failing.
* **Lock file names** of fonts and hyphenation follow one rule: letters, digits and `._,+[]-`, not starting with a dot
  or a dash. The fonts' rule allowed colons (a Windows drive or stream); the hyphenation rule did not allow the
  brackets of variable font names. Every pinned name passes.

## Tests

`packages/claudia-file-writer/tests` (100 % of statements and branches; the floor is 100): the retry and its waits with
a fake `replace` and `sleep`, so the Windows path runs in the Linux CI; the handle diagnostic with a real open file;
`write_once` losing a race; pinned files refused for bad names, plain http, a wrong hash, too many bytes. The fonts and
hyphenation tests that tested their own copies of download and write are gone; what is theirs (the command lines, the
collection record, 0644 on a fetched collection) stays.
