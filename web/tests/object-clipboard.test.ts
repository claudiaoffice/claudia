import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clipOf, drop, heldFor, holding, objectClipboard, pictureOf, textIsSelected, type ClipboardHost } from '~/lib/object-clipboard'
import type { ImageAsset } from '~/lib/images'
import type { ObjectBody } from '~/lib/objects'

const asset: ImageAsset = { id: 'i1', format: 'png', width: 40, height: 20, animated: false, data: 'QUJD', first_frame: null }
const body = (changes: Partial<ObjectBody> = {}): ObjectBody => ({
  id: 'o1', kind: 'image', w: 200, h: 100, style: '', paragraph: null, ref: 'i1', rotation: 0, snap: false, description: 'A red box', decorative: false,
  imported: { asset: 'i1', alt: 'A red box', imported_by: 'ann', imported_at: '', source: 'file', source_name: 'box.png', source_path: null },
  ...changes,
})

function host(selected: ReturnType<ClipboardHost['selected']>, readonly = false) {
  const log: string[] = []
  const h: ClipboardHost = {
    selected: () => selected,
    readonly: () => readonly,
    remove: async (id) => void log.push(`remove ${id}`),
    add: async (clip) => void log.push(`add ${clip.sourceName}`),
  }
  return { h, log }
}

beforeEach(() => {
  drop()
  vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn(async () => {}), readText: vi.fn(async () => 'A red box') } })
})

describe('clipOf', () => {
  it('holds a picture with its bytes, words and size', () => {
    expect(clipOf(body(), asset)).toMatchObject({ data: 'QUJD', description: 'A red box', sourceName: 'box.png', w: 200, h: 100, marker: 'A red box' })
  })
  it('is nothing for another kind of object, or a picture whose asset has not come', () => {
    expect(clipOf(body({ kind: 'shape' }), asset)).toBeNull()
    expect(clipOf(body(), undefined)).toBeNull()
  })
  it('says something to the system clipboard even for a picture with no words', () => {
    expect(clipOf(body({ description: '', imported: null }), asset)!.marker).not.toBe('')
  })
  it('is imported again without a description if it was decoration', () => {
    expect(pictureOf(clipOf(body({ decorative: true }), asset)!)).toMatchObject({ alt: '', decorative: true, sourcePath: null })
  })
})

describe('the object clipboard', () => {
  it('copies the selected picture, and pastes it while the system clipboard still says so', async () => {
    const { h, log } = host({ id: 'o1', body: body(), asset })
    const c = objectClipboard(h)
    expect(c.copy()).toBe(true)
    expect(holding()).toBe(true)
    expect(await c.paste('A red box')).toBe(true)
    expect(log).toEqual(['add box.png'])
  })
  it('does not paste a picture over text that was copied later', async () => {
    const { h, log } = host({ id: 'o1', body: body(), asset })
    const c = objectClipboard(h)
    c.copy()
    expect(await c.paste('something typed elsewhere')).toBe(false)
    expect(log).toEqual([])
  })
  it('cuts: copies, then removes (and a read-only window neither cuts nor pastes)', async () => {
    const { h, log } = host({ id: 'o1', body: body(), asset })
    expect(await objectClipboard(h).cut()).toBe(true)
    expect(log).toEqual(['remove o1'])
    const ro = host({ id: 'o1', body: body(), asset }, true)
    expect(await objectClipboard(ro.h).cut()).toBe(false)
    expect(await objectClipboard(ro.h).paste('A red box')).toBe(false)
    expect(ro.log).toEqual([])
  })
  it('has nothing to copy when no picture is selected', () => {
    expect(objectClipboard(host(null).h).copy()).toBe(false)
    expect(objectClipboard(host({ id: 's', body: body({ kind: 'shape' }), asset }).h).copy()).toBe(false)
  })
  it('lets a text copy go its way and forgets the picture', () => {
    const { h } = host({ id: 'o1', body: body(), asset })
    const c = objectClipboard(h)
    c.copy()
    const event = { preventDefault: vi.fn(), stopPropagation: vi.fn(), clipboardData: { setData: vi.fn() } } as unknown as ClipboardEvent
    c.onCopyEvent(event, false, true)
    expect(event.preventDefault).not.toHaveBeenCalled()
    expect(holding()).toBe(false)
  })
  it('takes over a copy or cut event while a picture is selected and no text is', () => {
    const { h, log } = host({ id: 'o1', body: body(), asset })
    const c = objectClipboard(h)
    const event = { preventDefault: vi.fn(), stopPropagation: vi.fn(), clipboardData: { setData: vi.fn() } } as unknown as ClipboardEvent
    c.onCopyEvent(event, true, false)
    expect(event.preventDefault).toHaveBeenCalled()
    expect(event.clipboardData!.setData).toHaveBeenCalledWith('text/plain', 'A red box')
    expect(log).toEqual(['remove o1'])
    expect(heldFor('A red box')).not.toBeNull()
  })
  it('takes over a paste event only while the clipboard says what the picture said', () => {
    const { h, log } = host({ id: 'o1', body: body(), asset })
    const c = objectClipboard(h)
    c.copy()
    const make = (text: string) => ({ preventDefault: vi.fn(), stopPropagation: vi.fn(), clipboardData: { getData: () => text } }) as unknown as ClipboardEvent
    const other = make('other')
    c.onPasteEvent(other)
    expect(other.preventDefault).not.toHaveBeenCalled()
    const mine = make('A red box')
    c.onPasteEvent(mine)
    expect(mine.preventDefault).toHaveBeenCalled()
    expect(log).toEqual(['add box.png'])
  })
})

describe('textIsSelected', () => {
  it('sees a range in a field, or on the page', () => {
    const field = { tagName: 'TEXTAREA', selectionStart: 1, selectionEnd: 3 }
    expect(textIsSelected({ activeElement: field, getSelection: () => null } as unknown as Document)).toBe(true)
    expect(textIsSelected({ activeElement: { tagName: 'DIV' }, getSelection: () => ({ isCollapsed: false }) } as unknown as Document)).toBe(true)
    expect(textIsSelected({ activeElement: { tagName: 'DIV' }, getSelection: () => ({ isCollapsed: true }) } as unknown as Document)).toBe(false)
  })
})
