/**
 * `@claudia/layout`: deterministic layout for the three claudia apps.
 *
 * - **Fonts and shaping** (`fonts/`): font files by SHA-256, faces at axis locations, HarfBuzz as WebAssembly,
 *   picking fonts from a server's catalogue the way CSS does.
 * - **Paragraph to lines** (`text/`): one style per paragraph, UAX #14 breaks and hyphenation by TeX's patterns,
 *   lines chosen for the whole paragraph by Knuth and Plass, justification in whole mpt; CSS styles resolved to
 *   integers.
 * - **Box clipping** (`text/box`): text in a box of fixed size, cut at the border (D182).
 * - **Flow pagination** (`flow/`): paragraphs into pages of any paper size, with orphans, widows and keep-with-next.
 * - **Display list** (`display/`) and **PDF writer** (`pdf/`): glyph runs, paths (colours and gradients) and
 *   images, transformed, clipped and made transparent in groups, drawn to a PDF.
 * - **SVG** (`svg/`): any SVG picture drawn as display items, for every app.
 *
 * Everything is pure ES2022: no DOM, no Node API, no clock. The caller loads bytes (fonts, WebAssembly, images)
 * and checks their hashes with its own platform; the library computes in integers (mpt = 1/1000 pt) so that every
 * engine gives the same result.
 *
 * @module
 */
export { LAYOUT_VERSION } from './version'
export { canonicalJson } from './canonical'
export { cssLengthToMpt, fmt3, milToMpt, MPT_PER_PT, mulDivRound, umToMpt } from './units'

export { HarfBuzz, HARFBUZZ_PIN, SHAPER_ID, WasmMismatch } from './fonts/harfbuzz'
export type { Extents, Glyph, HarfBuzzWasm, HbFont, Sha256, ShapeOptions, Variations } from './fonts/harfbuzz'
export { faceId, FontSet, UnusableFont } from './fonts/fontset'
export type { FaceMetrics, FaceRef, Shaped } from './fonts/fontset'
export { readSfnt, SfntError, tableDirectory } from './fonts/sfnt'
export type { Axis, SfntInfo, Table } from './fonts/sfnt'
export { DEFAULT_GENERICS, FontResolver, parseFamilies, weightOf } from './fonts/resolve'
export type { Catalogue, CatalogueFont, Generics, Resolution } from './fonts/resolve'

export { BLACK, paragraphStyle } from './text/style'
export type { ParagraphStyle, Rgba, TextAlign } from './text/style'
export { badness, layoutParagraph, MAX_STRETCH } from './text/paragraph'
export type { Line, ParagraphLayout, ParagraphOptions, PlacedWord } from './text/paragraph'
export { HYPHENATION, Hyphenator, pickHyphenation } from './text/hyphenate'
export type { HyphenationEntry } from './text/hyphenate'
export { BASE_FONT_SIZE, boxDecorationFromCss, isPlain, NO_DECORATION, paragraphStyleFromCss, parseColor } from './text/css'
export type { BorderSide, BoxDecoration, Css, StyleFromCss } from './text/css'
export { boxItems, layoutBox } from './text/box'
export type { BoxLayout } from './text/box'

export { contentBox, MIN_CONTENT, MIN_PAGE, PAPER_SIZES, pageGeometry, paperById } from './flow/paper'
export type { Margins, Orientation, PageGeometry, PaperSize } from './flow/paper'
export { flowItems, locate, paginate } from './flow/paginate'
export type { FlowBlock, FlowPage, Fragment, PlacedLine, Spot } from './flow/paginate'

export { fingerprintText, IDENTITY, isGradient, rectPath, walk } from './display/list'
export type { DisplayItem, DisplayList, DisplayPage, GlyphRun, Gradient, GradientStop, GroupItem, ImageItem, Matrix, Paint, PathItem, PathOp, Rect, RunGlyph } from './display/list'
export { decorationItems, insets, lineItems } from './display/text'
export { cosMillionths, sinMillionths } from './display/angles'

export { writePdf } from './pdf/writer'
export type { ImageSource, PdfInfo, PdfOptions } from './pdf/writer'
export { decodePng, ImageError, isPng } from './image/png'
export type { Pixels } from './image/png'
export { isJpeg, readJpeg } from './image/jpeg'
export { decodeGif, isGif } from './image/gif'
export { decodeBmp, isBmp } from './image/bmp'
export { outlinePath, PathError } from './display/svgpath'
export { atan2, sinCos } from './display/detmath'
export type { JpegInfo } from './image/jpeg'

export { drawSvg, parseSvg, SvgError, svgFonts } from './svg/render'
export type { SvgContext, SvgDocument, SvgDrawing } from './svg/render'
export { parseXml, XmlError } from './svg/xml'
export type { XmlElement, XmlNode } from './svg/xml'
export { fromBase64, sha256Hex, utf8Decode, utf8Encode } from './bytes'

export { fontsNeeded, layoutText } from './apps/composes'
export type { ImageInfo, Note, PageSetupData, ShapeOutline, TextBlock, TextDocument, TextLayoutOptions, TextObject, TextPages, TextStyle } from './apps/composes'
