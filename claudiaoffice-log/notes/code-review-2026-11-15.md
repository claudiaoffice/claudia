# Code review of 2026-11-15 at `7994b00`

The owner asked for a review for duplication, separation of concerns, naming and convoluted solutions. The items are
in `bugtracker.md` as CODE-27 to CODE-41, with CODE-14 and CODE-21 re-checked. This note gives the overall picture, the
order to work in, and the questions only the owner can answer.

## The picture in one paragraph

The Python side is in good shape: low complexity (12 functions of grade D or worse in radon, the worst 36), 0.3 %
duplicated lines, a strict ruff set, and good layering where it was designed on purpose (search: engine, app adapter,
wire adapter). The debt sits at the *edges between the apps*. The kernel shares objects across the three apps, but
the server's wire methods for them are written three times (CODE-27); per-app wiring is spread over five tables
(CODE-28); the two Neutralino shells are still copies (CODE-14); the web's three sessions repeat their write path and
shared methods (CODE-35). Most of it comes from the same history: computes was built first, composes and creates were
grown next to it by copying, and the shared layer was extracted below (kernel) but not above (server methods, web
sessions). Several "kept in sync by hand" spots are guarded by tests that compare the copies rather than by having
one copy (CODE-32).

## Measured

| What | Result |
|---|---|
| Source lines (no tests) | ≈ 102,000 (Python 58,700, TypeScript 34,500, Vue/CSS the rest) |
| Test lines | ≈ 92,700 |
| Duplicated lines, jscpd (≥ 12 lines, 80 tokens) | 3.6 % overall; Python 0.3 %; TypeScript 9.6 % (almost all the two Neutralino shells) |
| macOS vs Windows shell | 11 of 22 source files byte-identical (1,658 lines), 10 test files (1,233 lines), the 3 generated menus identical |
| radon, grade D or worse | 12 functions (`numformats._render_number` E/36, the rest D/21–26) |
| Function-level imports (PLC0415, ignored repo-wide) | 44, 29 of them in `claudia_computes` |

## Order of work (proposal)

1. **CODE-14 and CODE-27** first: they are where a fix today must be made two or three times, and both block cheaper
   follow-ups (CODE-32's single generator, CODE-28's app record).
2. **CODE-31** (history in English for a German user): small, visible, and it touches a principle (i18n everywhere).
3. **CODE-34** (atomic writes without the Windows retry): small; a real failure mode on the Windows client's server.
4. **CODE-30, CODE-35, CODE-36, CODE-37**: mechanical, each a single afternoon, each removes a class of copy.
5. **CODE-28, CODE-29, CODE-38, CODE-39**: structure and names; best done together with the single-server move
   (D430–D432), since it touches the same files.
6. **CODE-41**: the import cycles in computes; the largest and least urgent.

## Questions for the owner

* **CODE-14:** D113 says one package per OS. Merging the macOS and Windows sources into one `clients/neutralino/`
  package needs that decision amended. Go ahead?
* **CODE-33:** `claudia-client` is used by no client. Delete it, or make it importable by the Linux shell (drop its
  unused `claudia-core` dependency, target Python 3.12) and replace the shell's own `trust.py`?
* **CODE-31:** translate history entries on the server (in the connection's locale, as other server messages are) or
  on the client (commands send a msgid and parameters)? Server-side is smaller; client-side lets a person switch
  language without a round trip.
* **CODE-35:** composes' session checks `denied()` and wraps every write in `act()`; computes and creates do not. Is
  that difference intended (composes' typing buffer) or should all three follow one write path?

## Method

Cloned `main` at `7994b00` (2026-11-15 18:14). Ran jscpd 4 over `packages`, `clients`, `web/app` and `layout/src`
without tests and generated files; radon cc; ruff with N, ARG, PIE, ERA, PL added to the project's set; byte
comparison of the two Neutralino trees. Read `claudia_server` (protocol, apps, computes, composes, creates, rendered,
office_export, state), `claudia_core.objects`, `claudia_computes` (model, region), the fonts and hyphenation fetchers,
the Linux manifest, `web/app/lib` (the three sessions, base session, document menus, storage use) and the large
components. Every line number in the items was read at `7994b00`.

**Not reviewed:** `layout/` beyond the duplication scan, the io packages' internals (only their export wiring),
`claudia-container`, the AI packages, CSS, the shells running on their own systems. The local working copy was not
read file by file; it differed slightly from `main` in a few files (a patch for CODE-26 lay unapplied at its root).
