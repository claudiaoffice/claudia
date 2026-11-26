import { describe, expect, it } from 'vitest'
import { fileToBase64, formatByteSize, imageByteSize, imageDataUrl, NEW_OBJECT_CAP, offersPathChoice, pictureSize, sourcePathToSend } from '~/lib/images'

describe('fileToBase64', () => {
  it('encodes a small file exactly as the bytes it holds', async () => {
    const file = new File([new Uint8Array([0, 1, 2, 253, 254, 255])], 'tiny.bin')
    expect(await fileToBase64(file)).toBe(Buffer.from([0, 1, 2, 253, 254, 255]).toString('base64'))
  })

  it('round-trips a file large enough to cross the chunking boundary', async () => {
    const bytes = new Uint8Array(0x8000 * 2 + 37)
    for (let i = 0; i < bytes.length; i++) bytes[i] = i % 256
    const file = new File([bytes], 'big.bin')
    expect(await fileToBase64(file)).toBe(Buffer.from(bytes).toString('base64'))
  })

  it('encodes an empty file as an empty string', async () => {
    const file = new File([], 'empty.bin')
    expect(await fileToBase64(file)).toBe('')
  })
})

describe('imageDataUrl', () => {
  it('maps every supported format to its MIME type', () => {
    expect(imageDataUrl({ format: 'jpeg', data: 'AA==' })).toBe('data:image/jpeg;base64,AA==')
    expect(imageDataUrl({ format: 'gif', data: 'AA==' })).toBe('data:image/gif;base64,AA==')
    expect(imageDataUrl({ format: 'bmp', data: 'AA==' })).toBe('data:image/bmp;base64,AA==')
    expect(imageDataUrl({ format: 'svg', data: 'AA==' })).toBe('data:image/svg+xml;base64,AA==')
  })

  it('falls back to a generic type for a format it does not know, rather than guessing one', () => {
    expect(imageDataUrl({ format: 'tiff', data: 'AA==' })).toBe('data:application/octet-stream;base64,AA==')
  })
})

describe('imageByteSize', () => {
  it('recovers the exact byte count base64 holds, padding and all', () => {
    expect(imageByteSize(Buffer.from([1, 2, 3]).toString('base64'))).toBe(3) // one '=' of padding
    expect(imageByteSize(Buffer.from([1, 2]).toString('base64'))).toBe(2) // two '==' of padding
    expect(imageByteSize(Buffer.from([1, 2, 3, 4]).toString('base64'))).toBe(4) // no padding
    expect(imageByteSize('')).toBe(0)
  })
})

describe('formatByteSize', () => {
  it('shows a small count in bytes', () => {
    expect(formatByteSize(0)).toBe('0 B')
    expect(formatByteSize(512)).toBe('512 B')
  })

  it('rounds to the nearest whole kilobyte once it is big enough for one', () => {
    expect(formatByteSize(1024)).toBe('1 KB')
    expect(formatByteSize(88_234)).toBe('86 KB')
  })

  it('shows one decimal place once it is big enough for a megabyte', () => {
    expect(formatByteSize(1_572_864)).toBe('1.5 MB')
  })
})

describe('pictureSize', () => {
  it('is as high as asked, as wide as its own proportions make it', () => {
    expect(pictureSize(2, 240, 480)).toEqual({ w: 480, h: 240 })
    expect(pictureSize(0.5, 240, 480)).toEqual({ w: 120, h: 240 })
  })
  it('is narrowed to the width it may have, and keeps its proportions (the server allows a pixel of difference)', () => {
    const size = pictureSize(4, 240, 480)
    expect(size).toEqual({ w: 480, h: 120 })
    for (const aspect of [2.1, 3.3, 5.7, 9.99]) {
      const wide = pictureSize(aspect, 240, 480)
      expect(wide.w).toBeLessThanOrEqual(480)
      expect(Math.abs(wide.w - aspect * wide.h)).toBeLessThanOrEqual(1) // the server's own tolerance (ASPECT_TOLERANCE)
    }
  })
})

describe('pictureSize with the picture\'s own size (the owner, 2026-11-19: no bigger than 420 × 240 or the picture)', () => {
  it('shows a small picture at its own size', () => {
    expect(pictureSize(2, 240, 420, { width: 100, height: 50 })).toEqual({ w: 100, h: 50 })
  })
  it('shows a big picture within the cap', () => {
    expect(pictureSize(2, NEW_OBJECT_CAP.h, NEW_OBJECT_CAP.w, { width: 4000, height: 2000 })).toEqual({ w: 420, h: 210 })
    expect(pictureSize(0.5, NEW_OBJECT_CAP.h, NEW_OBJECT_CAP.w, { width: 2000, height: 4000 })).toEqual({ w: 120, h: 240 })
  })
  it('is never smaller than an object may be, and keeps the proportions', () => {
    expect(pictureSize(1, 240, 420, { width: 8, height: 8 })).toEqual({ w: 20, h: 20 })
    const flat = pictureSize(10, 240, 420, { width: 30, height: 3 })
    expect(flat.h).toBeGreaterThanOrEqual(20)
    expect(Math.abs(flat.w - 10 * flat.h)).toBeLessThanOrEqual(1)
  })
})

describe("Insert ▸ Image's \"Don't save the path\" (SEC-27)", () => {
  it('is offered only when the path of the picked file is known', () => {
    expect(offersPathChoice('/home/ann/Pictures/chart.png')).toBe(true)
    expect(offersPathChoice(null)).toBe(false) // a plain browser never knows it
    expect(offersPathChoice('')).toBe(false)
  })

  it('sends the path when the box is left unticked, an empty one when it is ticked', () => {
    expect(sourcePathToSend('/home/ann/Pictures/chart.png', false)).toBe('/home/ann/Pictures/chart.png')
    expect(sourcePathToSend('/home/ann/Pictures/chart.png', true)).toBe('')
    expect(sourcePathToSend(null, false)).toBeNull()
  })
})
