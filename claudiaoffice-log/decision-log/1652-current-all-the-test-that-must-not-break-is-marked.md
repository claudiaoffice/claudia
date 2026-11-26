---
id: D1652
title: "The test that must not break is marked: a pytest marker, a name in TypeScript"
status: current
applies-to: all
date: 2026-11-25
round: "Menus: the owner's answers after slice 2 (branch `menus`, 2026-11-25)"
supersedes: []
superseded-by: []
---

# D1652 · The test that must not break is marked: a pytest marker, a name in TypeScript

**The test that covers a feature's key risk (coding standards §2) carries the pytest marker `@pytest.mark.must_not_break` in Python, registered in the project's `pyproject.toml`, and in TypeScript a name that starts with `must not break:`. Its docstring or comment says which risk it covers. `pytest -m must_not_break` and `vitest -t "must not break"` run them.**

**Notes.** The owner's answer to Q4 after slice 2 of the menu work; the convention is in `coding-standards.md`. The first is the menu workbook test, `tests/test_menu_workbook.py`.

**Later.** Main's D1663 (proposed on `test-quality`, 2026-11-25) gives the mark its story: `@pytest.mark.must_not_break("E5.23")`, the Gherkin tag `@must-not-break:E5.23`, and `[must not break: E5.23]` in a vitest title, which `tests/test_must_not_break.py` checks. The menu branch follows that form since merging main.
