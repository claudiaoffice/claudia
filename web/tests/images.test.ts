import { describe, expect, it } from 'vitest'
import { fileToBase64, formatByteSize, imageByteSize, imageDataUrl } from '~/lib/images'

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
