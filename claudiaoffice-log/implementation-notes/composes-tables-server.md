# Tables on the server (E9.32, S1)

Where things are, and why. Decision: D1212 (and D1201–D1211 for the model).

## The wire

`claudia_server/tables.py` is a module of methods like `rendered.py` is: `add_table_methods(table, model_of=…,
placement=…)` registers them, composes calls it next to `add_rendering_methods`. An app that holds objects but no
tables (creates, computes) does not call it. The methods only say what a request means; the kernel's commands
(`claudia_core/table_commands.py`) do the work, carry the exact inverses and the regions for locks.

- A table is named by its id, rows and columns by theirs; a request never says "row 3". The ids are in `tables`.
- Table ids are random (`t` + 8 hex digits), row and column ids come from the definition's counters, so an id of
  something that was deleted never comes back.
- `merge_cells` is one Batch: the words of the covered boxes are joined to the first box (they are not lost), then the
  merge. A dry run on the definition happens first so that a refused merge changes nothing and says why.
- `set_entries` keeps the style a box has of its own, drops fields (words written over the wire make none) and turns
  line breaks into spaces (D1212).
- Typing in a box is not a table method: `edit_plan` in `composes.py` goes to `_box_plan` when an id is a box's. That
  keeps one way to write (`replace_text`, `replace_words`) for people and for the model.
- The event of a structure change is the kernel's `TablesChanged` (`{type: "table", id, definition}`), the whole table;
  typing in a box is the ordinary `text` event with the box's id as `block`. The hub forwards both unchanged.

## Search

`claudia_composes/search.py`: the kind `table`, row by row, covered boxes skipped, the place `{block, table, row, col}`.
`block` is the paragraph the table hangs from, so a client can take a person there. A selection finds a table only if it
hangs from inside the selection. A replacement is typing and deleting in the box; a box somebody holds is skipped and the
holder named (the box's `TableRegion`).

## The AI

- `apps.MODEL_METHODS["composes"]` has `TABLE_METHODS`; `SUGGEST_METHODS` has none of them.
- `DocumentLens`: `tables` is a look method; `orient` names the tables (id, name, size, header, where it hangs) and how
  boxes are named, only if the text has one; `show("tables")` writes a table with the row and column ids, the totals
  and the merges (40 rows, 60 characters a box); the recorder re-reads a table that a request touched, however it was
  touched (a structure change or the words of a box), and names one that went.
- `replace_words` and `_paragraph` in `composes_words.py` know box ids, so the model quotes words in a box like in a
  paragraph.

## What is deliberately not here

- Boxes in `reading_order` (list items, outline, headings in boxes): D1212.
- A suggestion of a table change: there is no suggestion of a structure yet, so in *suggest* mode the AI makes none.
- Linked tables (E9.33).
