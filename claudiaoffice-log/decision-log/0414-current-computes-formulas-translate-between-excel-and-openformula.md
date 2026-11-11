---
id: D414
title: "Formulas are translated between Excel text and OpenFormula by rules checked against LibreOffice's own output; what cannot be translated stays a value and is counted"
status: current
applies-to: computes
date: 2026-11-11
round: "OpenDocument import and export: odt first, maximum preservation (branch openoffice)"
supersedes: []
superseded-by: []
---

# D414 · Formulas are translated between Excel text and OpenFormula by rules checked against LibreOffice's own output; what cannot be translated stays a value and is counted

**`to_openformula(text, ...)` and `from_openformula(attribute, functions)` in `claudia_computes_io.openformula` translate between the model's formulas (Excel text with a leading `=`, D12) and the `table:formula` attribute (`of:=SUM([.A1:.A3])`).** References gain brackets and a dot (`[.A1]`, `[$Sheet2.A1]`, `[.A1:.B2]`, a name with spaces quoted); the argument separator is `;`; `&`, comparison operators, percent and unary signs stay. A formula that cannot be translated raises `Untranslatable(reason, detail)`: **the union and intersection operators (`~`, `!`) of OpenFormula and the Excel space operator have no counterpart in the model's language (D12)**, and a function the model does not implement is not guessed at. On import such a cell becomes its cached value with the loss `formula:<reason>`; on export it is written as its value alone with the same loss, never as a formula that might compute something else (D408).

**Checked, not assumed.** The translation was compared with what LibreOffice 24.2.7 itself writes for 110 probe formulas (functions, operators, absolute and mixed references, sheet references, strings with quotes, booleans, percent, nested calls): the only differences are XLOOKUP/XMATCH (written `COM.MICROSOFT.*` here, `_xlfn.xlookup` by LibreOffice) and a number written `1.5E3` that comes back as `1500`; `TRUE()` and `FALSE()` are kept as functions. `tests/test_openformula.py` holds the table and round-trips it.

**Notes.** A cached value is always written next to a formula (D408), and an `of` namespace declaration is always present, or LibreOffice reads every formula as an error (D413).
