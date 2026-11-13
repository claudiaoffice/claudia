/**
 * A PNG decoder for the PDF writer: any PNG (every colour type, bit depth and Adam7 interlacing) to 8-bit RGB plus
 * an optional 8-bit alpha plane. Pure TypeScript over fflate's inflate, so the same file gives the same pixels
 * everywhere.
 *
 * @module
 */
import { unzlibSync } from 'fflate'

export interface Pixels {
  width: number
  height: number
  /** width × height × 3 bytes */
  rgb: Uint8Array
  /** width × height bytes, or `null` when every pixel is opaque */
  alpha: Uint8Array | null
}

export class ImageError extends Error {}

const SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10]
const ADAM7 = [
  [0, 0, 8, 8],
  [4, 0, 8, 8],
  [0, 4, 4, 8],
  [2, 0, 4, 4],
  [0, 2, 2, 4],
  [1, 0, 2, 2],
  [0, 1, 1, 2],
] as const

const CHANNELS: Record<number, number> = { 0: 1, 2: 3, 3: 1, 4: 2, 6: 4 }

/** True if `bytes` start like a PNG. */
export const isPng = (bytes: Uint8Array): boolean => SIGNATURE.every((b, i) => bytes[i] === b)

function paeth(a: number, b: number, c: number): number {
  const p = a + b - c
  const pa = Math.abs(p - a)
  const pb = Math.abs(p - b)
  const pc = Math.abs(p - c)
  return pa <= pb && pa <= pc ? a : pb <= pc ? b : c
}

/** Decode a PNG; {@link ImageError} if it is damaged or not a PNG. */
export function decodePng(bytes: Uint8Array): Pixels {
  if (!isPng(bytes)) throw new ImageError('not a PNG file')
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  let pos = 8
  let width = 0
  let height = 0
  let depth = 0
  let type = 0
  let interlace = 0
  let palette: Uint8Array | null = null
  let trns: Uint8Array | null = null
  const idat: Uint8Array[] = []
  while (pos + 8 <= bytes.length) {
    const length = view.getUint32(pos)
    const kind = String.fromCharCode(...bytes.subarray(pos + 4, pos + 8))
    const data = bytes.subarray(pos + 8, pos + 8 + length)
    if (data.length !== length) throw new ImageError('the PNG is cut off')
    if (kind === 'IHDR') {
      width = view.getUint32(pos + 8)
      height = view.getUint32(pos + 12)
      depth = data[8]!
      type = data[9]!
      interlace = data[12]!
    } else if (kind === 'PLTE') palette = data
    else if (kind === 'tRNS') trns = data
    else if (kind === 'IDAT') idat.push(data)
    else if (kind === 'IEND') break
    pos += 12 + length
  }
  const channels = CHANNELS[type]
  if (!width || !height || !channels || ![1, 2, 4, 8, 16].includes(depth)) throw new ImageError('a PNG of a kind that cannot be read')
  if (width * height > 100_000_000) throw new ImageError('the image is too large')
  let total = 0
  for (const d of idat) total += d.length
  const packed = new Uint8Array(total)
  let o = 0
  for (const d of idat) {
    packed.set(d, o)
    o += d.length
  }
  let raw: Uint8Array
  try {
    raw = unzlibSync(packed)
  } catch {
    throw new ImageError('the PNG data cannot be unpacked')
  }
  const bpp = Math.max(1, (channels * depth) >> 3) // bytes per pixel for filtering
  const samples = new Uint16Array(width * height * channels) // samples at full depth
  let at = 0
  const pass = (x0: number, y0: number, dx: number, dy: number) => {
    const w = Math.ceil((width - x0) / dx)
    const h = Math.ceil((height - y0) / dy)
    if (w <= 0 || h <= 0) return
    const stride = Math.ceil((w * channels * depth) / 8)
    let prev = new Uint8Array(stride)
    for (let row = 0; row < h; row++) {
      const filter = raw[at++]
      const line = raw.slice(at, at + stride)
      if (line.length !== stride || filter === undefined) throw new ImageError('the PNG data is short')
      at += stride
      for (let i = 0; i < stride; i++) {
        const a = i >= bpp ? line[i - bpp]! : 0
        const b = prev[i]!
        const c = i >= bpp ? prev[i - bpp]! : 0
        let v = line[i]!
        if (filter === 1) v += a
        else if (filter === 2) v += b
        else if (filter === 3) v += (a + b) >> 1
        else if (filter === 4) v += paeth(a, b, c)
        else if (filter !== 0) throw new ImageError('an unknown PNG filter')
        line[i] = v & 255
      }
      prev = line
      const y = y0 + row * dy
      for (let col = 0; col < w; col++) {
        const x = x0 + col * dx
        for (let ch = 0; ch < channels; ch++) {
          const n = col * channels + ch
          let s: number
          if (depth === 8) s = line[n]!
          else if (depth === 16) s = (line[2 * n]! << 8) | line[2 * n + 1]!
          else {
            const bit = n * depth
            s = (line[bit >> 3]! >> (8 - depth - (bit & 7))) & ((1 << depth) - 1)
          }
          samples[(y * width + x) * channels + ch] = s
        }
      }
    }
  }
  if (interlace) for (const [x0, y0, dx, dy] of ADAM7) pass(x0, y0, dx, dy)
  else pass(0, 0, 1, 1)

  const n = width * height
  const rgb = new Uint8Array(n * 3)
  const alpha = new Uint8Array(n)
  let opaque = true
  const max = (1 << depth) - 1
  const to8 = (s: number) => (depth === 16 ? s >> 8 : depth === 8 ? s : Math.round((s * 255) / max))
  const key = trns && type !== 3 ? (type === 0 ? [(trns[0]! << 8) | trns[1]!] : [(trns[0]! << 8) | trns[1]!, (trns[2]! << 8) | trns[3]!, (trns[4]! << 8) | trns[5]!]) : null
  for (let i = 0; i < n; i++) {
    const s = i * channels
    let r: number, g: number, b: number, a = 255
    if (type === 3) {
      const idx = samples[s]!
      if (!palette || idx * 3 + 2 >= palette.length) throw new ImageError('a palette index outside the palette')
      r = palette[idx * 3]!
      g = palette[idx * 3 + 1]!
      b = palette[idx * 3 + 2]!
      if (trns && idx < trns.length) a = trns[idx]!
    } else if (type === 0 || type === 4) {
      r = g = b = to8(samples[s]!)
      if (type === 4) a = to8(samples[s + 1]!)
      else if (key && samples[s] === key[0]) a = 0
    } else {
      r = to8(samples[s]!)
      g = to8(samples[s + 1]!)
      b = to8(samples[s + 2]!)
      if (type === 6) a = to8(samples[s + 3]!)
      else if (key && samples[s] === key[0] && samples[s + 1] === key[1] && samples[s + 2] === key[2]) a = 0
    }
    rgb[i * 3] = r
    rgb[i * 3 + 1] = g
    rgb[i * 3 + 2] = b
    alpha[i] = a
    if (a !== 255) opaque = false
  }
  return { width, height, rgb, alpha: opaque ? null : alpha }
}
