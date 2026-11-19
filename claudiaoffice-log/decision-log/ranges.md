# Decision numbers: who may use which

Every branch or agent that may write decisions gets its own block of numbers **before** it starts, and records it
here in the same commit as its first decision. Nobody picks "the next free number" from the folder: that is how
parallel branches kept giving one number two meanings. A block is 20 numbers; ask for another when it runs out.
Unused numbers in a closed block stay unused.

`tests/test_decision_log.py` fails if a decision's number lies outside every row of the first table.

## Handed out

| Range | Given to | Date | State |
|---|---|---|---|
| D1–D99 | the original single-file log | 2026-11-01 | closed |
| D100–D119 | renumbered container and Linux-client decisions (see `_rounds.md`) | 2026-11-05 | closed |
| D120–D135 | rounds 19–22 | 2026-11-05 | closed |
| D141–D161 | rounds 23–29 | 2026-11-07 | closed |
| D168–D182 | server settings, worker pool, shared object layer | 2026-11-07 | closed |
| D200–D213 | colour roles, charts, styling dialogs, office export | 2026-11-08 | closed |
| D214–D240 | the 2026-11-10 restructuring: renumbered duplicates (D214–D220), former open questions (D221–D240) | 2026-11-10 | closed |
| D241–D250 | E5.8 Linux client: three apps, other servers, HTTPS (branch `linux-client-complete`) | 2026-11-10 | open |
| D251–D260 | E5.11 macOS client: three apps, command line, server flow (branch `macos-client-complete`) | 2026-11-10 | open |
| D261–D270 | the AI agent: rights, modes, proposals, Claude as a provider (E7; branch `ai_server`) | 2026-11-11 | open |
| D271–D280 | E5.11 Windows client: three apps, command line, server flow (branch `win-client-complete`) | 2026-11-12 | open |
| D281–D290 | search & replace in all three apps: the dialog, the pattern builder, the engine, replace in computes (branch `regex-builder`; D281–D289 used) | 2026-11-13 | open |
| D291–D299 | random numbers, alternatives and following a computation in computes (E6.21–E6.23; branch `random-in-computes`; D291–D299 used) | 2026-11-13 | open |
| D320–D339 | complete interface internationalization: web UI, Linux shell, server messages, help (branch `i18n`; D320–D323 used; first given D320–D299, which `random-in-computes` had too, renumbered at the merge) | 2026-11-13 | open |
| D340–D349 | presenter mode in creates: rights, frozen show, Markdown notes, planned times, keys, and the open points (E10.2; branch `presenter`; D340–D348 used) | 2026-11-13 | open |
| D360–D369 | QA follow-up: UX consistency across clients: one key table, every menu entry everywhere, setup of a new document (branch `qa`; D360–D362 used; first given D340–D359, which `presenter` had too, renumbered at the merge) | 2026-11-13 | open |
| D370–D389 | real-world documents: xlsx as Excel writes it today, slide templates, cell formats and number formats (branch `real-world-docs`; D370–D380 used; first given D340–D359, which `presenter` had too, renumbered at the merge) | 2026-11-13 | open |
| D390–D399 | rendered text containers: object kind, plugin layer, tool registry, LaTeX, Mermaid, Typst (branch `containers`; D390–D396 used; first given D340–D359, which `presenter` had too, renumbered at the merge) | 2026-11-13 | open |
| D560–D569 | rendered text containers, the screens: Insert menu, editing in place, fences, composes floating (branch `containers`; D560–D564 used; first given D520–D529, which `search-ui` and `file-handling` had too, renumbered at the merge) | 2026-11-15 | open |
| D901–D920 | pages, print preview and PDF: the layout library, fonts for clients, page setup (branch `layouting`; D901–D918 used) | 2026-11-12 | open |
| D600–D619 | names, tables and SQL(): named ranges, structured references, spilling, SQL(), chart source (branch `named-ranges-sql`) | 2026-11-11 | open |
| D620–D639 | pivot tables: a pivot is a named definition that compiles to SQL, its grid, its interface, its files (E6.30; branch `pivot`; D620–D628 used) | 2026-11-15 | open |
| D640–D659 | code review follow-up: the text app's AI acts or suggests like the others (CODE-27 follow-up; D640 used) | 2026-11-15 | open |
| D300–D319 | styles as facets, slots and bundles: Format menu, Edit dialog, cell styles (D300–D318 used) | 2026-11-10 | open |
| D401–D420 | OpenDocument import and export: odt, odp, ods (branch `openoffice`; D401–D414 used) | 2026-11-11 | open |
| D430–D449 | one server for all three apps: app modules, addresses, limits, idle exit, folder lock, isolation (branch `one-server`; D430–D448 used) | 2026-11-14 | open |
| D480–D499 | Excel function coverage: matrix results, cell-by-cell operators, the first 300 functions (branch `excel-functions`; D480–D481 used) | 2026-11-14 | open |
| D450–D469 | import and export wiring: every function of the three apps reaches the OpenDocument and Office formats, and what does not is said (branches `import-export-wiring`, `import-export`; D450–D468 used) | 2026-11-14 | open |
| D1001–D1020 | printing sheets: the computes print preview, scale, print area, page cuts, footer, charts (E6.19; branch `computes-print`; D1001–D1010 used) | 2026-11-14 | open |
| D1021–D1040 | rotation in the three apps: a turn is one command, the outline stays on the slide, charts do not turn, composes objects float at a free offset, the handle, the menu and the keys (E6.17, E9, E10; branch `rotation-ui`; D1021–D1024 used) | 2026-11-15 | open |
| D500–D519 | the three desktop clients: the shared server on macOS and Linux, fonts every server has, files through the shells' dialogs, printing from a window, the front page's File menu, port 8765, drops on Linux, closing the macOS window through the page (branch `clients`; D500–D506 used) | 2026-11-15 | open |
| D520–D529 | the search panel and movable dialogs: moving, the one-button "Look in", "n matches", Markdown in help topics and the topic opened from the panel (branch `search-ui`; D520–D522 used) | 2026-11-15 | open |
| D550–D559 | the dock: names of things, replaying the history by scrubbing, tags in the chat (branch `dock`; D550–D554 used, D554 by the QA of 2026-11-15; first given D520–D539, which `search-ui` and `file-handling` had too, renumbered at the merge) | 2026-11-15 | open |
| D470–D479 | search & replace in composes and creates: what is searched, shortcuts in a text, locks (E9.28, E10.19; branch `search`; D470–D472 used) | 2026-11-14 | open |
| D530–D549 | document description and tags, the front page's way back from a collection, moving and copying documents between places (branch `file-handling`; D530–D536 used, D536 by the QA of 2026-11-15) | 2026-11-15 | open |
| D660–D679 | code review follow-up: one Neutralino package for macOS and Windows (CODE-14; D660 used) | 2026-11-15 | open |
| D680–D699 | the AI in composes: a model-driven participant, its document lens, words by quoting them (E7.10; branch `composes-ai`; D680–D681 used) | 2026-11-16 | open |
| D700–D719 | code review follow-up: no claudia-client, one way to write a file (CODE-33, CODE-34; D700–D701 used) | 2026-11-16 | open |
| D720–D739 | the redaction contract: what a redacted step keeps, the plan, dependents, imports, hidden lines and chat, the store rewritten, the wire and its screens (E1.8, SEC-05; branch `redaction`; D720–D729 used) | 2026-11-16 | open |
| D740–D759 | the Windows installer: self-contained server, packaged client, Inno Setup, the service, signing (E8.1; branch `win-installer`; D740–D745 used) | 2026-11-17 | open |
| D760–D779 | stabilisation of main, second round: style loss in the creates exporters, one name for facts Python owns, pinned and promoted CI (CODE-58, CODE-60, PROC-27; D760–D762 used) | 2026-11-17 | open |
| D1041–D1060 | font management: who may receive a server's fonts, Server settings ▸ Fonts, fonts kept honest from import to export (E3.13; branch `font-server-ui`; D1041 used) | 2026-11-16 | open |
| D1061–D1080 | the floating object layer in composes: wrap, the engine first, grabbing an object behind the text, the cycling key (branch `floating-objects`; D1061–D1068 used) | 2026-11-17 | open |
| D1101–D1120 | workflow: focus and quiet mode, corkboard, binder and its private drawer, open points, session intent and timeline (E16; branch `workflow`; D1101–D1116 used) | 2026-11-18 | open |
| D780–D799 | deleting and hiding styles: origin, hidden, the held look, the stand-in, collisions, the screens (E1.10; branch `style-delete`; D226 settled, D780–D786 used) | 2026-11-17 | open |
| D1201–D1220 | tables in composes: own tables, linked tables, merged cells, looks, keys (E9.32, E9.33; branch `tables-in-composes`; D1201–D1214 used) | 2026-11-18 | open |
| D1221–D1240 | object interaction in the three apps: one contract for select, move, scale, turn and the object menu, tables as in-flow objects, holding, E2E (branch `object-interaction`; D1221–D1229 used) | 2026-11-18 | open |

## Never to be used

| Numbers | Why |
|---|---|
| D136–D140 | left empty by the second renumbering pass (2026-11-07) |
| D162–D167 | the server-settings round's first numbering, moved to D170–D175 when it was merged; an old citation of D163 lived on in the code until 2026-11-10 |
| D183–D199 | skipped on purpose by the colour-roles round, so no live branch could reach them |
