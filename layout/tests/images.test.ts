import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { readJpeg } from '../src/image/jpeg'
import { decodeBmp } from '../src/image/bmp'
import { decodeGif } from '../src/image/gif'
import { decodePng, ImageError } from '../src/image/png'
import { here } from './helpers'

const file = (name: string) => new Uint8Array(readFileSync(join(here, 'images', name)))
const expected: Record<string, { w: number; h: number; rgba: number[] }> = JSON.parse(readFileSync(join(here, 'images', 'expected.json'), 'utf8'))

const decoders = { png: decodePng, gif: decodeGif, bmp: decodeBmp } as const

describe('PNG, GIF and BMP', () => {
  for (const name of Object.keys(expected)) {
    it(`decodes ${name} to the same pixels as Pillow`, () => {
      const px = decoders[name.split('.').pop() as keyof typeof decoders](file(name))
      const e = expected[name]!
      expect([px.width, px.height]).toEqual([e.w, e.h])
      for (let i = 0; i < e.w * e.h; i++) {
        expect([px.rgb[3 * i], px.rgb[3 * i + 1], px.rgb[3 * i + 2]]).toEqual(e.rgba.slice(4 * i, 4 * i + 3))
        expect(px.alpha ? px.alpha[i] : 255).toBe(e.rgba[4 * i + 3])
      }
    })
  }
  it('says when an image is fully opaque', () => {
    expect(decodePng(file('rgb.png')).alpha).toBeNull()
    expect(decodePng(file('rgba.png')).alpha).not.toBeNull()
  })
  it('refuses what is not an image of its kind, or is cut off', () => {
    expect(() => decodeGif(file('rgb.png'))).toThrow(ImageError)
    expect(() => decodeBmp(file('rgb.png'))).toThrow(ImageError)
    expect(() => decodePng(file('photo.jpg'))).toThrow(ImageError)
    expect(() => decodePng(file('rgb.png').slice(0, 40))).toThrow(ImageError)
  })
})

describe('JPEG', () => {
  it('reads size and components', () => {
    expect(readJpeg(file('photo.jpg'))).toMatchObject({ width: 7, height: 5, components: 3 })
    expect(readJpeg(file('cmyk.jpg'))).toMatchObject({ width: 4, height: 3, components: 4, adobe: true })
  })
})
