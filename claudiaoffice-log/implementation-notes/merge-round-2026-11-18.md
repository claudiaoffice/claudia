# Merging four feature branches by pull request (2026-11-18)

First round in which Claude opened and merged the pull requests itself (the owner lifted the patches-only rule for this
experiment). Merge commits, `main` not protected. Order: `redaction` (#37), `style-delete` (#38), `tables-in-composes`
(#39), `floating-objects` (#40). Each branch took `main` in first, was tested, pushed, and merged through its PR.

## The procedure that worked

1. `git merge --no-ff origin/main` into the branch, resolve, run the whole suite, push, open the PR, merge it. The next
   branch then merges the `main` that holds the previous one, so every conflict is met once.
2. `gh pr create` does not work from a Claude session (GraphQL is blocked); the REST routes do:
   `gh api repos/claudiaoffice/claudia/pulls -X POST …` and `…/pulls/N/merge -X PUT -f merge_method=merge`.
3. Resolve by kind of file (below), then run: pytest, `layout` (`tsc` and vitest), `web` (`nuxt prepare`, vitest,
   `nuxt typecheck`), ruff, mypy, vulture, ESLint. The type checks found what the merge could not.

## Conflicts by kind

| Kind | What was done |
|---|---|
| Generated catalogs (`po/*.pot`, `po/*.po`, `web/public/i18n/*.json`, `*.mo`) | Never merged by hand. Take `main`'s, run `extract_i18n.py`, `update_po.py`, `make_pseudolocale.py`, copy the branch's German `msgstr` into entries that are still empty, then `po_to_json.py` and `compile_mo.py` (client and server). Fill only **empty** entries: filling every entry overwrites wording `main` changed. The `--check` forms of the four scripts must pass. |
| Changelogs, `ranges.md` | Keep both sides. Where `main` rewrote an entry the branch still has in its old form, `main`'s wording wins. A range row of a branch that is already on `main` is `main`'s, not the older row. |
| `claudiaoffice-log/human.md` | Deleted on `main` ("Notes removed") and edited on `floating-objects`: the deletion stands. The branch had only added a list of public test-document corpora (LibreOffice `sw/qa/extras/ooxmlexport/data`, `sc/qa/extras/testdocuments`, `sd/qa/unit/data`); it is in the history of `floating-objects`. |
| Code | Joined by hand; see the next two sections. |

## `floating-objects` with `tables-in-composes`

Both rewrote the print layout of composes (`layout/src/apps/composes.ts`) and the pagination.

* `build()` keeps `tables-in-composes`' split into `paragraphsOf` and `withTables`: a table is a flow item after the
  paragraph it hangs from, and pushes its own `origins` entry. The wrapping of `floating-objects` (`around`, `rows`,
  the passes that settle) stays inside `paragraphsOf`. A row of a wrapped paragraph is indexed by its place in
  `origins`, which is the place in the flow, so the table items between paragraphs do not move it.
* A line placed on a page belongs to a paragraph, never to a table (`paragraphAt`); `standing` and `locate` take
  `FlowItem`s. Objects of kind `table` are not wrapped around and not drawn as floating objects.
* `paginate.ts`: keep-with-next uses the item-aware check of `tables-in-composes` with the per-line leads of
  `floating-objects` in the height sum.
* **Not handled:** a table is laid out at the full width of the page and knows nothing about the bands a floating
  object keeps free. An object that overlaps a table's rows is drawn over them. Open (a wrap-aware table needs its own
  design: rows beside an object).
* Test: `layout/tests/composes-wrap-tables.test.ts`, a paragraph that wraps round a picture with a table hanging from
  it.

## Conflicts git did not report

`tables-in-composes` made `ObjectBody` point at its definition with one `ref` (D1211); `floating-objects` had moved
`add_object` out of `creates.py` into `shape_methods.py`, so `main`'s one-line change to the old copy had nothing to land
on, and three things on the branch still used the old fields. Found by the tests and by `nuxt typecheck`, not by git:
`shape_methods.py` builds the body with `ref=`; `web/app/lib/text-object-look.ts` and `TextContainers.vue` read an
object's shape and image with `pointer(object, kind)`; `test_server_composes_wrap.py` reads `obj["ref"]`.

**Lesson:** when one side moves code and the other changes it in place, git drops the change in silence. After such a
merge, search the moved code for the names the other side changed.

## What was red after the merges, and how it was made green (PR #41)

CI on `main` after #40 failed in Python (Linux and Windows), Linux client, Web and Chromium e2e. Every cause, none of
them in the merge conflicts themselves:

| Check | Cause | Fix |
|---|---|---|
| mypy | `element.attrib.pop(x, None)` in `_wrap.py`: the lxml stubs want a string default | default `""` |
| vulture | `PICTURE_STYLE_XML` had no user; `_set_wrap` is a registered wire method | constant removed; `_set_wrap` whitelisted like the other methods |
| docs | `WRAPS`, `MAX_WRAP_GAP` had no `autodata`; a corpus docstring named `run_file`/`discover`, which the package exports as `run_corpus_file`/`discover_corpus` | `autodata` entries in `docs/api/apps.rst`; qualified references |
| npm audit | allow-list entry `GHSA-fc5q-39xc-vjpf` matched no advisory any more | entry removed, as its own reason says |
| web lint | six ESLint errors on `floating-objects` | fixed |
| web tests | `text-object-look.test.ts` built objects with `shape`/`image` (before D1211's `ref`); hidden behind the lint failure | fixtures use `ref` |
| Linux client | the composes Edit menu test took Image… and Text Box to be the last entries; the table entries now follow | checks the order where it stands |
| e2e `pivots` | the SQL dialog opens at once and the query arrives later; the script read it once. It failed on `main` before this round too, and passes on a fast machine either way | waits for the text |
| LibreOffice (cancelled) | installing LibreOffice from a slow mirror took 14 of the job's 15 minutes; the check itself takes 44 seconds | limit 30 minutes, apt retries |

**Lesson:** a gate that stops at its first failure hides the ones behind it. The web tests never ran because lint
failed first, and the e2e steps after `pivots` (passwords, details, admin fonts, the two shell tests) had not run on
`main` since `pivots` started failing (it was already failing before the first merge). After a gate is repaired, run everything behind it too.

**Open:** `Python (macos-latest)` was never given a runner by GitHub ("capacity constraints, macOS arm64") in any run
seen on 2026-11-18, on `main` or on the PR, a re-run included, so no macOS result exists for this round.
