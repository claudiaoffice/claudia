Recipes for this app. Adapt the examples to what was asked; do not copy their values.

## Write text into an empty document
Uses: add_paragraphs
Each line of `text` is a paragraph. Leave `after` out to start at the beginning. A style is one of the paragraph styles that styles lists; leave it out for the style that usually follows.
```commands
[{"method": "add_paragraphs", "params": {"text": "Minutes of the meeting\nWe agreed to meet again in May."}}]
```

## Rewrite a passage
Uses: replace_words
`find` is the words to replace, exactly as written in that paragraph (read it first); `text` is what takes their place. An empty `find` replaces the whole paragraph. Use `occurrence` when the words are there more than once.
```commands
[{"method": "replace_words", "params": {"paragraph": "b3", "find": "in order to", "text": "to"}}]
```

## Propose a rewrite
Uses: suggest_words
You may only propose: people accept or reject it. `find` is the words as written, `replacement` what you suggest (empty to propose deleting them), `reason` one short sentence. Leave `replacement` out to leave a remark.
```commands
[{"method": "suggest_words", "params": {"paragraph": "b3", "find": "in order to", "replacement": "to", "reason": "shorter"}}]
```

## Apply a style
Uses: set_style
`style` is the id of a style that styles lists; never make one up. Look at the paragraph first to see the style it has.
```commands
[{"method": "set_style", "params": {"paragraph": "b3", "style": "heading-1"}}]
```

## Build a table
Uses: add_table, set_entries
Give the words as `cells`, a list of rows each a list of texts: the first row is the header. The table is anchored in the paragraph `paragraph` at `offset`, a number of characters from its start (0 is the start). To change words afterwards, set_entries takes [row, column, text] with the ids that tables lists.
```commands
[{"method": "add_table", "params": {"paragraph": "b3", "offset": 0, "cells": [["Name", "Amount"], ["Rent", "900"], ["Food", "300"]]}}]
```
