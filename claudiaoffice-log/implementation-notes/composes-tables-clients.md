# Tables in the layout and the clients (E9.32, S2 and S3)

Decisions: D1213 (and D1201–D1212 for the model and the wire). Server side: `composes-tables-server.md`.

## Layout (`layout/src/flow/`)

- `table.ts` lays a table out by integer arithmetic: `layoutTable(fonts, styles, data, width)` gives the columns' widths
  (a width the person set wins, the others share what is left by their words, never under their longest word), every
  box's paragraph by `layoutParagraph` at its column's width, and the rows with their heights. A merged box is as wide
  and high as the boxes it joins; the covered ones draw nothing. The total row exists when a column has a total; its
  words are the server's (`totals`) and, in the first column without a total of its own, `total_label`.
- A row is *tied* to the next one when a merge joins them, when it is a header row (the header is one unit), or when the
  next one is the total row. `paginate` takes `FlowItem = FlowBlock | FlowTable`; a table is split between units of rows,
  the header is repeated on each continuation page when it is at most half a page, a header is never alone at the foot of a
  page, and a row taller than a page is split by its lines (`RowPart`). Keep-with-next looks over a table like over a block.
- `tableItems` draws the decorations of a row first (fills, then borders, one line between neighbouring boxes), then the
  words. Number columns are right-aligned.
- `apps/composes.ts` places the table objects after their anchor paragraph; a floating one is printed there too, with a
  note. Golden file in `tests/table.test.ts` pins the display list.

## Web (`web/app/`)

- `lib/tables.ts` (pure): the server's table as rows and boxes (`gridOf`), steps between boxes (`stepBox`), what Merge
  Cells joins (`mergeRect`), places for inserts.
- `lib/text-session.ts`: `state.tables` and `state.box`; events: a box's `text` event reloads the tables, the `table` event
  replaces one; the methods wrap the wire methods and are denied for a viewer.
- `components/TableView.vue` is the island: `<table>` with caption, `th scope=col`, derived `tfoot`, and one
  `<textarea rows=1>` per box. `TextEditor.vue` renders it after the paragraph it hangs from and ignores events that start
  in it (`fromTable`); the window's shortcuts still run, because the island does not stop key events.
- `lib/table-menu.ts` (pure) builds Edit's entries and the keys (`whileTyping`), `insertTableItems` the Insert entry.
  `TextWorkspace.vue` only holds the dialogs and `runTable`.
- The keys and the menus of every client come from the manifest (`clients/linux/.../manifest.py`): composes gets the table
  block through `_table_block()` and `insert.table` through `_insert_menu(tables=True)`; `_row_column_menus()` is shared
  with computes. `scripts/generate_keys.py` and `clients/neutralino/tools/generate_menu.py --all` regenerate the web key
  table and the macOS/Windows menus.

## Not verified

No browser or GNOME session was run. The focus hand-over between a box and the text editor, mouse-opened menus after
typing in a box (`state.box` stays until the selection moves), and screen readers are tested by reading the code only.
