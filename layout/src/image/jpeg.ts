/**
 * What the PDF writer must know about a JPEG to embed it as it is (no decoding): size, colour components, and
 * whether it is an Adobe CMYK file with inverted values.
 *
 * @module
 */
import { ImageError } from './png'

export interface JpegInfo {
  width: number
  height: number
  components: 1 | 3 | 4
  /** Adobe APP14 marker: CMYK stored inverted, as Photoshop writes it */
  adobe: boolean
}

export const isJpeg = (bytes: Uint8Array): boolean => bytes[0] === 0xff && bytes[1] === 0xd8

/** Read the frame header of a JPEG; {@link ImageError} if there is none. */
export function readJpeg(bytes: Uint8Array): JpegInfo {
  if (!isJpeg(bytes)) throw new ImageError('not a JPEG file')
  let pos = 2
  let adobe = false
  while (pos + 4 <= bytes.length) {
    if (bytes[pos] !== 0xff) {
      pos++
      continue
    }
    const marker = bytes[pos + 1]!
    if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7) || marker === 0xff) {
      pos += marker === 0xff ? 1 : 2
      continue
    }
    const length = (bytes[pos + 2]! << 8) | bytes[pos + 3]!
    if (marker === 0xee && String.fromCharCode(...bytes.subarray(pos + 4, pos + 9)) === 'Adobe') adobe = true
    // SOF0…SOF15 except DHT (C4), JPG (C8) and DAC (CC)
    if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
      const height = (bytes[pos + 5]! << 8) | bytes[pos + 6]!
      const width = (bytes[pos + 7]! << 8) | bytes[pos + 8]!
      const components = bytes[pos + 9]!
      if (!width || !height || ![1, 3, 4].includes(components)) throw new ImageError('a JPEG of a kind that cannot be embedded')
      return { width, height, components: components as 1 | 3 | 4, adobe }
    }
    if (marker === 0xda) break
    pos += 2 + length
  }
  throw new ImageError('the JPEG has no frame header')
}
