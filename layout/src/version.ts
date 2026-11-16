/**
 * The version of the layout rules. It is part of every display list and changes whenever a rule changes in a way
 * that can move a glyph, so a layout made by another version is never mistaken for this one's.
 */
export const LAYOUT_VERSION = 'claudia-layout-4'
// 2: paragraphs are broken by Knuth and Plass with hyphenation (D912); SVG pictures are drawn (D914)
// 3: a shape's label is inset 8 px and centred vertically; page numbers are 9 pt (D918); slides are laid out (D917)
// 4: list items are moved in and their markers drawn (E9.21); a heading keeps with the next paragraph by its level (E9.22)
