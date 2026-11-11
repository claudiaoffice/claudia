// The server's `style_model` (D303, D304, D316), as a session loads it.
export const STYLE_MODEL = {
  facets: {
    text: ['font-family', 'font-size', 'font-weight', 'font-style', 'text-decoration', 'color', 'letter-spacing', 'word-spacing'],
    paragraph: ['text-align', 'line-height', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left'],
    box: ['background-color', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'border-top', 'border-right', 'border-bottom', 'border-left', 'vertical-align', 'white-space'],
    outline: ['fill', 'stroke', 'stroke-width'],
  },
  kinds: { paragraph: ['text', 'paragraph', 'box'], box: ['box'], outline: ['outline'] },
  slots: {
    paragraph: [{ name: 'paragraph', reads: ['text', 'paragraph', 'box'], kind: 'paragraph', takes: ['paragraph'] }],
    text: [
      { name: 'box', reads: ['box'], kind: 'box', takes: ['paragraph', 'box'] },
      { name: 'words', reads: ['text', 'paragraph'], kind: 'paragraph', takes: ['paragraph'] },
    ],
    shape: [
      { name: 'outline', reads: ['outline'], kind: 'outline', takes: ['outline'] },
      { name: 'label', reads: ['text', 'paragraph'], kind: 'paragraph', takes: ['paragraph'] },
    ],
    image: [{ name: 'box', reads: [], kind: 'box', takes: ['box'] }],
    diagram: [{ name: 'box', reads: ['box'], kind: 'box', takes: ['paragraph', 'box'] }],
    cell: [
      { name: 'box', reads: ['box'], kind: 'box', takes: ['paragraph', 'box'] },
      { name: 'words', reads: ['text', 'paragraph'], kind: 'paragraph', takes: ['paragraph'] },
    ],
  },
  targets: ['object'],
}
