# Import and export wiring (D450–D469, branch `import-export-wiring`)

The audit (`import-export-coverage-2026-11-14.md`) found functions of the three apps that never reach the formats.
The work goes in slices, each a patch against the branch.

## Slice 1 — unwritten changes and loss lists (D450–D452)
`claudia_odf_io.unwritten_changes` compares the facets of a model before and after and reports the ones a converter
does not write; each converter has a `*_WRITTEN` set that shrinks as slices land.

## Slice 2 — composes lists (D453)
* odt: `_odt_lists.py` reads `text:list` trees as items (`ListReading`), writes them (`ListFlow`, `ListNames`) and
  makes `text:list-style` elements. The patch (`_Patch._plan`) decides for each block whether its element is kept,
  written again as part of a "region" (a list whose items changed), or new.
* docx: `_docx_lists.py` (`Numbering`, `read_lists`, `ListWriter`). python-docx cannot make a numbering part, so
  `numbering_in(create=True)` loads one.
* Found on the way: untouched pieces of a list that a patch continues need an `xml:id`, which is only known after the
  first piece was placed; hence the late serialisation in `XmlPart`.
* Property tests (`test_odt_lists.py`, `test_docx_lists.py`): random edits of items and definitions; the file must say
  the same lists as the model, and what was not touched must be unchanged.

## Slice 3 — composes page, language, styles, palette (D454, D455)
* `_layout.py`: units and language tags shared by both formats. `_odt_setup.py` / `_docx_setup.py` read, write and
  patch the page and the language (the odt patch edits the first master page and the default style in place; the docx
  writes the first section and the document defaults and owns the parts that change).
* `_style_look.py` turns the CSS a style sets (palette roles already replaced) into a `Look` in points and
  `#RRGGBB`; what it cannot say goes in `Look.unsaid`. `_odt_styles.py` (`StyleNames`, `style_xml`) and
  `_docx_styles.py` (`WordNames`, `write_styles`) write it. A style that is written replaces what the file had of it;
  a custom style never takes a name a file already has.
* The patch writes a style again only when its `Look` (or parent) differs from the baseline's, a new style when a
  paragraph needs it. Palette roles are not in the files, so a changed colour rewrites the styles that name it.
* Found on the way: the server's odt patch lacked `info` and `change_times` (fixed); a default model exports without
  a loss, so docx hyphenation is the document setting and padding is only a loss for a style with no border at all.
