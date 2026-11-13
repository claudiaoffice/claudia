/**
 * A small reader for the tables of a TrueType/OpenType file that layout and the PDF writer need: units per em,
 * bounding box, vertical metrics, cap height, italic angle, weight, embedding rights, the PostScript name, advance
 * widths and variation axes. Outlines are never read here; shaping and subsetting are HarfBuzz's job.
 *
 * @module
 */

/** One variation axis of a variable font (`fvar`). Values are in the axis' own units (wght: 100…900). */
export interface Axis {
  tag: string
  min: number
  default: number
  max: number
}

/** What {@link readSfnt} found. All lengths in font units. */
export interface SfntInfo {
  /** `truetype` (glyf outlines) or `cff` (an OpenType file with CFF outlines). */
  outlines: 'truetype' | 'cff'
  unitsPerEm: number
  numGlyphs: number
  bbox: [number, number, number, number]
  ascender: number
  descender: number
  lineGap: number
  capHeight: number
  /** degrees, rounded to an integer */
  italicAngle: number
  weight: number
  /** `OS/2.fsType`; bit 1 (value 2) forbids embedding */
  fsType: number
  fixedPitch: boolean
  postscriptName: string
  axes: Axis[]
  /** the advance width of every glyph id, `numGlyphs` long */
  advances: Uint16Array
}

/** The file is not a font this reader understands; the message says why. */
export class SfntError extends Error {}

/** Where one table of a font file lies: byte offset and length. */
export interface Table {
  offset: number
  length: number
}

function tag(view: DataView, at: number): string {
  return String.fromCharCode(view.getUint8(at), view.getUint8(at + 1), view.getUint8(at + 2), view.getUint8(at + 3))
}

/** The table directory: tag → place in the file. */
export function tableDirectory(bytes: Uint8Array): Map<string, Table> {
  if (bytes.length < 12) throw new SfntError('too short to be a font')
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const version = tag(view, 0)
  if (version === 'wOF2' || version === 'wOFF') throw new SfntError('a WOFF/WOFF2 file; layout needs the TrueType or OpenType file itself')
  if (version !== '\u0000\u0001\u0000\u0000' && version !== 'true' && version !== 'OTTO') throw new SfntError('not a TrueType or OpenType file')
  const count = view.getUint16(4)
  const tables = new Map<string, Table>()
  for (let i = 0; i < count; i++) {
    const at = 12 + i * 16
    if (at + 16 > bytes.length) throw new SfntError('the table directory is cut off')
    const offset = view.getUint32(at + 8)
    const length = view.getUint32(at + 12)
    if (offset + length > bytes.length) throw new SfntError(`table ${tag(view, at)} lies outside the file`)
    tables.set(tag(view, at), { offset, length })
  }
  return tables
}

function fixed(view: DataView, at: number): number {
  return view.getInt32(at) / 65536
}

function postscriptName(view: DataView, name: Table | undefined): string {
  if (!name) return ''
  const count = view.getUint16(name.offset + 2)
  const strings = name.offset + view.getUint16(name.offset + 4)
  let found = ''
  for (let i = 0; i < count; i++) {
    const at = name.offset + 6 + i * 12
    const platform = view.getUint16(at)
    const encoding = view.getUint16(at + 2)
    const id = view.getUint16(at + 6)
    if (id !== 6) continue
    const length = view.getUint16(at + 8)
    const start = strings + view.getUint16(at + 10)
    let s = ''
    if (platform === 3 || platform === 0) {
      for (let k = 0; k + 1 < length; k += 2) s += String.fromCharCode(view.getUint16(start + k))
    } else if (platform === 1 && encoding === 0) {
      for (let k = 0; k < length; k++) s += String.fromCharCode(view.getUint8(start + k))
    } else continue
    if (s) {
      found = s
      if (platform === 3) break
    }
  }
  return found
}

/** Read the tables listed in {@link SfntInfo}; {@link SfntError} if a required one is missing. */
export function readSfnt(bytes: Uint8Array): SfntInfo {
  const tables = tableDirectory(bytes)
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const need = (t: string): Table => {
    const found = tables.get(t)
    if (!found) throw new SfntError(`the font has no ${t} table`)
    return found
  }
  const head = need('head')
  const hhea = need('hhea')
  const maxp = need('maxp')
  const hmtx = need('hmtx')
  const os2 = tables.get('OS/2')
  const post = tables.get('post')
  const unitsPerEm = view.getUint16(head.offset + 18)
  const bbox: [number, number, number, number] = [
    view.getInt16(head.offset + 36),
    view.getInt16(head.offset + 38),
    view.getInt16(head.offset + 40),
    view.getInt16(head.offset + 42),
  ]
  const numGlyphs = view.getUint16(maxp.offset + 4)
  const numberOfHMetrics = view.getUint16(hhea.offset + 34)
  const advances = new Uint16Array(numGlyphs)
  let last = 0
  for (let g = 0; g < numGlyphs; g++) {
    if (g < numberOfHMetrics) last = view.getUint16(hmtx.offset + g * 4)
    advances[g] = last
  }
  let ascender = view.getInt16(hhea.offset + 4)
  let descender = view.getInt16(hhea.offset + 6)
  let lineGap = view.getInt16(hhea.offset + 8)
  let capHeight = Math.round(ascender * 0.7)
  let weight = 400
  let fsType = 0
  if (os2 && os2.length >= 78) {
    weight = view.getUint16(os2.offset + 4)
    fsType = view.getUint16(os2.offset + 8)
    const useTypo = (view.getUint16(os2.offset + 62) & 0x80) !== 0
    if (useTypo) {
      ascender = view.getInt16(os2.offset + 68)
      descender = view.getInt16(os2.offset + 70)
      lineGap = view.getInt16(os2.offset + 72)
    }
    if (view.getUint16(os2.offset) >= 2 && os2.length >= 90) capHeight = view.getInt16(os2.offset + 88)
  }
  const axes: Axis[] = []
  const fvar = tables.get('fvar')
  if (fvar) {
    const axesAt = fvar.offset + view.getUint16(fvar.offset + 4)
    const axisCount = view.getUint16(fvar.offset + 8)
    const axisSize = view.getUint16(fvar.offset + 10)
    for (let i = 0; i < axisCount; i++) {
      const at = axesAt + i * axisSize
      axes.push({ tag: tag(view, at), min: fixed(view, at + 4), default: fixed(view, at + 8), max: fixed(view, at + 12) })
    }
  }
  return {
    outlines: tables.has('glyf') ? 'truetype' : 'cff',
    unitsPerEm,
    numGlyphs,
    bbox,
    ascender,
    descender,
    lineGap,
    capHeight,
    italicAngle: post ? Math.round(fixed(view, post.offset + 4)) : 0,
    weight,
    fsType,
    fixedPitch: post ? view.getUint32(post.offset + 12) !== 0 : false,
    postscriptName: postscriptName(view, tables.get('name')),
    axes,
    advances,
  }
}
