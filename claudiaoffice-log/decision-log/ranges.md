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
| D281–D290 | search & replace in all three apps: the dialog, the pattern builder, the engine, replace in computes (branch `regex-builder`; D281–D287 used) | 2026-11-13 | open |
| D291–D299 | complete interface internationalization: web UI, Linux shell, server messages, help (branch `i18n`; D291–D294 used) | 2026-11-13 | open |

| D300–D319 | styles as facets, slots and bundles: Format menu, Edit dialog, cell styles (D300–D315 used) | 2026-11-10 | open |
| D901–D920 | pages, print preview and PDF: the layout library, fonts for clients, page setup (branch `layouting`; D901–D918 used) | 2026-11-12 | open |
| D600–D619 | names, tables and SQL(): named ranges, structured references, spilling, SQL(), chart source (branch `named-ranges-sql`) | 2026-11-11 | open |
| D300–D319 | styles as facets, slots and bundles: Format menu, Edit dialog, cell styles (D300–D318 used) | 2026-11-10 | open |
| D401–D420 | OpenDocument import and export: odt, odp, ods (branch `openoffice`; D401–D414 used) | 2026-11-11 | open |

## Never to be used

| Numbers | Why |
|---|---|
| D136–D140 | left empty by the second renumbering pass (2026-11-07) |
| D162–D167 | the server-settings round's first numbering, moved to D170–D175 when it was merged; an old citation of D163 lived on in the code until 2026-11-10 |
| D183–D199 | skipped on purpose by the colour-roles round, so no live branch could reach them |
