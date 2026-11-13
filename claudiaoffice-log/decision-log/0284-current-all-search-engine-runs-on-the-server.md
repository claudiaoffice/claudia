---
id: D284
title: "One pattern engine, on the server; the client asks for matches and gets spans back"
status: current
applies-to: all
date: 2026-11-13
round: "Search & replace in all three apps (branch `regex-builder`)"
supersedes: []
superseded-by: []
---

# D284 · One pattern engine, on the server; the client asks for matches and gets spans back

**One engine for all apps and clients**: the server evaluates patterns with Python's `re`, Unicode-aware, and answers a `search_find` request with the matches as `(location, start, end)` spans plus the text of any kept parts. Clients draw spans; they never evaluate a pattern themselves, so a pattern cannot mean one thing in the browser and another for the AI. The builder compiles to a pattern in this syntax; a typed pattern is validated by the server while typing, as CSS is (D73). Evaluation has a **time budget** and runs in the worker pool (D168–D182), so a pattern that backtracks without end is stopped and reported rather than freezing the server. The AI user searches through the same methods (D261).

**Notes.** Claude's proposal, agreed by the owner with the mock-ups on 2026-11-13. Python `re` has no `\p{L}`, so "a letter" compiles to `[^\W\d_]`; the builder hides this and a person typing her own pattern is told the syntax is Python's. The alternative, a client-side JavaScript engine for instant feedback, would mean two dialects and a second implementation for the AI; the server is local for most people and the request is debounced. The `regex` package (timeouts, `\p{L}`) is the fallback if `re` proves too limited; open in D287.

**As built (2026-11-13).** `claudia_core.search` on Python `re` (DOTALL, ignore case by default). Python's `re` cannot be interrupted, so the budget is kept in three places instead of by a worker timeout: a **static guard** that refuses nested or ambiguous repeats and over-deep nesting before a pattern is run (answered as an error with a reason, never run), **size caps** on the pattern and on each text, and a **time budget of 2 s** checked between texts, after which the answer says `timed_out`. A search that cannot be run is answered as `error: {message, field, position}`, not as a failed request, so the panel can say so while she types. The `regex` package stays open in D287.

**Changed (2026-11-13, D288, D289).** The shape guard above let exponential patterns through (SEC-18). Patterns now run on `regex` with a deadline inside the pattern, in the new package claudia-search; every answer names its place by the app's own `at`.
