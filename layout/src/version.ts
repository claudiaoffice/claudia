/**
 * The version of the layout rules. It is part of every display list and changes whenever a rule changes in a way
 * that can move a glyph, so a layout made by another version is never mistaken for this one's.
 */
export const LAYOUT_VERSION = 'claudia-layout-7'
// 2: paragraphs are broken by Knuth and Plass with hyphenation (D912); SVG pictures are drawn (D914)
// 3: a shape's label is inset 8 px and centred vertically; page numbers are 9 pt (D918); slides are laid out (D917)
// 4: list items are moved in and their markers drawn (E9.21); a heading keeps with the next paragraph by its level (E9.22)
// 5: a numbered heading's number hangs before it; the words of a text box or shape follow their marker (E9.22)
// 6: an agenda's places are right-aligned on its lines with a dot leader (E9.31)
// 7: a table of contents is laid out with its pages, a leader and links; the PDF has links and bookmarks (E9.31, step F)
