Recipes for this app. Adapt the examples to what was asked; do not copy their values.

## Add a slide
Uses: add_slide
The new slide is empty and last. The answer holds its id: use that id to put things on it.
```commands
[{"method": "add_slide", "params": {}}]
```

## Write words in a text box
Uses: add_object, set_text
A slide is 1600 wide and 900 high; x and y are the top left corner. Put a text box with the words in it; to change the words of an object later, set_text with its id.
```commands
[{"method": "add_object", "params": {"slide": "s1", "kind": "text", "x": 160, "y": 120, "w": 1280, "h": 160, "text": "Agenda"}}]
```

## Draw a shape
Uses: add_object
`kind` is "shape" and `shape` the id of an outline that shapes lists: never make one up. A circle keeps its proportions, so give it the same width and height.
```commands
[{"method": "add_object", "params": {"slide": "s1", "kind": "shape", "shape": "circle", "x": 600, "y": 300, "w": 400, "h": 400}}]
```

## Speaker notes
Uses: set_slide_notes
Notes are Markdown, shown to the speaker only. An empty text clears them.
```commands
[{"method": "set_slide_notes", "params": {"slide": "s1", "notes": "Welcome everyone. Introduce the agenda."}}]
```

## Move and resize
Uses: move_object, resize_object
move_object changes the top left corner only. resize_object takes the corner too, with the new width and height.
```commands
[{"method": "move_object", "params": {"id": "o1", "x": 200, "y": 150}}]
```
