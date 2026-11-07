// file-dialog.ts is the fix for the owner's third real-run bug: clicking Insert Image's "Choose a file..." did
// nothing at all on her Mac. The pure half -- turning an <input accept="..."> into a showOpenDialog filter, and a
// chosen path into a MIME type and a filename -- is tested here. The live half (installFileDialogBridge's capture
// click listener, Neutralino.os.showOpenDialog, Neutralino.filesystem.readBinaryFile, DataTransfer) needs a real
// DOM and a real Neutralino, like page-bridge.ts's installBridge() -- see this module's top comment.
import { describe, expect, it } from 'vitest'
import { basename, guessMimeType, parseAcceptExtensions } from '../src/file-dialog.js'

describe('parseAcceptExtensions', () => {
  it("keeps only the bare '.ext' tokens, dropping MIME-type tokens", () => {
    expect(parseAcceptExtensions('image/jpeg,image/gif,image/bmp,image/svg+xml,.jpg,.jpeg,.gif,.bmp,.svg')).toEqual([
      'jpg',
      'jpeg',
      'gif',
      'bmp',
      'svg',
    ])
  })

  it('lower-cases extensions and drops the leading dot', () => {
    expect(parseAcceptExtensions('.JPG,.Png')).toEqual(['jpg', 'png'])
  })

  it('dedupes repeated extensions, keeping the first occurrence', () => {
    expect(parseAcceptExtensions('.jpg,.jpeg,.jpg')).toEqual(['jpg', 'jpeg'])
  })

  it('returns an empty list for an accept attribute with no bare extension (MIME types only)', () => {
    expect(parseAcceptExtensions('image/jpeg,image/png')).toEqual([])
  })

  it('returns an empty list for an empty or missing accept attribute', () => {
    expect(parseAcceptExtensions('')).toEqual([])
  })
})

describe('guessMimeType', () => {
  it.each([
    ['photo.jpg', 'image/jpeg'],
    ['photo.JPEG', 'image/jpeg'],
    ['icon.svg', 'image/svg+xml'],
    ['scan.bmp', 'image/bmp'],
    ['animation.gif', 'image/gif'],
    ['picture.png', 'image/png'],
  ])('maps %s to %s', (path, mime) => {
    expect(guessMimeType(path)).toBe(mime)
  })

  it('falls back to a generic type for an unknown or missing extension', () => {
    expect(guessMimeType('README')).toBe('application/octet-stream')
    expect(guessMimeType('data.xyz')).toBe('application/octet-stream')
  })
})

describe('basename', () => {
  it('takes the last path segment of a Mac path', () => {
    expect(basename('/Users/matt/Pictures/sunset.jpg')).toBe('sunset.jpg')
  })

  it('returns the whole string when there is no slash', () => {
    expect(basename('sunset.jpg')).toBe('sunset.jpg')
  })
})
