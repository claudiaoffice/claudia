# Search & replace — design note

2026-11-13, branch `regex-builder`. The owner's brief is D281; the rest is Claude's proposal (D282–D287, all `undecided`) until the screens are agreed. Screens are in `mockups/`; nothing is coded yet.

## What the owner asked for

One function across all three apps, at **Edit ▸ Search & replace…**. Computes first, where it searches text in cells, formula expressions and values. It is based on regular expressions, but a person is not told so. She builds the important queries in a UI that shows what they do ("this string must not occur, but at least one of these characters") and can type her own pattern and apply it directly, an option that is not on the surface, like the CSS view of a style (D73).

## The screens

| File | Shows |
|---|---|
| `mockups/search-replace-edit-menu.svg` | The entry in Edit of all three apps: one new group between the clipboard and the app's own items |
| `mockups/computes-search-find.svg` | The quick path: type, see "1 of 6", matches tinted in the grid, a corner mark where the match is in a formula, results listed with their kind |
| `mockups/computes-search-builder.svg` | The builder with the owner's example; the pattern restated as a sentence; what was left out and why |
| `mockups/computes-search-replace.svg` | Replace with a kept part; the sheet shows the result in place before anything is replaced; a cell locked by Anna is skipped and named |
| `mockups/search-pattern-as-text.svg` | "Write the pattern yourself" from the ⋯ menu: three fields, validation while typing, a sample to try it on |
| `mockups/search-in-composes-and-creates.svg` | The same panel in composes (paragraphs with their heading) and creates (slides, locked shapes) |

The worked example in all computes screens is one sheet, "Budget 2027", whose Amount column was typed as text in four notations.

## One panel, one component

The panel is non-modal and floats over the right of the document (D282). It is **one frontend component** for the three apps and every shell, with a `SearchHost` per app, the way the styling dialog has a `StyleHost` (E5.13). The host says what the app can look in, how to draw a match, how to jump to it and how to replace it; everything else is shared.

| | computes | composes | creates |
|---|---|---|---|
| Look in | Text, Formulas, Values | Text, Headings, … (by style) | Text boxes, Shape labels |
| Where | This sheet, All sheets, Selection | Whole document, Section, Selection | All slides, Selected slides |
| A result is | a cell, with its kind | a paragraph, with its heading | an object, with its slide |
| Extra parts in the builder | a cell reference, a function name | a word | none yet |
| Replace keeps | the cell's style | the paragraph's style | the box's and paragraph's styles |

## The builder's vocabulary (D283)

**Find** is a list of parts: *what* × *how many*, optionally *kept as a name*. **Only in cells that…** is a list of conditions on the whole cell. With no part given, the whole cell is the match.

| Builder says | Compiles to |
|---|---|
| the text "X" | `re.escape(X)` |
| any one of € $ £ | `[€$£]` |
| none of a b | `[^ab]` |
| a letter / a digit / a space | `[^\W\d_]` / `\d` / `\s` |
| a number | `\d+(?:[.,]\d+)*` |
| start / end | `^` / `$` |
| once / optional / one or more / any number | *(nothing)* / `?` / `+` / `*` |
| exactly n / n to m | `{n}` / `{n,m}` |
| kept as "amount" | a capture group; `\1` in the replacement |
| cell contains X | cell filter `^(?=.*X)`, with DOTALL so a cell may hold line breaks |
| cell does not contain X | cell filter `^(?!.*X)` |
| cell starts with / ends with / is exactly X | `^X` / `X$` / `^X$` |
| all of / any of | filters in a row / `(?:A|B)` |
| Match case off | `re.IGNORECASE` |
| Whole cell / whole word | `^(?:…)$` / `\b…\b` |

The mock-ups' example compiles to Find `€\s?(\d+(?:[.,]\d+)*)`, cell filter `^(?!.*EUR)`, Replace `\1 EUR`. The quick find field is **always plain text**, escaped; a pattern only appears through the builder or the ⋯ menu.

Why two patterns (the span and the cell filter): a replacement needs a span, and "does not contain" has none. Folding the filter into the span's pattern would put a lookahead before every match; keeping it apart is also what lets the panel say *why* a cell was left out.

## Pattern as text

Reached from ⋯ ▸ Write the pattern yourself…, so the surface stays quiet. It starts from what the builder made, so it teaches. It has three fields (Find, Only in cells matching, Replace), the one flag a person can see (Ignore capitals), a sample to try the pattern on with the kept parts marked, and one sentence with a character position for each mistake. Editing it ends the builder's view of it; "Back to the builder" returns to the last builder state after a confirmation. The syntax is Python's `re` and is said to be so in one small line.

## Engine and protocol (D284)

The server evaluates; clients draw spans. A sketch, not yet a decision on names:

```
search_find(query, scope)   → { matches: [{ where, start, end, kind, parts }], left_out: [{ where, why }], counts: {text, formulas, values}, error? }
search_replace(query, scope, replacement, exclude)   → one command (D286)
```

`query` is the builder's model or a typed pattern. `search_find` is debounced by the client and cancellable; evaluation has a time budget in the worker pool. A mistake in a typed pattern comes back as `error: {message, position}`. The AI user calls the same methods.

## Replace in computes (D285, D286)

Stored contents only. A value a formula computes is findable, never replaceable, and the Values switch shows a lock when Replace is open. Replace opens with Text only and says when the pattern is also in formulas, because replacing inside a formula can change what it computes; in the example "€" is in four `SUBSTITUTE(…;"€";"")` formulas that must not be touched. The command stores the changed cells, not the pattern, so replay never depends on the engine. The effect is shown in the grid before it is made. The later step, showing a formula's new *value*, is the scratch-copy preview of D263.

## What else has to move when it is built

* **Menu and shells**: `edit.search-replace` in `web/app/lib/document-menus.ts` (the shared block), the shortcut table in `web/app/lib/shortcuts.ts`, and the GTK and Neutralino manifests with accelerator and role. The desktop shells frame the web app, so they need nothing else.
* **i18n**: every phrase of the builder is a whole translatable string with placeholders; none is assembled from pieces, because word order differs between languages. Part names such as "number" are strings too.
* **Accessibility**: a live region says "6 matches"; a match is marked by a band and an underline, not colour alone; the panel is reachable by keyboard from the first Tab and closes with Esc and returns the focus to where it was.
* **Import and export**: none. A search is not content of a document, and Excel, LibreOffice and Word have their own find. Said here so nobody looks for it.
* **Tests and docs**: E1.12 starts with the compile table above as its first test file. The pattern syntax and the builder have a Help topic, "About searching and patterns", with worked examples; the engine and the new methods are in the Sphinx documentation and the API surface.
* **Performance**: the first version scans a sheet's stored contents once per request; a debounce of about 150 ms; a time budget on the engine; the list is virtualised after 200 matches. To be measured on the large test documents before anything cleverer.

## Open (D287)

Panel placement against a bar; `re` against `regex`; what "Values" means for formatted numbers; what else computes searches (names, sheet names, chart titles, floating text); accent-insensitive matching; saved searches; macOS shortcut for Replace; replace in composes while others type.
