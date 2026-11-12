/**
 * The first frame of a GIF as pixels, for the PDF writer (an animated GIF prints still). Pure TypeScript: LZW,
 * interlacing and the transparent colour.
 *
 * @module
 */
import { ImageError, type Pixels } from './png'

export const isGif = (b: Uint8Array): boolean => b[0] === 0x47 && b[1] === 0x49 && b[2] === 0x46 && b[3] === 0x38

function lzw(data: Uint8Array, minSize: number, pixels: number): Uint8Array {
  const out = new Uint8Array(pixels)
  const clear = 1 << minSize
  const end = clear + 1
  const prefix = new Int32Array(4096)
  const suffix = new Uint8Array(4096)
  const first = new Uint8Array(4096)
  const stack = new Uint8Array(4097)
  let size = minSize + 1
  let next = end + 1
  let prev = -1
  let bits = 0
  let acc = 0
  let o = 0
  for (let i = 0; i < clear; i++) {
    prefix[i] = -1
    suffix[i] = i
    first[i] = i
  }
  for (let p = 0; p < data.length && o < pixels; ) {
    while (bits < size && p < data.length) {
      acc |= data[p++]! << bits
      bits += 8
    }
    if (bits < size) break
    const code = acc & ((1 << size) - 1)
    acc >>>= size
    bits -= size
    if (code === clear) {
      size = minSize + 1
      next = end + 1
      prev = -1
      continue
    }
    if (code === end) break
    let c = code
    let top = 0
    if (prev === -1) {
      if (code >= next) throw new ImageError('a damaged GIF')
      out[o++] = suffix[code]!
      prev = code
      continue
    }
    if (code > next) throw new ImageError('a damaged GIF')
    if (code === next) {
      stack[top++] = first[prev]!
      c = prev
    }
    while (c >= clear) {
      stack[top++] = suffix[c]!
      c = prefix[c]!
    }
    stack[top++] = c
    const lead = c
    while (top > 0 && o < pixels) out[o++] = stack[--top]!
    if (next < 4096) {
      prefix[next] = prev
      suffix[next] = lead
      first[next] = first[prev]!
      next++
      if (next === 1 << size && size < 12) size++
    }
    prev = code
  }
  return out
}

/** Decode the first image of a GIF; {@link ImageError} if it is damaged or not a GIF. */
export function decodeGif(bytes: Uint8Array): Pixels {
  if (!isGif(bytes) || bytes.length < 13) throw new ImageError('not a GIF file')
  const width = bytes[6]! | (bytes[7]! << 8)
  const height = bytes[8]! | (bytes[9]! << 8)
  if (!width || !height || width * height > 100_000_000) throw new ImageError('a GIF of a size that cannot be read')
  const flags = bytes[10]!
  let pos = 13
  let global: Uint8Array | null = null
  if (flags & 0x80) {
    const n = 3 << ((flags & 7) + 1)
    global = bytes.subarray(pos, pos + n)
    pos += n
  }
  let transparent = -1
  while (pos < bytes.length) {
    const block = bytes[pos++]
    if (block === 0x21) {
      const label = bytes[pos++]
      if (label === 0xf9 && bytes[pos] === 4) {
        if (bytes[pos + 1]! & 1) transparent = bytes[pos + 4]!
      }
      while (pos < bytes.length && bytes[pos] !== 0) pos += bytes[pos]! + 1
      pos++
    } else if (block === 0x2c) {
      const left = bytes[pos]! | (bytes[pos + 1]! << 8)
      const top = bytes[pos + 2]! | (bytes[pos + 3]! << 8)
      const w = bytes[pos + 4]! | (bytes[pos + 5]! << 8)
      const h = bytes[pos + 6]! | (bytes[pos + 7]! << 8)
      const f = bytes[pos + 8]!
      pos += 9
      let table = global
      if (f & 0x80) {
        const n = 3 << ((f & 7) + 1)
        table = bytes.subarray(pos, pos + n)
        pos += n
      }
      if (!table) throw new ImageError('a GIF without colours')
      const minSize = bytes[pos++]!
      if (minSize < 2 || minSize > 11) throw new ImageError('a damaged GIF')
      const parts: Uint8Array[] = []
      let total = 0
      while (pos < bytes.length && bytes[pos] !== 0) {
        const n = bytes[pos]!
        parts.push(bytes.subarray(pos + 1, pos + 1 + n))
        total += n
        pos += n + 1
      }
      const data = new Uint8Array(total)
      let o = 0
      for (const p of parts) {
        data.set(p, o)
        o += p.length
      }
      const indices = lzw(data, minSize, w * h)
      const rows: number[] = []
      if (f & 0x40) for (const [start, step] of [[0, 8], [4, 8], [2, 4], [1, 2]] as const) for (let y = start; y < h; y += step) rows.push(y)
      else for (let y = 0; y < h; y++) rows.push(y)
      const rgb = new Uint8Array(width * height * 3).fill(255)
      const alpha = new Uint8Array(width * height)
      rows.forEach((y, r) => {
        for (let x = 0; x < w; x++) {
          const tx = left + x
          const ty = top + y
          if (tx >= width || ty >= height) continue
          const idx = indices[r * w + x]!
          const at = ty * width + tx
          rgb[at * 3] = table![idx * 3] ?? 0
          rgb[at * 3 + 1] = table![idx * 3 + 1] ?? 0
          rgb[at * 3 + 2] = table![idx * 3 + 2] ?? 0
          alpha[at] = idx === transparent ? 0 : 255
        }
      })
      const opaque = alpha.every((a) => a === 255)
      return { width, height, rgb, alpha: opaque ? null : alpha }
    } else if (block === 0x3b) break
    else throw new ImageError('a damaged GIF')
  }
  throw new ImageError('a GIF without an image')
}
