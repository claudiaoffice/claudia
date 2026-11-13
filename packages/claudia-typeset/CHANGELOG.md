# Changelog of claudia-typeset

Newest first. The format follows [Keep a Changelog](https://keepachangelog.com/); versions follow the versioning
policy (`docs/versioning.md`). While the major version is 0, a minor version may break the API.

## [0.3.0] - 2026-11-13

### Added
- `Limits.address_space` (default `True`): `False` leaves out the address-space limit, which Chromium-based tools
  cannot run under (D346).
- `NEVER_ALLOWED`, and `check_svg(svg, *, extra_elements=...)`: a plugin may name more elements of its drawings
  (`<style>` rules are checked too); what can run code never is allowed (D343).
- `resolve_program(..., hint=...)`: the hint at the end of the message when a program is not found.

## [0.2.0] - 2026-11-03

Windows, and the person's own LaTeX (D90, E3.10): the typesetter works on the three systems, and it is told
where LaTeX is instead of finding it by luck.

### Added
- Windows: `run_sandboxed` puts the process into a Job Object (memory limit, CPU limit, limit on the number of
  processes, everything killed with the job) and starts it with a small environment of its own, with `TEMP` in
  the job folder. Written from the Windows documentation; it is first run by the Windows CI job.
- A watchdog on every system: the job folder may not grow beyond `Limits.output_mb` in total, nor hold more than
  10,000 entries, whatever is written in how many files (links are not followed).
- `run_sandboxed(search_path=...)`: folders put in front of the PATH of the process.
- `Typesetter(xelatex=..., pdftocairo=...)`: where the programs are, as a full path, a folder or a name on the
  PATH. Without LaTeX the server still starts; the first job says what is missing.
- `resolve_program`, `SETTINGS`, `HELP_TOPIC`: how a setting is resolved, the names of the settings and the id of
  the help topic that every message of `EngineUnavailable` points to (`help/configure-latex.md`, shipped in the
  package).
- `Typesetter.diagnose()`, `Diagnosis`, `Step`, `hint_for`: tests each program, the fonts and a small formula, and
  says what to do, for example which TeX package to install.

### Changed
- `EngineUnavailable` now lives in `claudia_typeset.programs` (still exported from the package).
- `Limits.output_mb` also bounds what a job writes to its folder in total.
- A process that is stopped for a limit is read to the end of its pipe before it is waited for.

### Fixed
- `run_sandboxed` no longer refuses to run on Windows.

## [0.1.0] - 2026-11-03

First version (E3.4 and E3.10, first slice): formulas and text blocks to SVG with XeLaTeX, outside the kernel.

### Added
- `Job`, `Mode`, `Limits`, `BadJob`: what may be asked; every field is checked before anything runs.
- `run_sandboxed`, `Completed`, `SandboxError`, `Timeout`, `OutputTooLarge`: a process with a clean environment, a
  folder of its own, resource limits and no survivors (Linux and macOS; Windows from 0.2.0).
- `build_source`, `parse_log`, `Built`, `TexError`, `FontUnavailable`: the TeX source for a formula or a page, with
  fonts chosen from the catalogue, and the first TeX error mapped to a line of the user's own text.
- `check_svg`, `UnsafeOutput`: the picture is only drawing, with no script and no reference to anything outside it.
- `cache_key`, `ResultCache`: results kept by job, engine version and font catalogue.
- `Typesetter`, `Typeset`, `TypesetFailed`, `EngineUnavailable`: the service itself.

### Not yet
- Document mode (whole documents to PDF), the worker pool and per-document queue (E3.5).
