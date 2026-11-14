---
id: D289
title: "A search names every place by the app's own `at`"
status: current
applies-to: all
date: 2026-11-13
round: "Search & replace in all three apps (branch `regex-builder`); QA follow-up CODE-18"
supersedes: []
superseded-by: []
---

# D289 · A search names every place by the app's own `at`

**Everything a search answers names its place as `at`, a small object that only the app reads**: in a workbook
`{sheet, row, col}`; in a text it will be a paragraph and an offset, on a slide a slide and an object. Matches,
left-out texts, a preview's changes and skipped places all carry `at`, and a client says which matches to leave alone
as `{at, match}`, sending `at` back unchanged. The search itself (`claudia_search.scan` and `plan`, over `Text(at, kind,
text)`) knows no app; the app offers its texts with their places, checks the `at` it gets back, and turns a plan into
its own command. In the web client the panel and `lib/search.ts` never read a place: the app's `SearchHost` keys it
(`keyOf`), names it (`where`, "Costs!B2"), goes to it (`jump`) and names its scopes (`scopeLabel`).

**Notes.** QA (CODE-18) found that D284's "one panel for all three apps" was computes-shaped all the way down: the
protocol, the session and the panel spoke `{sheet, row, col}`. Changed before composes (E9.28) and creates (E10.19)
build on it. A breaking change to computes' three search methods (claudia-server changelog); the web client and the
server ship together. *Left for the other apps:* the panel's own words still speak of cells ("Whole cell", "Replaced in
one cell") and the kinds are computes' (text, formulas, values); both become the host's when a second app needs them.
