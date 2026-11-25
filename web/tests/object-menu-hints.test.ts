// CODE-71: the object menu's key hints come from the manifest (`keys.generated.ts`), never typed by hand, so the two
// cannot drift. The table is replaced by one where every action's key is named after the action: a hint then shows
// which action's key it is, and a hint typed by hand shows up as one that is no action's.
import { describe, expect, it, vi } from 'vitest'
import { contextMenuItems, type MenuSubject } from '~/lib/object-menu'

vi.mock('~/lib/keys.generated', async (original) => {
  const { KEYS } = await original<typeof import('~/lib/keys.generated')>()
  return { KEYS: Object.fromEntries(Object.entries(KEYS).map(([id, key]) => [id, { ...key, chord: { key: id } }])) }
})

/** Each entry's action, as the menus workbook (`claudia-menus`, Context menus) names it. */
const ACTION_OF: Record<string, string> = {
  'Name & describe…': 'format.describe',
  'Edit text': 'edit.edit-text',
  'Style…': 'format.apply-style',
  'Rotate by…': 'format.rotate-by',
  'Wrap text…': 'format.wrap-text',
  Cut: 'edit.cut',
  Copy: 'edit.copy',
  Delete: 'edit.delete',
}

const actions = {
  describe: vi.fn(),
  edit: vi.fn(),
  style: vi.fn(),
  rotateBy: vi.fn(),
  remove: vi.fn(),
  cut: vi.fn(),
  copy: vi.fn(),
  setSnap: vi.fn(),
  setWrap: vi.fn(),
  setGap: vi.fn(),
}

describe('the hints of the object menu (CODE-71)', () => {
  it("every entry shows its action's key from the manifest", () => {
    const subjects: MenuSubject[] = [{ kind: 'text' }, { kind: 'image' }]
    const items = subjects.flatMap((o) => contextMenuItems(o, false, actions, { wrap: 'around' }))
    const hinted = items.filter((item) => item.label in ACTION_OF)
    expect(new Set(hinted.map((item) => item.label))).toEqual(new Set(Object.keys(ACTION_OF)))
    for (const item of hinted) expect({ entry: item.label, hint: item.hint }).toEqual({ entry: item.label, hint: ACTION_OF[item.label] })
  })
})
