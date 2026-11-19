# The function folder and what a document says it needs (E1.9; proposal D1313)

*Design for the owner's review, 2026-11-19, branch `e1-core`. The owner asked for the function folder to be designed in
E1.9 (open point 12) while the macro and `UserFunction` topic is parked (D1309). Nothing here is built.*

**Scope.** Where the functions a server offers come from, how a document says which ones it needs, and what happens when
it is opened on a server that has other ones. **Not** in scope: macros, heavy functions in workers, and whether the
code of a function may travel inside a document. Those are parked; §7 shows how this design leaves the door open.

## 1. What exists

* 253 built-in functions, registered by `builtin_registry()` (`claudia_computes/functions/builtin.py`) through
  `FunctionRegistry.register`, which already refuses a reserved name, a duplicate, a missing description and a missing
  example.
* **Nothing loads a user's function from anywhere.** D38 says the administrator installs functions from a folder on the
  server; that folder does not exist (E4.10).
* The manifest of E1.9 is a data model and a check (`claudia_core/manifest.py`: `Requirements`, `Environment`,
  `check`, `RequirementReport` with `missing_functions` and `stale_functions`), plus `Document.apply_report` and
  `DocumentModel.mark_stale`. **No app overrides `requirements()`**, and the server never builds an `Environment` with
  functions or `providable_fonts`: the check is never run.
* The sealed file has a **plain** `manifest.json` (title, uid, app, description, tags; D103, D530) that anybody who can
  list the server reads. It is not where requirements can go (§4).
* The font service (D905, D1041) is the model to follow: three sources read in order, a catalogue with a digest, a
  reload, a Server settings page.

## 2. The folder

Three sources, like the fonts:

| Source | Where | Who writes it |
|---|---|---|
| built-in | code: `claudia_computes.functions.library` (E4.11) | the release |
| operator | `--functions DIR`, repeatable | whoever starts the server |
| added | `STATE_DIR/functions/` (next to `admin/` and `fonts/`, `state.py`) | an administrator, or the person on a local server |

* One `.py` file per function by convention; a file may define several. A function is a `UserFunction` subclass exactly
  as `functions/base.py` describes; the only addition is `version = "1"` (a string, shown to people, **not enforced**: the
  digest is the truth).
* **The AI can never write there** (E7.6 already tests that no method reachable by `ai` writes to the function
  folder), and nothing a document or a network client sends is ever written there or run. Same trust rule as D38:
  whoever controls the folder controls the functions.
