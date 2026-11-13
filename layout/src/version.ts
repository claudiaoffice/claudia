/**
 * The version of the layout rules. It is part of every display list and changes whenever a rule changes in a way
 * that can move a glyph, so a layout made by another version is never mistaken for this one's.
 */
export const LAYOUT_VERSION = 'claudia-layout-2'
// 2: paragraphs are broken by Knuth and Plass with hyphenation (D912); SVG pictures are drawn (D914)
