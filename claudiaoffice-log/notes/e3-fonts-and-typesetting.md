# Fonts and typesetting libraries — E3.3, E3.4, E3.10

Built 2026-11-03 as two packages outside the kernel (D89): `claudia-fonts` 0.1.0 and `claudia-typeset` (0.1.0, then
0.2.0 the same day). Moved here 2026-11-05. Decisions D89–D99 are in `decision-log/`. Both packages are in the uv
workspace, in the API snapshot, in the Sphinx site and in the quality gate.

## How the two fit together

One catalogue (`claudia_fonts.Catalogue`) is the single source of truth for fonts (D93). A **collection** is a folder
of `.ttf`/`.otf` files with a `collection.json` (name, licence, `redistributable`, optional source and version). The
catalogue reads them with fontTools, keeps the latest font per family and style, records every font it refused or
replaced as a `Problem`, and has a digest over the sha256 of all accepted files.

- **Browsers:** `WebFontCache` makes `<sha256>.woff2` from the same bytes, only for redistributable fonts, and refuses
  if the file changed since it was read; `font_face_css` writes one `@font-face` per style with `font-display: swap`.
  Family names are escaped, so a hostile name cannot inject CSS.
- **Engine:** `write_fontconfig` writes a `fonts.conf` listing only the folders of accepted fonts, a shared cache
  directory, and a `rejectfont` for every refused or replaced file. It includes no system configuration and no
  aliases.
- **Substitution** (Arial to Liberation Sans, Calibri to Carlito and so on) is `Catalogue.resolve`.
  `claudia-typeset` applies it in the TeX source because XeTeX ignores fontconfig aliases (D95).

`claudia-typeset` turns a `Job` (mode math or page, source, optional font and width) into a checked SVG:

1. `Job` checks everything before anything runs: source size, file names, allowed file types, passes, font name,
   width. Document mode is validated but not built (`NotImplementedError`).
2. `build_source` writes a `standalone` document with fontspec and unicode-math, the text font and a math font from
   the catalogue, and the user's text on its own lines so TeX line numbers can be mapped back. The closing `$` of a
   formula is on its own line, so a `%` at the end of the user's text cannot swallow it.
3. `Typesetter` makes a private job folder, runs XeLaTeX through `run_sandboxed`, converts with
   `pdftocairo -svg -f 1 -l 1`, checks the SVG with `check_svg`, caches it under `cache_key(job, engine version,
   catalogue digest)` and removes the folder. Failures are never cached.
4. `parse_log` finds the first TeX error, maps it to a line of the user's text when it lies inside it, removes the job
   path from the message, and gives the `l.N` context line.

Exceptions: `BadJob`, `FontUnavailable` (before the engine starts), `TypesetFailed` (carrying a `TexError`),
`Timeout`, `OutputTooLarge`, `UnsafeOutput`, `EngineUnavailable`.

## Probe results (2026-11-03, one Linux machine, Debian TeX Live 2023)

- Formula to PDF: pdflatex 0.15 s, xelatex 0.32 s; PDF to SVG with `pdftocairo` 0.03 s, and the SVG is
  self-contained; peak memory about 183 MB.
- `-no-shell-escape` with `shell_escape=f`, `openin_any=p` and `openout_any=p` stop `\write18`, reading by absolute
  path, reading by `../`, and writing outside the job folder.
- `FONTCONFIG_FILE` pointing at a generated `fonts.conf` makes XeTeX embed a font that exists only in the listed
  folder; without it the same font is "not found". `pdffonts` on the result shows what was embedded; `-recorder` does
  not list fontconfig-loaded fonts.
- fontconfig `<alias>` and `<match>/<edit>` are **not** honoured by XeTeX/fontspec.
  `<selectfont><rejectfont><glob>` of an exact path does hide a file. This is the finding behind D95.
- TeX trees ship 72 Latin Modern and 33 TeX Gyre OTF files; their name tables carry no licence text; Latin Modern
  `fsType` is 12, not the restricted bit. WOFF2 of Latin Modern Roman: 108 KB to 47 KB in about 0.5 s.
- Present on that machine: beamer, tikz, standalone, amsmath, fontspec, unicode-math. **Absent:** biblatex.sty, biber,
  dvisvgm, tectonic — so biblatex and Beamer-with-biber remain untested.
- Tectonic (desk research, not run): it runs biber when needed but does not ship it, biber must match Tectonic's
  bundled biblatex, and offline operation after a warm cache is implied but pinning and enforcement are undocumented.

## Tests

