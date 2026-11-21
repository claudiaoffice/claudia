// Tables in the text session (E9.32): the tables the server sends, kept up to date from its events, and the requests that
// change them. A box is typed in with `replace_text` and the box's id; the rest are the server's table methods.
import { describe, expect, it } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { TextSession } from '~/lib/text-session'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'essay',
  app: 'composes',
  branch: 'main',
  revision: 'main:2',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  branches: [{ name: 'main', head: 'main:2', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  async connect() {
    return WELCOME
  }
  async request(method: string, params: any = {}) {
    this.calls.push({ method, params })
    const handler = this.handlers[method]
    if (!handler) throw new ProtocolError('unknown_method', method)
    return handler(params)
  }
  onEvent(h: EventHandler) {
    this.events.push(h)
  }
  onClose(_h: CloseHandler) {}
  close() {}
  push(name: string, data: any) {
    for (const h of this.events) h(name, data)
  }
}


const TABLE = {
  format: 1,
  id: 't1',
  columns: [
    { id: 'c1', kind: 'text', total: null, width: null },
    { id: 'c2', kind: 'number', total: 'sum', width: null },
  ],
  rows: ['r1', 'r2'],
  entries: [
    ['r1', 'c1', { id: 't1/r1/c1', style: '', text: 'Site' }],
    ['r2', 'c1', { id: 't1/r2/c1', style: '', text: 'Roof beds' }],
    ['r2', 'c2', { id: 't1/r2/c2', style: '', text: '8' }],
  ],
  merges: [],
  header_rows: 1,
  banded: false,
  look: 'rules',
  placement: 'flow',
  width: null,
  next_row: 2,
  next_col: 2,
  used_by: ['o1'],
  totals: { c2: '8' },
}
const OBJECT = { id: 'o1', kind: 'table', w: 480, h: 48, style: 'plain-box', paragraph: null, ref: 't1', name: 'Harvest', rotation: 0, anchor: { kind: 'block', holder: 'b1', offset: 0 } }
const block = (id: string, text: string) => ({ id, style: 'body', text, runs: [[[...text].length, 'ann', null]] })

async function opened() {
  const link = new FakeLink()
  link.handlers = {
    blocks: () => ({ revision: 'main:2', styles: [{ id: 'body', name: 'body', purpose: '', based_on: null, css: {}, computed: {}, to_name: false }], lists: [], schemes: [], blocks: [block('b1', 'Before.'), block('b2', 'After.')] }),
    suggestions: () => [],
    style_model: () => STYLE_MODEL,
    palette: () => ({ type: 'palette', roles: [], readings: [] }),
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    branches: () => [{ name: 'main', head: 'main:2', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    hold: () => ({}),
    look: () => ({}),
    objects: () => ({ objects: [OBJECT] }),
    tables: () => [structuredClone(TABLE)], // a copy each time, as the wire gives one: the session may change what it holds
    replace_text: () => ({ revision: 'main:3', block: 't1/r2/c1', offset: 0 }),
    add_table: () => ({ revision: 'main:3', object: 'o2', table: 't2' }),
  }
  const session = new TextSession(() => link, { retryDelays: [0] })
  await session.open()
  return { link, session }
}
const calls = (link: FakeLink, method: string) => link.calls.filter((c) => c.method === method)

describe('the tables of a text', () => {
  it('loads the tables with the text, and an older server that has none is no trouble', async () => {
    const { session } = await opened()
    expect(Object.keys(session.state.tables)).toEqual(['t1'])
    expect(session.state.tables.t1!.totals).toEqual({ c2: '8' })
    const link = new FakeLink()
    link.handlers = { ...(await opened()).link.handlers }
    delete link.handlers.tables
    const old = new TextSession(() => link, { retryDelays: [0] })
    await old.open()
    expect(old.state.tables).toEqual({})
  })

  it('takes a changed table from the event, and drops a forgotten one', async () => {
    const { link, session } = await opened()
    const { used_by: _u, totals: _t, ...definition } = TABLE
    link.push('table', { type: 'table', id: 't1', definition: { ...definition, rows: ['r1', 'r2', 'r3'] } })
    expect(session.state.tables.t1!.rows).toEqual(['r1', 'r2', 'r3'])
    expect(session.state.tables.t1!.used_by).toEqual(['o1'])
    link.push('table', { type: 'table', id: 't1', definition: null })
    expect(session.state.tables.t1).toBeUndefined()
  })

  it('asks for the tables again when words in a box change, and does not reload the text for it', async () => {
    const { link, session } = await opened()
    const before = calls(link, 'tables').length
    const loads = calls(link, 'blocks').length
    link.push('text', { type: 'text', block: 't1/r2/c2', offset: 0, removed: 1, inserted: '9', runs: [[1, 'ann', null]] })
    await Promise.resolve()
    await new Promise((r) => setTimeout(r, 0))
    expect(calls(link, 'tables').length).toBe(before + 1)
    expect(calls(link, 'blocks').length).toBe(loads)
    expect(session.state.blocks.map((b) => b.text)).toEqual(['Before.', 'After.'])
  })

  it('types in a box with the box id, replacing what was in it', async () => {
    const { link, session } = await opened()
    expect(await session.setBox('t1', 'r2', 'c1', 'Roof garden')).toBe(true)
    expect(calls(link, 'replace_text').at(-1)!.params).toMatchObject({ block: 't1/r2/c1', start: 0, end_block: 't1/r2/c1', end: 9, text: 'Roof garden' })
  })

  it('sends one line, and nothing when the words are the same', async () => {
    const { link, session } = await opened()
    expect(await session.setBox('t1', 'r2', 'c1', 'Roof beds')).toBe(true)
    expect(calls(link, 'replace_text')).toHaveLength(0)
    await session.setBox('t1', 'r2', 'c2', '1\n2')
    expect(calls(link, 'replace_text').at(-1)!.params.text).toBe('1 2')
  })

  // B1: Enter and then leaving the box both put the same words in; the second came before the first's echo and doubled them
  it('does not put the same words in twice when two commits come close together', async () => {
    const { link, session } = await opened()
    await Promise.all([session.setBox('t1', 'r1', 'c1', 'A'), session.setBox('t1', 'r1', 'c1', 'A')])
    expect(calls(link, 'replace_text')).toHaveLength(1)
    expect(calls(link, 'replace_text')[0]!.params).toMatchObject({ block: 't1/r1/c1', end: 4, text: 'A' })
    await session.setBox('t1', 'r1', 'c1', 'AB')
    expect(calls(link, 'replace_text').at(-1)!.params).toMatchObject({ end: 1, text: 'AB' }) // it knows what the box has now
  })

  it('counts a box in characters, as the server does', async () => {
    const { link, session } = await opened()
    await session.setBox('t1', 'r1', 'c1', 'x')
    expect(calls(link, 'replace_text').at(-1)!.params.end).toBe(4)
    session.state.tables.t1!.entries[0]![2].text = '🌱🌱'
    await session.setBox('t1', 'r1', 'c1', 'y')
    expect(calls(link, 'replace_text').at(-1)!.params.end).toBe(2)
  })

  it('puts a table after a paragraph, and says which table it made', async () => {
    const { link, session } = await opened()
    link.handlers.add_table = () => ({ revision: 'main:3', object: 'o2', table: 't2' })
    expect(await session.addTable({ block: 'b1', offset: 3 }, { rows: 3, cols: 2, headerRows: 1 })).toEqual({ object: 'o2', table: 't2' })
    expect(calls(link, 'add_table').at(-1)!.params).toMatchObject({ block: 'b1', offset: 3, rows: 3, cols: 2, header_rows: 1 })
  })

  it('asks for rows and columns next to a row or a column, and deletes and sorts by ids', async () => {
    const { link, session } = await opened()
    for (const m of ['insert_rows', 'delete_rows', 'insert_columns', 'delete_columns', 'sort_rows', 'set_table_options', 'set_column', 'merge_cells', 'split_cell', 'remove_table']) link.handlers[m] = () => ({ revision: 'main:3' })
    await session.insertRows('t1', { after: 'r2' })
    await session.deleteRows('t1', ['r2'])
    await session.insertColumns('t1', { before: 'c1' })
    await session.deleteColumns('t1', ['c2'])
    await session.sortRows('t1', 'c2', true)
    await session.setTableOptions('t1', { banded: true })
    await session.setColumn('t1', 'c2', { total: 'mean' })
    await session.mergeCells('t1', 'r2', 'c1', 1, 2)
    await session.splitCell('t1', 'r2', 'c1')
    await session.removeTable('t1')
    const sent = (method: string) => calls(link, method).at(-1)!.params
    expect(sent('insert_rows')).toMatchObject({ table: 't1', after: 'r2' })
    expect(sent('delete_rows')).toMatchObject({ table: 't1', ids: ['r2'] })
    expect(sent('insert_columns')).toMatchObject({ table: 't1', before: 'c1' })
    expect(sent('delete_columns')).toMatchObject({ table: 't1', ids: ['c2'] })
    expect(sent('sort_rows')).toMatchObject({ table: 't1', column: 'c2', descending: true })
    expect(sent('set_table_options')).toMatchObject({ table: 't1', options: { banded: true } })
    expect(sent('set_column')).toMatchObject({ table: 't1', column: 'c2', changes: { total: 'mean' } })
    expect(sent('merge_cells')).toMatchObject({ table: 't1', row: 'r2', col: 'c1', rows: 1, cols: 2 })
    expect(sent('split_cell')).toMatchObject({ table: 't1', row: 'r2', col: 'c1' })
    expect(sent('remove_table')).toMatchObject({ id: 't1' })
  })

  it('tells a viewer that the text can only be looked at, and sends nothing', async () => {
    const { link, session } = await opened()
    session.state.me.role = 'viewer'
    expect(await session.setBox('t1', 'r2', 'c1', 'x')).toBe(false)
    expect(await session.insertRows('t1', { after: 'r1' })).toBe(false)
    expect(calls(link, 'replace_text')).toHaveLength(0)
    expect(calls(link, 'insert_rows')).toHaveLength(0)
  })

  it('remembers the box the caret is in, for the entries of the Edit menu', async () => {
    const { session } = await opened()
    expect(session.state.box).toBeNull()
    session.focusBox({ table: 't1', row: 'r2', col: 'c1' })
    expect(session.state.box).toEqual({ table: 't1', row: 'r2', col: 'c1' })
    expect(session.boxTable()?.id).toBe('t1')
    session.focusBox(null)
    expect(session.boxTable()).toBeNull()
  })

  it('reads the tables to print along with the objects', async () => {
    const { link, session } = await opened()
    link.handlers.shapes = () => []
    link.handlers.images = () => []
    const extras = await session.printExtras()
    expect(extras.tables.map((t) => t.id)).toEqual(['t1'])
    expect(extras.tables[0]!.totals).toEqual({ c2: '8' })
  })
})
