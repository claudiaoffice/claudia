/**
 * Windows bitmaps (BMP) as pixels, for the PDF writer: 1, 4, 8, 24 and 32 bits per pixel, uncompressed or with
 * bit fields, bottom-up or top-down.
 *
 * @module
 */
import { ImageError, type Pixels } from './png'

export const isBmp = (b: Uint8Array): boolean => b[0] === 0x42 && b[1] === 0x4d

/** Decode a BMP; {@link ImageError} for a compressed or damaged one. */
export function decodeBmp(bytes: Uint8Array): Pixels {
  if (!isBmp(bytes) || bytes.length < 54) throw new ImageError('not a BMP file')
  const v = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const offset = v.getUint32(10, true)
  const header = v.getUint32(14, true)
  const width = v.getInt32(18, true)
  const rawHeight = v.getInt32(22, true)
  const bpp = v.getUint16(28, true)
  const compression = header >= 40 ? v.getUint32(30, true) : 0
  const height = Math.abs(rawHeight)
  const topDown = rawHeight < 0
  if (width <= 0 || height === 0 || width * height > 100_000_000) throw new ImageError('a BMP of a size that cannot be read')
  if (compression !== 0 && compression !== 3) throw new ImageError('a compressed BMP; only uncompressed bitmaps are read')
  let masks = [0x00ff0000, 0x0000ff00, 0x000000ff, 0xff000000]
  if (compression === 3) masks = [v.getUint32(54, true), v.getUint32(58, true), v.getUint32(62, true), header >= 56 ? v.getUint32(66, true) : 0]
  const paletteAt = 14 + header + (compression === 3 && header === 40 ? 12 : 0)
  const colours = bpp <= 8 ? v.getUint32(46, true) || 1 << bpp : 0
  const stride = Math.ceil((width * bpp) / 32) * 4
  const rgb = new Uint8Array(width * height * 3)
  const alpha = new Uint8Array(width * height).fill(255)
  let hasAlpha = false
  const channel = (value: number, mask: number) => {
    if (!mask) return 0
    let shift = 0
    while (((mask >>> shift) & 1) === 0) shift++
    const max = mask >>> shift
    return Math.round((((value & mask) >>> shift) * 255) / max)
  }
  for (let row = 0; row < height; row++) {
    const y = topDown ? row : height - 1 - row
    const line = offset + row * stride
    if (line + Math.ceil((width * bpp) / 8) > bytes.length) throw new ImageError('the BMP is cut off')
    for (let x = 0; x < width; x++) {
      const at = y * width + x
      let r: number, g: number, b: number
      if (bpp <= 8) {
        const bit = x * bpp
        const idx = (bytes[line + (bit >> 3)]! >> (8 - bpp - (bit & 7))) & ((1 << bpp) - 1)
        if (idx >= colours) throw new ImageError('a colour index outside the palette')
        b = bytes[paletteAt + idx * 4]!
        g = bytes[paletteAt + idx * 4 + 1]!
        r = bytes[paletteAt + idx * 4 + 2]!
      } else if (bpp === 24) {
        b = bytes[line + x * 3]!
        g = bytes[line + x * 3 + 1]!
        r = bytes[line + x * 3 + 2]!
      } else if (bpp === 32) {
        const value = v.getUint32(line + x * 4, true)
        r = channel(value, masks[0]!)
        g = channel(value, masks[1]!)
        b = channel(value, masks[2]!)
        if (masks[3]) {
          alpha[at] = channel(value, masks[3])
          if (alpha[at] !== 255) hasAlpha = true
        }
      } else throw new ImageError(`a BMP with ${bpp} bits per pixel cannot be read`)
      rgb[at * 3] = r
      rgb[at * 3 + 1] = g
      rgb[at * 3 + 2] = b
    }
  }
  // a 32-bit BMP whose alpha is all zero means "no alpha"
  if (hasAlpha && alpha.every((a) => a === 0)) hasAlpha = false
  return { width, height, rgb, alpha: hasAlpha ? alpha : null }
}