`claudia-fonts`: 62 tests. `claudia-typeset`: 147 tests, of which 24 run the real engine and skip themselves where
`xelatex`, `pdftocairo` or `kpsewhich` are missing, and 8 run only on Windows. The rest need no TeX: job checks, the
SVG allowlist, the sandbox, source and log handling, the cache, and the typesetter with stand-in programs that record
how they were called. The repository has no async test plugin, so async tests are driven with `asyncio.run` through a
small decorator.

**Mutation checks done:** weakening `-no-shell-escape`, `shell_escape`, `openin_any` or `openout_any` makes six
hostile tests fail. The fonts library was checked the same way earlier. This is the strongest-tested part of the tree
and is worth copying as a pattern elsewhere.

## Windows, the user's own LaTeX, and the help topic (0.2.0, same day)

Decisions D97–D99, triggered by the owner's answer: users install LaTeX and configure its path, there must be a good
help entry, and the OS layer must work on Windows.

**The OS layer.** `run_sandboxed` picks a guard by platform. POSIX: rlimits set in the child, an own process group,
`killpg`. Windows: `_windows.WindowsJob` (ctypes, `kernel32`) with
`JOBOBJECT_EXTENDED_LIMIT_INFORMATION` — process time, process memory, an active-process limit of 16 and
kill-on-close — and the process put into the job right after it starts. The environment is a small allow-list per
platform. A folder watchdog (every 0.2 s, plus one check after the process ends) enforces `Limits.output_mb` as a
total and 10,000 entries on every system, because a limit on single files does not stop many files. After a limit is
passed the pipe is read to its end before the process is waited for; without that, `wait()` never returned — found by
the tests.

**Program lookup.** `programs.resolve_program` for the settings `xelatex` and `pdftocairo`: a path, a folder, or a
PATH name, with PATHEXT on Windows, no symlink resolution, and never the working folder. `Typesetter.diagnose()`
returns a `Diagnosis` with a hint per failed step. Messages name the setting, the value and
`typeset.configure-latex`.

**Help topic.** `claudia_typeset/help/configure-latex.md`: install steps for Windows (MiKTeX or TeX Live, poppler
through scoop or Chocolatey), macOS (MacTeX or BasicTeX, `brew install poppler`) and Linux; the two settings; MiKTeX's
install-on-the-fly switched off; check commands; typical folders; common errors. A draft format (D99).

## Not verified, plainly

- **No Windows code has run.** It was written from the documentation; the structure sizes (64, 48, 144 bytes on
  64-bit) and limit values are tested on Linux. The first real run is the Windows CI job, which has not run either.
- macOS has not been run on a real Mac, and `RLIMIT_AS` is not enforced there, so memory is limited only by the wall
  clock and the file limits.
- XeTeX's font lookup on Windows and macOS is untested, as is MiKTeX's use of its own configuration with a cleaned
  environment.
- Job Object assignment happens just after the process starts, so a small gap is real. The process is cheap to kill
  and runs nothing of the user's before TeX starts.
- `pdftocairo` is a separate poppler install on Windows and macOS; `dvisvgm`, part of TeX Live, could remove that need
  later.

## Open or not done

- **Nothing is wired to the server.** No routes under `/api/v1/fonts`, no `submit`/`status`/`cancel` wire methods, no
  per-document fair queue, no settings for the LaTeX programs, no Tools ▸ Check LaTeX, no capability flag for the
  frontend, and no registration of the user's TeX fonts into the catalogue. The product cannot typeset anything yet,
  and no document can be given a font.
- `claudia-fonts fetch` and `fonts.lock` for the starter set; the web app's brand fonts still come from npm packages.
- Document mode to PDF.
- HTTP route versioning: `CONTRIBUTING.md` says URL-versioned and existing routes are `/api/...`; new font routes are
  planned under `/api/v1/fonts`.
- CI installs TeX Live and poppler on Linux only, and the workflow has not run on a real runner.
- The cache key has no language yet, and the coarse catalogue digest invalidates everything when any font changes.
- The licence of Latin Modern and TeX Gyre (believed GUST Font License) goes to the audit (E11.2).

## Next slices as planned

1. Server routes `/api/v1/fonts` and the web brand fonts from the catalogue.
2. `providable_fonts` in the manifest check, the job font setup from a document's requirements, and registering the
   Latin Modern fonts of the user's TeX install into the catalogue with licence records.
3. Wire methods and the per-document fair queue, limits, Docker `WITH_TEX`, the demo cell `=$$\frac{x}{y}$$` (E6.15),
   and the settings screen with `--xelatex` and `--pdftocairo` plus Tools ▸ Check LaTeX.
4. Document mode to PDF with the font library hooked up; later biblatex/biber, Beamer, the preview-engine question,
   and `dvisvgm` as a way to drop the poppler requirement.