* On a **local** server (the desktop client's own) *Tools ▸ New Function…* (E4.10) writes into `STATE_DIR/functions/`,
  which is the "profile folder" of that story. On a network server only an administrator may.

## 3. Loading

At start and on *Reload* (a button on the settings page; watching the folder is E4.10):

1. each `.py` file is imported under a private module name with `importlib` (no change to `sys.path`);
2. each `UserFunction` found goes through `FunctionRegistry.register`, so every existing refusal applies, **plus** the
   examples are run as tests (`check_examples`, E13.2): a failing example refuses the function, with the reason;
3. a function whose name is a built-in or a core form is refused ("cannot be replaced"); a name already taken by an
   earlier source is refused for the later one, never silently replaced (**operator before added**);
4. every refusal is recorded with the file and the reason and shown on the settings page. **One bad file never stops the
   others or the server.**
5. A reload bumps `registry.version`, so every open workbook recompiles its formulas and recalculates: an edited
   function shows its new results at once, which is what E4.10's "hot reload" asks for.

The server builds one registry per module (built-ins plus the folder) and hands it to every workbook, so a document
never loads code itself.

## 4. The digest, and what a document records

* **Digest** of a function = SHA-256 of its **file** with line endings normalised and trailing blanks removed, computed
  at load (`Bound.version`, `Bound.digest`, `Bound.source`). The whole file, not the class: a helper at module level
  is part of the function, and a change there can change results. The cost: editing a comment in a file that defines
  three functions changes all three digests. The template of *New Function…* has one function per file.
* **Built-ins have no digest.** They are versioned by the release (`state_schema` and the package version). A document
  that calls `XLOOKUP` records the name only, so an older server that lacks it says so.
* **What a document records is a stamp**: for each function its formulas call that is not a core form, `(name,
  version, digest)` as of the last time the document was calculated with it. `WorkbookModel.requirements()` reads the
  names from the formulas (derived, never stored); only the **digests** are stored, because they cannot be derived from
  the content.
* **Where the stamp lives: inside the sealed content, not in the plain manifest.** A function's name can say what a
  document is about (`BONUS_BANDS`), and the plain manifest is readable without a password. So the stamp is a **logged,
  non-undoable command** `StampFunctions`, the precedent being `Redacted`, `Checkpoint` and `ApplyCalculated`; replay
  gives the same stamps in the same order. The server appends it when a user function is first used in the document and
  when an editor or owner accepts a changed function (§5). The history shows it as one quiet entry.
* **Fonts are not stamped.** What a document needs in fonts is derived from its content on open (styles and runs), and
  D1306 says what happens.

## 5. On open

The server builds the `Environment` (app, schemas, the folder's functions with version and digest, installed fonts,
fonts the font service can provide) and runs `check(manifest_of(model), environment)`:

| Finding | What happens | What a person sees |
|---|---|---|
| a function is **missing** | the document opens; every cell that calls it shows `#NAME?`; the **formula text is kept**; installing the function and reloading recalculates | a quiet banner at the top of the document: "TAXRATE is not installed on this server (used in 14 cells). Ask the person who runs it." Details… |
| a function's **digest differs** from the stamp | the document is calculated with the **installed** function (values are derived, so they are right for this server) | a banner: "TAXRATE has changed since this workbook last used it. Results may differ from before. **Keep this version** (editors and owners) · Details…". *Keep* appends a new stamp. A viewer sees the banner and cannot stamp |
| a font is missing | D1306 | the same banner, one line per kind |
| wrong app or a newer schema | refused with the existing message | as today |

Nothing here **blocks opening**, and nothing is deleted or rewritten. The banner is not modal and can be dismissed for
the session; it comes back the next time the document is opened while the finding stands. `RequirementReport.ok` and
`clean` already say which findings block and which only inform. `mark_stale` stays as it is (it matters for stored
worker results, E4.5, which are parked): for pure in-process functions a changed function simply recalculates.

## 6. Screens and what is in E1.9

* **Server settings ▸ Functions**: a table of every function (name, version, source, short digest, loaded or refused
  with the reason, how many open workbooks use it) with *Reload*; the same Claudia look as Fonts, the Ink admin chrome and
  the persistent "which server" line (the earlier admin-surface stance). *Add* and *Remove* come with E4.10.
* **Tools ▸ Functions…** in computes (E6.8 already names it): the list for everybody, read only, with each function's
  examples, and "this workbook needs" with the status of each. *Tools ▸ New Function…* stays E4.10. Both are
  computes-only Tools items; the menus workbook gets the rows and keys before they are built.
* **The banner** is the one new thing a person sees on open, in computes (functions) and in all three apps (fonts).
  It needs a mock before it is built.

**Proposed split.** **E1.9** gets the loader, the digest, `requirements()` for workbooks, `StampFunctions`, the check on
open, the banner, the read-only Server settings ▸ Functions page and the read-only Tools ▸ Functions… list. **E4.10**
keeps *New Function…*, add and remove, and watching the folder. **E4.4/E4.5** (heavy and worker results) stay with the
parked topic.

## 7. Documents sent between servers, and the parked question

The owner's worry is that documents sent around will meet servers with other code. What this design gives: a document
**says exactly which function versions it was calculated with**, a server **tells the person precisely** what differs,
and **nothing is lost** (formulas are kept as text, results are recalculated, never overwritten).

What it does not do is **supply** a missing function. The parked question (should functions or macros live *in* the
document?) can be answered later without redoing this, because a function is already **one text file with a digest**.
One possible answer, offered only as a thought: a document may carry the **source** of the functions it needs as inert
data, which is never run; the server shows it to an administrator, who can install it with one click after seeing that
its digest equals the stamp. Nothing executes from a document (D38 holds), and the sender's code still arrives with
the document. That is a choice for the owner, not part of this proposal.

Export to Excel is a separate point: a user function has no Excel counterpart, so the export should write the last
values and say so in the loss report. To be checked in the import/export round; not part of E1.9.

## 8. Tests first (TDD)

Loader: a good file registers; a bad file, a failing example, a reserved or duplicate name are refused with reasons and
the rest still load; operator before added; reload bumps the registry version and recalculates an open workbook; the AI
and a network client cannot write the folder. Digest: stable across line endings, changes with the file. Kernel:
`requirements()` lists exactly the non-core functions called; `StampFunctions` replays identically and is not undoable;
`check` gives missing and changed. Server: the report on open for each row of §5; a viewer cannot stamp; the plain
manifest never carries a function name. E2E (spec first, `specs/container/requirements.feature`).

## 9. For the owner to decide (defaults proposed)

1. One file per function by convention; digest of the whole file; `version` shown, not enforced.
2. The stamp is a sealed, logged, non-undoable command, never in the plain manifest.
3. A changed function: open, calculate with the installed one, banner, *Keep this version* for editors and owners.
4. A missing function: `#NAME?`, formula kept, banner.
5. Sources: built-in, `--functions`, and `STATE_DIR/functions/` through Server settings; operator before added; a
   built-in name is never replaceable.
6. Built-ins are recorded by name only, without a digest.
7. The scope split of §6 between E1.9 and E4.10.
8. The banner needs a mock first; do you want the mock in this round?
