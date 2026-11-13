import { describe, expect, it } from 'vitest'
import { STYLE_MODEL } from './style-model.fixture'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { Session } from '~/lib/session'

const ASSET = { id: 'a'.repeat(64), format: 'gif', width: 20, height: 10, animated: false, data: 'AA==', first_frame: null }
const IMPORT = { asset: ASSET.id, alt: 'a chart', imported_by: 'ann', imported_at: '2026-11-07T10:00:00.000Z', source: 'disk', source_name: 'chart.gif', source_path: '/Users/ann/chart.gif' }
// An object as the server sends it (E10.16, D177): the shared body's fields flat, the anchor nested — the same
// shape in all three apps, only `anchor` differing (here a cell of a sheet).
const image = (id: string, extra: object = {}) => ({
  id,
  kind: 'image',
  w: 400,
  h: 200,
  style: 'plain-image',
  paragraph: null,
  shape: null,
  image: ASSET.id,
  imported: IMPORT,
  rotation: 0,
  snap: true,
  anchor: { kind: 'cell', container: 's1', row: 0, col: 0 },
  ...extra,
})

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'plan',
  app: 'computes',
  line: 'main',
  revision: 'main:3',
  id: 1,
  color: '#e6194b',
  people: [{ id: 9, user: 'ai', color: '#5b4bc4' }],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  lines: [{ name: 'main', head: 'main:3', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  closers: CloseHandler[] = []
  welcome = WELCOME
  failConnect: ProtocolError | null = null
  async connect() {
    if (this.failConnect) throw this.failConnect
    return this.welcome
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
  onClose(h: CloseHandler) {
    this.closers.push(h)
  }
  close() {}
  push(name: string, data: any) {
    for (const h of this.events) h(name, data)
  }
  drop(code = 1006) {
    for (const h of this.closers) h(code, false)
  }
  count(method: string) {
    return this.calls.filter((c) => c.method === method).length
  }
  last(method: string) {
    return this.calls.filter((c) => c.method === method).at(-1)?.params
  }
}

function server(link: FakeLink) {
  const cells: Record<string, any> = { '0,0': { t: 'text', v: 'Item' }, '1,1': { t: 'int', v: 40 } }
  link.handlers = {
    sheets: () => [{ id: 's1', name: 'Budget', rows: 2, cols: 2 }],
    images: () => [],
    // A workbook has styles and a palette of its own since E9.7/D200: its floating objects are drawn from them.
    styles: () => [
      {
        id: 'plain-shape',
        name: 'Plain shape',
        purpose: '',
        based_on: null,
        css: { fill: '@accent/14' },
        computed: { fill: '@accent/14' },
        resolved: { fill: 'rgba(91, 75, 196, 0.14)' },
        to_name: false,
        kind: 'outline',
      },
    ],
    style_model: () => STYLE_MODEL,
    palette: () => ({
      type: 'palette',
      roles: [{ id: 'accent', name: 'Accent', purpose: 'the one thing to notice', colour: '#5B4BC4' }],
      readings: [],
    }),
    objects: (p: any) => ({ revision: 'main:3', sheet: p.sheet, objects: [] }),
    log: () => [{ revision: 'main:3', author: 'ben', origin: 'do', time: 't', label: 'Edit cell', summary: 'B2 = 40', of: null }],
    chat_log: () => [{ number: 1, author: 'ben', to: '', text: 'hi', time: 't', at: null }],
    checkpoints: () => [],
    history: () => ({ can_undo: true, can_redo: false, undo_label: 'Edit cell', redo_label: '' }),
    lines: () => [{ name: 'main', head: 'main:3', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    cells: (p: any) => ({
      revision: 'main:3',
      cells: Object.entries(cells)
        .map(([k, v]) => [...k.split(',').map(Number), v] as [number, number, any])
        .filter(([r, c]) => r >= p.row0 && r <= p.row1 && c >= p.col0 && c <= p.col1),
    }),
    set_cells: () => ({ revision: 'main:4' }),
    undo: () => ({ applied: true, revision: 'main:5' }),
    presence: () => ({}),
    lock: () => ({}),
    unlock: () => ({}),
    chat: () => ({}),
    peek_line: ({ line }: any) => ({ line, revision: 'main:3', app: 'computes', state_schema: 1, state: {} }),
    propose_restore: () => ({ applied: true, proposal: null }),
    propose_switch: () => ({ applied: true, proposal: null }),
    answer_restore: () => ({ resolved: 'agreed' }),
    withdraw_restore: () => ({}),
    discard_side_history: () => ({ discarded: [] }),
    set_restore_policy: ({ policy }: any) => ({ policy }),
    ping: () => ({ revision: 'main:3', line: 'main' }),
    sizes: () => ({ revision: 'main:3', rows: [[3, 52]], cols: [] }),
    resize_lines: () => ({ revision: 'main:4' }),
    diagrams: () => [],
    charts: () => [],
    names: () => ({ revision: 'main:3', names: [] }),
    random_state: () => ({ revision: 'main:3', seed: 0, draw: 0 }),
  }
}

function memoryStorage() {
  const map = new Map<string, string>()
  return { getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => void map.set(k, v) }
}

async function opened(options: { storage?: ReturnType<typeof memoryStorage>; doc?: string } = {}) {
  const link = new FakeLink()
  server(link)
  if (options.doc) link.welcome = { ...WELCOME, doc: options.doc }
  const links = [link]
  const session = new Session(() => links.shift() ?? link, { retryDelays: [0], storage: options.storage ?? memoryStorage() })
  await session.open()
  return { link, session }
}

describe('opening', () => {
  it('connects and loads what the screen needs', async () => {
    const { session, link } = await opened()
    const s = session.state
    expect(s.status).toBe('open')
    expect(s.me).toMatchObject({ user: 'ann', role: 'owner', color: '#e6194b' })
    expect(s.people.map((p) => p.user)).toEqual(['ai'])
    expect(s.sheets.map((x) => x.name)).toEqual(['Budget'])
    expect(s.activeSheet).toBe('s1')
    expect(s.entries[0]).toMatchObject({ author: 'ben', summary: 'B2 = 40' })
    expect(s.chat.map((m) => m.text)).toEqual(['hi'])
    expect(s.canUndo).toBe(true)
    expect(s.revision).toBe('main:3')
    expect(link.count('sheets')).toBe(1)
  })

  it('reports a refused handshake and stays closed', async () => {
    const link = new FakeLink()
    link.failConnect = new ProtocolError('unauthorized', 'missing or wrong credentials')
    const session = new Session(() => link)
    await expect(session.open()).rejects.toMatchObject({ code: 'unauthorized' })
    expect(session.state.status).toBe('closed')
  })
})

describe('host', () => {
  it('is blank when nothing was asked to connect to a particular server', async () => {
    const link = new FakeLink()
    server(link)
    const session = new Session(() => link)
    await session.open()
    expect(session.state.host).toBe('')
  })

  it('carries the server address the caller connected to (E3.11, "knowing which server you\'re on")', async () => {
    const link = new FakeLink()
    server(link)
    const session = new Session(() => link, { host: 'demo.claudiaoffice.de:8420' })
    await session.open()
    expect(session.state.host).toBe('demo.claudiaoffice.de:8420')
  })
})

describe('ping', () => {
  it('is null before anything has connected', async () => {
    const link = new FakeLink()
    server(link)
    const session = new Session(() => link)
    expect(await session.ping()).toBeNull()
  })

  it('is a non-negative round-trip time once open', async () => {
    const { session } = await opened()
    const ms = await session.ping()
    expect(ms).not.toBeNull()
    expect(ms).toBeGreaterThanOrEqual(0)
  })

  it('is null if the request fails', async () => {
    const link = new FakeLink()
    server(link)
    delete link.handlers.ping
    const session = new Session(() => link)
    await session.open()
    expect(await session.ping()).toBeNull()
  })
})

describe('cells', () => {
  it('loads a window once and serves it from memory', async () => {
    const { session, link } = await opened()
    await session.ensure('s1', 0, 10, 0, 5)
    await session.ensure('s1', 0, 10, 0, 5)
    expect(link.count('cells')).toBe(1)
    expect(session.cell('s1', 0, 0)).toEqual({ t: 'text', v: 'Item' })
    expect(session.cell('s1', 1, 1)).toEqual({ t: 'int', v: 40 })
    expect(session.cell('s1', 5, 5)).toBeNull()
  })

  it('follows cell events, also for empty cells', async () => {
    const { session, link } = await opened()
    await session.ensure('s1', 0, 10, 0, 5)
    link.push('cells', { sheet: 's1', positions: [[0, 0]], cells: [[0, 0, { t: 'text', v: 'Thing' }], [1, 1, null]] })
    expect(session.cell('s1', 0, 0)).toEqual({ t: 'text', v: 'Thing' })
    expect(session.cell('s1', 1, 1)).toBeNull()
  })

  it('reloads the window when rows or columns moved', async () => {
    const { session, link } = await opened()
    await session.ensure('s1', 0, 10, 0, 5)
    const before = session.state.generation
    link.push('structure', { sheet: 's1', axis: 'row', insert: true, at: 0, count: 1 })
    expect(session.state.generation).toBe(before + 1)
    await session.ensure('s1', 0, 10, 0, 5)
    expect(link.count('cells')).toBe(2)
  })
})

describe('cell styles (E6.13, D307, D317)', () => {
  const INPUT = { slot: 'box', layer: 'range', area: [1, 1, 2, 3], style: 'input' }
  function styled(link: FakeLink) {
    link.handlers.cell_styles = () => ({ revision: 'main:3', ranges: [INPUT, { ...INPUT, slot: 'words' }] })
    link.handlers.style_uses = () => ({ uses: { input: 2 } })
    link.handlers.apply_style = () => ({ revision: 'main:4' })
    link.handlers.deviate = () => ({ style: 'input-changed', name: 'Input (changed)', revision: 'main:4' })
    link.handlers.clear_cell_style = () => ({ revision: 'main:4' })
  }

  it('loads a sheet’s style ranges once, all of them: a range is one entry however many cells it covers', async () => {
    const { session, link } = await opened()
    styled(link)
    await session.ensureCellStyles('s1')
    await session.ensureCellStyles('s1')
    expect(link.count('cell_styles')).toBe(1)
    expect(link.last('cell_styles')).toEqual({ sheet: 's1', row0: 0, row1: 1_048_575, col0: 0, col1: 16_383 })
    expect(session.cellStyles('s1').map((r) => r.slot)).toEqual(['box', 'words'])
    expect(session.cellStyles('s2')).toEqual([])
  })

  it('loads them again when they changed, and forgets them when rows or columns moved', async () => {
    const { session, link } = await opened()
    styled(link)
    await session.ensureCellStyles('s1')
    link.push('cell_styles', { sheet: 's1', area: [0, 0, 0, 0] })
    await session.settled()
    expect(link.count('cell_styles')).toBe(2)
    link.push('structure', { sheet: 's1', axis: 'row', insert: true, at: 0, count: 1 })
    expect(session.cellStyles('s1')).toEqual([])
    await session.ensureCellStyles('s1')
    expect(link.count('cell_styles')).toBe(3)
  })

  it('does not load a sheet nobody has looked at when its styles change', async () => {
    const { session, link } = await opened()
    styled(link)
    link.push('cell_styles', { sheet: 's1', area: [0, 0, 0, 0] })
    await session.settled()
    expect(link.count('cell_styles')).toBe(0)
  })

  it('counts the uses of every style from the server, and again when styles, cells or objects change', async () => {
    const { session, link } = await opened()
    styled(link)
    await session.refreshUses()
    expect(session.state.styleUses).toEqual({ input: 2 })
    const before = link.count('style_uses')
    for (const event of ['cell_styles', 'objects', 'styles']) link.push(event, event === 'objects' ? { changed: [], removed: [], order: [], container: 's1' } : { sheet: 's1', area: [0, 0, 0, 0], styles: [] })
    await session.settled()
    expect(link.count('style_uses')).toBe(before + 3)
  })

  it('styles cells in both slots, deviates them, and clears them, against the revision it is looking at', async () => {
    const { session, link } = await opened()
    styled(link)
    const cells = { sheet: 's1', range: [1, 1, 2, 3] as [number, number, number, number] }
    expect(await session.applyStyle([cells], 'input')).toBe(true)
    expect(link.last('apply_style')).toEqual({ targets: [cells], style: 'input', slot: undefined, base: 'main:3' })
    expect(await session.deviateStyle('input', [cells], 'box', { set: { 'background-color': '@attention/14' } })).toBe(true)
    expect(link.last('deviate')).toMatchObject({ parent: 'input', targets: [cells], slot: 'box', set: { 'background-color': '@attention/14' } })
    expect(await session.clearCellStyle('s1', [1, 1, 2, 3])).toBe(true)
    expect(link.last('clear_cell_style')).toEqual({ sheet: 's1', range: [1, 1, 2, 3], slot: undefined, base: 'main:3' })
  })
})

describe('floating objects (images, E6.17)', () => {
  it('loads the decoded pictures and the objects of every sheet, on top of the cells', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.images = () => [ASSET]
    link.handlers.objects = ({ sheet }: any) => ({ revision: 'main:3', sheet, objects: sheet === 's1' ? [image('i1')] : [] })
    const session = new Session(() => link)
    await session.open()
    expect(session.state.images[ASSET.id]).toEqual(ASSET)
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['i1'])
    const o = session.objectsOn('s1')[0]!
    expect(o.image).toBe(ASSET.id)
    expect(o.imported).toEqual(IMPORT)
  })

  it('follows the stacking order the server sends, and takes objects away', async () => {
    const { link, session } = await opened()
    link.push('objects', { type: 'objects', container: 's1', changed: [image('a'), image('b')], removed: [], order: ['a', 'b'] })
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['a', 'b'])
    link.push('objects', { type: 'objects', container: 's1', changed: [image('a', { anchor: { kind: 'cell', container: 's1', row: 3, col: 2 } })], removed: [], order: ['a', 'b'] })
    expect(session.objectsOn('s1')[0]?.anchor).toMatchObject({ row: 3, col: 2 })
    link.push('objects', { type: 'objects', container: 's1', changed: [], removed: ['a'], order: ['b'] })
    expect(session.objectsOn('s1').map((o) => o.id)).toEqual(['b'])
    expect(session.state.objects.a).toBeUndefined()
  })

  it('learns and forgets decoded pictures', async () => {
    const { link, session } = await opened()
    link.push('image', { type: 'image', id: ASSET.id, asset: ASSET })
    expect(session.state.images[ASSET.id]!.width).toBe(20)
    link.push('image', { type: 'image', id: ASSET.id, asset: null })
    expect(session.state.images[ASSET.id]).toBeUndefined()
  })

  it('imports a picture, anchored to a cell with a fixed pixel size', async () => {
    const { link, session } = await opened()
    link.handlers.add_image = () => ({ object: 'i1', revision: 'main:4' })
    const id = await session.addImage({ data: 'AA==', alt: 'a chart', sourceName: 'chart.gif', sourcePath: null }, { row: 2, col: 1, w: 400, h: 200 })
    expect(id).toBe('i1')
    expect(link.last('add_image')).toEqual({
      sheet: 's1',
      data: 'AA==',
      alt: 'a chart',
      source_name: 'chart.gif',
      source_path: null,
      row: 2,
      col: 1,
      w: 400,
      h: 200,
      base: 'main:3',
    })
  })

  it('imports a decorative picture with the mark and no words (BITV 1.1.1)', async () => {
    const { link, session } = await opened()
    link.handlers.add_image = () => ({ object: 'i1', revision: 'main:4' })
    await session.addImage({ data: 'AA==', alt: '', sourceName: 'rule.gif', sourcePath: null, decorative: true }, { row: 2, col: 1, w: 400, h: 200 })
    expect(link.last('add_image')).toMatchObject({ alt: '', decorative: true })
  })

  it('describes an object, trimmed, and marks one as decoration without words', async () => {
    const { link, session } = await opened()
    link.handlers.describe_object = () => ({ revision: 'main:4' })
    expect(await session.describeObject('i1', '  sales by quarter ', false)).toBe(true)
    expect(link.last('describe_object')).toEqual({ id: 'i1', description: 'sales by quarter', decorative: false, base: 'main:3' })
    await session.describeObject('i1', 'left over', true)
    expect(link.last('describe_object')).toEqual({ id: 'i1', description: '', decorative: true, base: 'main:3' })
  })

  it('says why importing a picture failed, without touching the objects', async () => {
    const { link, session } = await opened()
    link.handlers.add_image = () => {
      throw new ProtocolError('command_error', 'this document does not look like a picture the browser can show')
    }
    const id = await session.addImage({ data: 'not base64', alt: 'x', sourceName: 'x.bin', sourcePath: null }, { row: 0, col: 0, w: 10, h: 10 })
    expect(id).toBeNull()
    expect(session.state.notice?.text).toContain('picture')
  })

  it('moves an object to a new anchor cell; its size is never part of the request', async () => {
    const { link, session } = await opened()
    link.handlers.move_object = () => ({ revision: 'main:4' })
    expect(await session.moveObject('i1', 5, 6)).toBe(true)
    expect(link.last('move_object')).toEqual({ id: 'i1', row: 5, col: 6, base: 'main:3' })
  })

  it('removes an object', async () => {
    const { link, session } = await opened()
    link.handlers.remove_object = () => ({ revision: 'main:4' })
    expect(await session.removeObject('i1')).toBe(true)
    expect(link.last('remove_object')).toEqual({ id: 'i1', base: 'main:3' })
  })

  it('a colleague holding the sheet open refuses the move and the person is told', async () => {
    const { session, link } = await opened()
    link.handlers.move_object = () => {
      throw new ProtocolError('conflict', 'the document changed under you')
    }
    expect(await session.moveObject('i1', 1, 1)).toBe(false)
    expect(session.state.notice).toMatchObject({ kind: 'warning', text: 'the document changed under you' })
  })
})

describe('row and column sizes', () => {
  it('shows every line at the default until the sizes are loaded', async () => {
    const { session } = await opened()
    expect(session.rowHeight('s1', 3)).toBe(26)
    expect(session.colWidth('s1', 0)).toBe(96)
  })

  it('loads a sheet’s sizes once and serves them from memory', async () => {
    const { session, link } = await opened()
    await session.ensureSizes('s1')
    await session.ensureSizes('s1')
    expect(link.count('sizes')).toBe(1)
    expect(session.rowHeight('s1', 3)).toBe(52)
    expect(session.rowHeight('s1', 4)).toBe(26) // not overridden: the default
    expect(session.colWidth('s1', 0)).toBe(96)
  })

  it('follows sizes events, including a line reset back to the default', async () => {
    const { session, link } = await opened()
    await session.ensureSizes('s1')
    link.push('sizes', { sheet: 's1', axis: 'col', sizes: [[0, 144]] })
    expect(session.colWidth('s1', 0)).toBe(144)
    link.push('sizes', { sheet: 's1', axis: 'row', sizes: [[3, null]] })
    expect(session.rowHeight('s1', 3)).toBe(26)
  })

  it('forgets a sheet’s sizes (and reloads them) when its rows or columns were restructured', async () => {
    const { session, link } = await opened()
    await session.ensureSizes('s1')
    expect(session.rowHeight('s1', 3)).toBe(52)
    link.push('structure', { sheet: 's1', axis: 'row', insert: true, at: 0, count: 1 })
    await session.ensureSizes('s1')
    expect(link.count('sizes')).toBe(2)
  })

  it('resizes lines against the revision it is looking at', async () => {
    const { session, link } = await opened()
    await session.resizeLines('s1', 'row', [[3, 39], [4, 78]])
    const call = link.calls.find((c) => c.method === 'resize_lines')!
    expect(call.params).toEqual({ sheet: 's1', axis: 'row', sizes: [[3, 39], [4, 78]], base: 'main:3' })
  })

  it('tells the person when a colleague is in the way, and does not throw', async () => {
    const { session, link } = await opened()
    link.handlers.resize_lines = () => {
      throw new ProtocolError('conflict', 'ben resized row 4 after you')
    }
    expect(await session.resizeLines('s1', 'row', [[3, 39]])).toBe(false)
    expect(session.state.notice).toMatchObject({ kind: 'warning', text: 'ben resized row 4 after you' })
  })
})

describe('events', () => {
  it('keeps the history, the revision and the undo state', async () => {
    const { session, link } = await opened()
    link.push('command', { revision: 'main:4', author: 'ai', origin: 'do', time: 't2', label: 'Edit cells', summary: '3 cells in A1:A3' })
    expect(session.state.entries.at(-1)).toMatchObject({ author: 'ai', summary: '3 cells in A1:A3' })
    expect(session.state.revision).toBe('main:4')
    link.push('command', { revision: 'main:4', author: 'ai', origin: 'do', time: 't2', label: 'x', summary: 'again' })
    expect(session.state.entries.filter((e) => e.revision === 'main:4')).toHaveLength(1)
    link.push('history', { author: 'ann', can_undo: false, can_redo: true, undo_label: '', redo_label: 'Edit cell' })
    expect(session.state.canUndo).toBe(false)
    expect(session.state.canRedo).toBe(true)
  })

  it('collects chat and checkpoints', async () => {
    const { session, link } = await opened()
    link.push('chat', { number: 2, author: 'ai', to: 'ann', text: 'done', time: 't', at: null })
    link.push('checkpoint', { number: 1, label: 'first', author: 'ann', marks: 'main:3' })
    expect(session.state.chat.map((m) => m.text)).toEqual(['hi', 'done'])
    expect(session.state.checkpoints.map((c) => c.label)).toEqual(['first'])
  })

  it('knows who is here, where they are, and who is typing', async () => {
    const { session, link } = await opened()
    link.push('joined', { id: 2, user: 'ben', color: '#3cb44b' })
    expect(session.state.people.map((p) => p.user)).toEqual(['ai', 'ben'])
    const region = { kind: 'cells', range: { first: { row: 2, col: 1, sheet: 's1' }, last: { row: 2, col: 1, sheet: 's1' } } }
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [region], locked: true } })
    expect(session.state.presence.ben).toMatchObject({ locked: true })
    expect(session.state.presence.ben!.regions).toEqual([region])
    link.push('ephemeral', { kind: 'typing', sender: 'ai', data: { on: true } })
    expect(session.state.typing).toEqual(['ai'])
    link.push('ephemeral', { kind: 'typing', sender: 'ai', data: { on: false } })
    expect(session.state.typing).toEqual([])
    link.push('left', { id: 2, user: 'ben' })
    link.push('ephemeral', { kind: 'presence', sender: 'ben', data: { regions: [], gone: true } })
    expect(session.state.people.map((p) => p.user)).toEqual(['ai'])
    expect(session.state.presence.ben).toBeUndefined()
  })

  it('reloads everything when the document changed line or was rebuilt', async () => {
    for (const name of ['branch', 'rebuilt', 'redacted']) {
      const { session, link } = await opened()
      await session.ensure('s1', 0, 10, 0, 5)
      link.push(name, {})
      await session.settled()
      expect(link.count('sheets')).toBe(2)
      expect(link.count('log')).toBe(2)
      expect(session.state.notice?.text).toMatch(/changed/i)
    }
  })

  it('reloads the sheets when they changed', async () => {
    const { session, link } = await opened()
    link.push('sheets', {})
    await session.settled()
    expect(link.count('sheets')).toBe(2)
  })
})

describe('doing things', () => {
  it('types into cells against the revision it is looking at', async () => {
    const { session, link } = await opened()
    await session.setCells('s1', [{ row: 0, col: 0, input: 'x' }])
    const call = link.calls.find((c) => c.method === 'set_cells')!
    expect(call.params).toEqual({ sheet: 's1', cells: [{ row: 0, col: 0, input: 'x' }], base: 'main:3' })
  })

  it('tells the person when a colleague holds the cell, and does not throw', async () => {
    const { session, link } = await opened()
    link.handlers.set_cells = () => {
      throw new ProtocolError('locked', 'ben is working on B2 right now')
    }
    expect(await session.setCells('s1', [{ row: 1, col: 1, input: '1' }])).toBe(false)
    expect(session.state.notice).toMatchObject({ kind: 'warning', text: 'ben is working on B2 right now' })
  })

  it('reloads when an edit was made against a view that is gone', async () => {
    const { session, link } = await opened()
    link.handlers.set_cells = () => {
      throw new ProtocolError('stale', 'the document went back')
    }
    expect(await session.setCells('s1', [{ row: 0, col: 0, input: '1' }])).toBe(false)
    await session.settled()
    expect(link.count('sheets')).toBe(2)
    expect(session.state.notice?.text).toMatch(/not applied|changed/i)
  })

  it('explains a viewer’s refusal', async () => {
    const { session, link } = await opened()
    link.handlers.set_cells = () => {
      throw new ProtocolError('forbidden', 'set_cells needs the editor role')
    }
    await session.setCells('s1', [{ row: 0, col: 0, input: '1' }])
    expect(session.state.notice?.text).toMatch(/only look/i)
  })

  it('undoes, and says when there was nothing to undo because of a colleague', async () => {
    const { session, link } = await opened()
    expect(await session.undo()).toBe(true)
    link.handlers.undo = () => {
      throw new ProtocolError('conflict', 'ben changed B2 after you')
    }
    expect(await session.undo()).toBe(false)
    expect(session.state.notice?.text).toBe('ben changed B2 after you')
  })

  it('locks a cell while it is edited and lets go afterwards', async () => {
    const { session, link } = await opened()
    expect(await session.beginEdit('s1', 2, 1)).toBe(true)
    expect(link.calls.find((c) => c.method === 'lock')!.params.regions[0].range.first).toMatchObject({ row: 2, col: 1, sheet: 's1' })
    await session.endEdit()
    expect(link.count('unlock')).toBe(1)
    link.handlers.lock = () => {
      throw new ProtocolError('locked', 'ben is working on C3 right now')
    }
    expect(await session.beginEdit('s1', 2, 2)).toBe(false)
    expect(session.state.notice?.text).toMatch(/ben/)
  })

  it('sends chat as it is typed, with how the person wants the AI to treat it', async () => {
    const { session, link } = await opened()
    await session.say('@ai hello')
    expect(link.calls.find((c) => c.method === 'chat')!.params).toEqual({ text: '@ai hello', ai_mode: 'suggest' })
  })

  it('lets the person choose act, from then on, and tells the server with every message', async () => {
    const { session, link } = await opened()
    expect(session.state.aiMode).toBe('suggest')
    session.setAiMode('act')
    expect(session.state.aiMode).toBe('act')
    await session.say('@ai fill A1')
    await session.say('hello everybody')
    const sent = link.calls.filter((c) => c.method === 'chat').map((c) => c.params)
    expect(sent).toEqual([
      { text: '@ai fill A1', ai_mode: 'act' },
      { text: 'hello everybody', ai_mode: 'act' },
    ])
  })

  it('remembers the choice for this document in this browser, and not for another', async () => {
    const storage = memoryStorage()
    const first = await opened({ storage })
    first.session.setAiMode('act')
    const again = await opened({ storage })
    expect(again.session.state.aiMode).toBe('act')
    const elsewhere = await opened({ storage, doc: 'budget' })
    expect(elsewhere.session.state.aiMode).toBe('suggest')
  })

  it('keeps the choice across a reconnect', async () => {
    const { session, link } = await opened()
    session.setAiMode('act')
    link.drop(1006)
    await session.settled()
    expect(session.state.status).toBe('open')
    expect(session.state.aiMode).toBe('act')
  })
})

describe('losing the connection', () => {
  it('opens a new one and reloads', async () => {
    const first = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    const links = [first, second]
    const session = new Session(() => links.shift()!, { retryDelays: [0] })
    await session.open()
    first.drop(1006)
    expect(session.state.status).toBe('reconnecting')
    await session.settled()
    expect(session.state.status).toBe('open')
    expect(second.count('sheets')).toBe(1)
  })

  it('keeps trying while the document is sealed (an editor has not opened it since the server started)', async () => {
    const first = new FakeLink()
    const sealed = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    sealed.failConnect = new ProtocolError('sealed', 'this document is sealed: an owner or editor has to open it first')
    const links = [first, sealed, second]
    const session = new Session(() => links.shift()!, { retryDelays: [0] })
    await session.open()
    first.drop(1006)
    await session.settled()
    expect(session.state.status).toBe('open')
    expect(second.count('sheets')).toBe(1)
  })

  it('gives up for good on a refusal that will not change', async () => {
    const first = new FakeLink()
    const refused = new FakeLink()
    server(first)
    refused.failConnect = new ProtocolError('unauthorized', 'missing or wrong credentials')
    const links = [first, refused]
    const session = new Session(() => links.shift()!, { retryDelays: [0] })
    await session.open()
    first.drop(1006)
    await session.settled()
    expect(session.state.status).toBe('closed')
  })

  it('loads the cells again on the new connection, even if a request was left hanging on the old one', async () => {
    const first = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    first.handlers.cells = () => new Promise(() => undefined) // never answered
    const links = [first, second]
    const session = new Session(() => links.shift()!, { retryDelays: [0] })
    await session.open()
    void session.ensure('s1', 0, 10, 0, 5)
    first.drop(1006)
    await session.settled()
    await session.ensure('s1', 0, 10, 0, 5)
    expect(second.count('cells')).toBe(1)
    expect(session.cell('s1', 1, 1)).toEqual({ t: 'int', v: 40 })
  })

  it('does not retry when the server refused us', async () => {
    const { session, link } = await opened()
    link.drop(4401)
    expect(session.state.status).toBe('closed')
    expect(session.state.error).toMatch(/password/)
  })

  it('stays closed when we closed it ourselves', async () => {
    const { session, link } = await opened()
    session.close()
    for (const h of link.closers) h(1000, true)
    expect(session.state.status).toBe('closed')
  })
})

describe('reading what is loaded', () => {
  it('lists the filled cells of a rectangle', async () => {
    const { session } = await opened()
    await session.ensure('s1', 0, 10, 0, 5)
    expect(session.filledIn('s1', 0, 0, 5, 5).sort()).toEqual([[0, 0], [1, 1]])
    expect(session.filledIn('s1', 1, 0, 5, 0)).toEqual([])
  })
})

describe('the recovery key', () => {
  it('asks the server for a new one and hands it over', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.new_recovery_key = () => ({ recovery_key: 'ABCD-EFGH' })
    const session = new Session(() => link)
    await session.open()
    expect(await session.newRecoveryKey()).toBe('ABCD-EFGH')
    expect(session.state.notice).toBeNull()
  })

  it('gives nothing back, and says why, if the server will not make one', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.new_recovery_key = () => {
      throw new ProtocolError('forbidden', 'only the owner of a document makes a recovery key')
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.newRecoveryKey()).toBeNull()
    expect(session.state.notice?.text).toBe('You can only look at this document.')
  })

  it('stays quiet when the server simply keeps no recovery keys (that is not the person’s doing)', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.new_recovery_key = () => {
      throw new ProtocolError('unavailable', 'this server does not keep recovery keys')
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.newRecoveryKey({ quiet: true })).toBeNull()
    expect(session.state.notice).toBeNull()
  })
})

describe('the Manage menu (leaving, handing over ownership, deleting, exporting)', () => {
  it('has nothing waiting to send before a checkpoint or an export: every change went out as it was made', async () => {
    const { session, link } = await opened()
    const before = link.calls.length
    await session.flush()
    expect(link.calls.length).toBe(before)
  })

  it('lists everybody, not just who is connected', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.roster = () => [
      { user: 'ann', role: 'owner' },
      { user: 'ben', role: 'editor' },
    ]
    const session = new Session(() => link)
    await session.open()
    expect(await session.roster()).toEqual([
      { user: 'ann', role: 'owner' },
      { user: 'ben', role: 'editor' },
    ])
  })

  it('leaves with a password, and closes for nobody but us', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.leave = () => ({ left: true })
    const session = new Session(() => link)
    await session.open()
    expect(await session.leave('Correct-Horse-9')).toBe(true)
    expect(session.state.status).toBe('open')
  })

  it('reports why leaving did not work', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.leave = () => {
      throw new ProtocolError('unauthorized', 'that is not your current password')
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.leave('wrong')).toBe(false)
    expect(session.state.notice?.text).toBe('that is not your current password')
  })

  it('proposes a new owner with our own password', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.propose_owner = (p) => ({ proposed: p.name })
    const session = new Session(() => link)
    await session.open()
    expect(await session.proposeOwner('ben', 'Correct-Horse-9')).toBe(true)
    expect(link.calls.at(-1)).toMatchObject({ method: 'propose_owner', params: { name: 'ben', password: 'Correct-Horse-9' } })
  })

  it('accepting ownership reconnects so the new role is recognised', async () => {
    const first = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    first.handlers.accept_owner = () => ({ accepted: true })
    const links = [first, second]
    const session = new Session(() => links.shift()!)
    await session.open()
    expect(await session.acceptOwner('Battery-Staple-7')).toBe(true)
    expect(session.state.status).toBe('open')
    expect(second.count('sheets')).toBe(1)
  })

  it('deletes the document with a password, and closes the session', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.delete_document = () => ({ deleted: true })
    const session = new Session(() => link)
    await session.open()
    expect(await session.deleteDocument('Correct-Horse-9')).toBe(true)
    expect(session.state.status).toBe('closed')
  })

  it('does not close the session when deleting is refused', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.delete_document = () => {
      throw new ProtocolError('forbidden', 'only an owner of a document may delete it')
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.deleteDocument('Correct-Horse-9')).toBe(false)
    expect(session.state.status).toBe('open')
  })

  it('exports the current content as plain data', async () => {
    const link = new FakeLink()
    server(link)
    const exported = { format: 'claudia-export 1', app: 'computes', exported_at: 't', state_schema: 1, state: {} }
    link.handlers.export_content = () => exported
    const session = new Session(() => link)
    await session.open()
    expect(await session.exportContent()).toEqual(exported)
  })

  it('exports the current content as a Word, Excel or PowerPoint file', async () => {
    const link = new FakeLink()
    server(link)
    const exported = { format: 'xlsx', content_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', data: 'AAAA' }
    link.handlers.export_office = (params) => {
      expect(params).toEqual({ format: 'xlsx' })
      return exported
    }
    const session = new Session(() => link)
    await session.open()
    expect(await session.exportOffice('xlsx')).toEqual(exported)
  })

  it('asks for tracked changes only when told to, so apps without them see no new parameter', async () => {
    const link = new FakeLink()
    server(link)
    const seen: unknown[] = []
    link.handlers.export_office = (params) => {
      seen.push(params)
      return { format: 'odt', content_type: 'application/vnd.oasis.opendocument.text', data: 'AAAA' }
    }
    const session = new Session(() => link)
    await session.open()
    await session.exportOffice('odt', { trackedChanges: true })
    await session.exportOffice('odt', { trackedChanges: false })
    expect(seen).toEqual([{ format: 'odt', tracked_changes: true }, { format: 'odt' }])
  })

  it('tells us when somebody else leaves', async () => {
    const { session, link } = await opened()
    link.push('ephemeral', { kind: 'person_left', sender: 'ben', data: { user: 'ben' } })
    expect(session.state.notice?.text).toMatch(/ben left/)
  })

  it('reconnects when the ownership of the document changed under us', async () => {
    const first = new FakeLink()
    const second = new FakeLink()
    server(first)
    server(second)
    const links = [first, second]
    const session = new Session(() => links.shift()!)
    await session.open()
    first.push('ephemeral', { kind: 'owner_changed', sender: 'ben', data: { owner: 'ben' } })
    await session.settled()
    expect(session.state.notice?.text).toMatch(/ben is now the owner/)
    expect(session.state.status).toBe('open')
    expect(second.count('sheets')).toBe(1)
  })

  it('closes the session when the document was deleted out from under us', async () => {
    const { session, link } = await opened()
    link.push('ephemeral', { kind: 'document_deleted', sender: 'ann', data: {} })
    expect(session.state.status).toBe('closed')
    expect(session.state.notice?.text).toMatch(/deleted/)
  })
})

const PROPOSAL = {
  id: 1,
  kind: 'restore' as const,
  by: 'ben',
  checkpoint: 1,
  line: null,
  label: 'checkpoint “good”',
  opened_at: 0,
  expires_at: 900,
  policy: 'consensus' as const,
  group: ['ann', 'ben'],
  agreed: ['ben'],
}

describe('lines, and restoring with consent', () => {
  it('loads the lines and the restore policy, and lets you peek at one', async () => {
    const { session, link } = await opened()
    expect(session.state.lines).toEqual([{ name: 'main', head: 'main:3', active: true, forked_from: null }])
    expect(session.state.restorePolicy).toBe('consensus')
    expect(await session.peekLine('main')).toMatchObject({ line: 'main', revision: 'main:3' })
    expect(link.calls.find((c) => c.method === 'peek_line')!.params).toEqual({ line: 'main' })
  })

  it('suggests a restore; the server may carry it out at once', async () => {
    const { session, link } = await opened()
    expect(await session.proposeRestore(1)).toBe(true)
    expect(link.calls.find((c) => c.method === 'propose_restore')!.params).toEqual({ checkpoint: 1 })
    expect(session.state.proposal).toBeNull()
  })

  it('suggests switching to another line', async () => {
    const { session, link } = await opened()
    expect(await session.proposeSwitch('restore-1')).toBe(true)
    expect(link.calls.find((c) => c.method === 'propose_switch')!.params).toEqual({ line: 'restore-1' })
  })

  it('tracks an open suggestion from the restore_proposed event', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    expect(session.state.proposal).toEqual(PROPOSAL)
  })

  it('answers the open suggestion', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    expect(await session.answerRestore(true)).toBe(true)
    expect(link.calls.find((c) => c.method === 'answer_restore')!.params).toEqual({ agree: true })
  })

  it('clears the proposal and tells everybody once it is agreed', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    link.push('restore_resolved', { outcome: 'agreed' })
    expect(session.state.proposal).toBeNull()
    expect(session.state.notice).toMatchObject({ kind: 'info', text: expect.stringContaining('checkpoint “good”') })
  })

  it('warns when the suggestion was declined', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    link.push('restore_resolved', { outcome: 'declined' })
    expect(session.state.proposal).toBeNull()
    expect(session.state.notice).toMatchObject({ kind: 'warning', text: expect.stringMatching(/declined/i) })
  })

  it('says when the suggestion was withdrawn', async () => {
    const { session, link } = await opened()
    link.push('restore_proposed', PROPOSAL)
    link.push('restore_resolved', { outcome: 'withdrawn' })
    expect(session.state.notice?.text).toMatch(/withdrawn/i)
  })

  it('takes back the open suggestion', async () => {
    const { session, link } = await opened()
    expect(await session.withdrawRestore()).toBe(true)
    expect(link.count('withdraw_restore')).toBe(1)
  })

  it('discards the hidden lines and reloads what the screen shows', async () => {
    const { session, link } = await opened()
    expect(await session.discardSideHistory()).toBe(true)
    await session.settled()
    expect(link.count('discard_side_history')).toBe(1)
    expect(link.count('sheets')).toBe(2)
  })

  it('sets the restore policy', async () => {
    const { session, link } = await opened()
    expect(await session.setRestorePolicy('veto')).toBe(true)
    expect(session.state.restorePolicy).toBe('veto')
    expect(link.calls.find((c) => c.method === 'set_restore_policy')!.params).toEqual({ policy: 'veto' })
  })

  it('tells a returning person what happened to the line they were on', async () => {
    const link = new FakeLink()
    server(link)
    link.welcome = { ...link.welcome, returned: { by: 'ben', kind: 'restore', label: 'checkpoint “good”', agreed: ['ann', 'ben'] } }
    const session = new Session(() => link)
    await session.open()
    expect(session.state.notice?.text).toMatch(/ben restored to checkpoint “good”/i)
  })
})

describe('names, tables and queries (E6.5)', () => {
  const SALES = {
    name: 'Sales',
    scope: null,
    kind: 'range',
    header: true,
    grows: true,
    purpose: 'input',
    column_purposes: [],
    sheet: 's1',
    sheet_name: 'Budget',
    region: { sheet: 's1', row0: 0, col0: 0, row1: 3, col1: 2 },
    a1: 'Budget!A1:C4',
    anchor: null,
    columns: [],
    rows: 3,
  }

  it('loads the names with the document and loads them again when they change', async () => {
    const { session, link } = await opened()
    expect(session.state.names).toEqual([])
    link.handlers.names = () => ({ revision: 'main:4', names: [SALES] })
    link.push('names', { type: 'names' })
    await session.settled()
    expect(session.state.names.map((n) => n.name)).toEqual(['Sales'])
  })

  it('defines, renames and removes a name with the revision it saw', async () => {
    const { session, link } = await opened()
    link.handlers.define_name = () => ({ revision: 'main:4' })
    link.handlers.rename_name = () => ({ revision: 'main:5' })
    link.handlers.remove_name = () => ({ revision: 'main:6' })
    const draft = { name: 'Sales', scope: null, range: SALES.region, header: true, grows: true, purpose: 'input' as const }
    expect(await session.defineName(draft)).toBe(true)
    expect(link.last('define_name')).toEqual({ definition: draft, base: 'main:3' })
    expect(await session.renameName('Sales', 'Revenue', null)).toBe(true)
    expect(link.last('rename_name')).toMatchObject({ old: 'Sales', new: 'Revenue', scope: null })
    expect(await session.removeName('Revenue', null)).toBe(true)
    expect(link.last('remove_name')).toMatchObject({ name: 'Revenue', scope: null })
  })

  it('says why a name was refused and answers false', async () => {
    const { session, link } = await opened()
    link.handlers.define_name = () => {
      throw new ProtocolError('bad_request', 'define_name: B3 is a cell, not a name')
    }
    expect(await session.defineName({ name: 'B3', scope: null, header: false, grows: false, purpose: 'data' })).toBe(false)
    expect(session.state.notice?.text).toMatch(/cell, not a name/)
  })

  it('previews a query and puts one into a cell', async () => {
    const { session, link } = await opened()
    link.handlers.sql_preview = () => ({ ok: true, columns: ['Region'], rows: [['North']], row_count: 1, ms: 0.4 })
    link.handlers.define_sql = () => ({ revision: 'main:4' })
    expect(await session.sqlPreview('SELECT Region FROM Sales', 's1')).toMatchObject({ ok: true, row_count: 1 })
    expect(link.last('sql_preview')).toEqual({ query: 'SELECT Region FROM Sales', sheet: 's1', limit: 20 })
    expect(await session.defineSql('s1', 5, 0, 'SELECT 1', 'ByRegion')).toBe(true)
    expect(link.last('define_sql')).toEqual({ sheet: 's1', row: 5, col: 0, query: 'SELECT 1', name: 'ByRegion', base: 'main:3' })
  })

  it('asks again for the figure of a chart that reads a name when any cell changes', async () => {
    const { session, link } = await opened()
    link.handlers.chart_figure = () => ({ revision: 'main:3', figure: { data: [], layout: {} } })
    link.push('diagram', { id: 'c1', definition: { format: 1, id: 'c1', kind: 'bar', source: 'Sales', source_scope: null } })
    await session.ensureFigure('c1')
    expect(session.figureOf('c1')).not.toBeNull()
    link.push('cells', { sheet: 's2', positions: [[40, 40]], cells: [] })
    expect(session.figureOf('c1')).toBeNull()
  })
})

describe('searching', () => {
  const QUERY = { mode: 'text', text: '€', match_case: false, whole: 'none' } as const
  const ANSWER = { revision: 'main:3', matches: [], left_out: [], counts: { text: 0, formulas: 0, values: 0 }, total: 0, truncated: false, timed_out: false }

  it('looks in all three kinds on the scope it is given, and answers what the server says', async () => {
    const { session, link } = await opened()
    link.handlers.search_find = () => ANSWER
    expect(await session.searchFind(QUERY, ['text', 'formulas', 'values'], { sheet: 's1' })).toEqual(ANSWER)
    expect(link.last('search_find')).toEqual({ query: QUERY, kinds: ['text', 'formulas', 'values'], scope: { sheet: 's1' } })
  })

  it('does not make a noise when a search cannot be answered while she types', async () => {
    const { session, link } = await opened()
    link.handlers.search_find = () => {
      throw new ProtocolError('internal', 'down')
    }
    expect(await session.searchFind(QUERY, ['text'], {})).toBeNull()
    expect(session.state.notice).toBeNull()
  })

  it('asks what a replacement would change, without a base: it changes nothing', async () => {
    const { session, link } = await opened()
    link.handlers.search_preview = () => ({ revision: 'main:3', changes: [], skipped: [], total: 0 })
    await session.searchPreview({ ...QUERY, replace: [{ text: 'EUR ' }] }, ['text'], {}, [{ sheet: 's1', row: 0, col: 0, match: null }])
    expect(link.last('search_preview')).toEqual({
      query: { ...QUERY, replace: [{ text: 'EUR ' }] },
      kinds: ['text'],
      scope: {},
      leave: [{ sheet: 's1', row: 0, col: 0, match: null }],
    })
  })

  it('replaces against the revision it is looking at, and tells the person what the server refused', async () => {
    const { session, link } = await opened()
    link.handlers.search_replace = () => ({ revision: 'main:4', replaced: 2, skipped: [] })
    expect(await session.searchReplace({ ...QUERY, replace: [{ text: 'EUR ' }] }, ['text'], { sheet: 's1' }, [])).toEqual({ revision: 'main:4', replaced: 2, skipped: [] })
    expect(link.last('search_replace')).toMatchObject({ kinds: ['text'], scope: { sheet: 's1' }, leave: [], base: 'main:3' })
    link.handlers.search_replace = () => {
      throw new ProtocolError('bad_request', 'search_replace: that would change 20000 cells, at most 10000 at a time: narrow the search')
    }
    expect(await session.searchReplace(QUERY, ['text'], {}, [])).toBe(false)
    expect(session.state.notice?.text).toMatch(/narrow the search/)
  })
})

describe('random numbers, alternatives and following a computation (E6.21–E6.23)', () => {
  const TRACE = {
    revision: 'main:3',
    trace: {
      sheet: 's1',
      row: 7,
      col: 1,
      reach: 'group',
      cells: [[1, 1, 'input'], [7, 1, 'calc']],
      other: {},
      total: 2,
      connected: true,
      truncated: false,
    },
  }

  it('starts with the random state the server has', async () => {
    const link = new FakeLink()
    server(link)
    link.handlers.random_state = () => ({ revision: 'main:3', seed: 7, draw: 3 })
    const session = new Session(() => link, { retryDelays: [0], storage: memoryStorage() })
    await session.open()
    expect(session.state.random).toEqual({ seed: 7, draw: 3 })
  })

  it('opens a server that does not know random numbers yet', async () => {
    const link = new FakeLink()
    server(link)
    delete link.handlers.random_state
    const session = new Session(() => link, { retryDelays: [0], storage: memoryStorage() })
    await session.open()
    expect(session.state.random).toEqual({ seed: 0, draw: 0 })
  })

  it('follows a resample or a new seed that anybody made', async () => {
    const { session, link } = await opened()
    link.push('random', { type: 'random', seed: 5, draw: 2 })
    expect(session.state.random).toEqual({ seed: 5, draw: 2 })
  })

  it('resamples by one draw, or by as many as asked', async () => {
    const { session, link } = await opened()
    link.handlers.resample = () => ({ revision: 'main:4', draw: 1 })
    expect(await session.resample()).toBe(true)
    expect(link.last('resample')).toEqual({ steps: 1, base: 'main:3' })
    await session.resample(4)
    expect(link.last('resample').steps).toBe(4)
  })

  it('tells why a resample did not work', async () => {
    const { session, link } = await opened()
    link.handlers.resample = () => {
      throw new ProtocolError('forbidden', 'viewers cannot resample')
    }
    expect(await session.resample()).toBe(false)
    expect(session.state.notice?.text).toContain('only look')
  })

  it('sets a seed', async () => {
    const { session, link } = await opened()
    link.handlers.set_random_seed = () => ({ revision: 'main:4' })
    expect(await session.setRandomSeed(42)).toBe(true)
    expect(link.last('set_random_seed')).toEqual({ seed: 42, base: 'main:3' })
  })

  it('previews a distribution, and gives the reason when it cannot', async () => {
    const { session, link } = await opened()
    link.handlers.random_preview = () => ({ formula: '=RANDOM("normal",1,2)', excel: '=NORMINV(RAND(),1,2)', continuous: true, draws: [1, 2, 3] })
    const ok = await session.randomPreview({ distribution: 'normal', params: [1, 2] })
    expect(ok).toEqual({ formula: '=RANDOM("normal",1,2)', excel: '=NORMINV(RAND(),1,2)', continuous: true, draws: [1, 2, 3] })
    link.handlers.random_preview = () => {
      throw new ProtocolError('command_error', 'normal needs a spread above 0')
    }
    expect(await session.randomPreview({ distribution: 'normal', params: [1, -2] })).toEqual({ error: 'normal needs a spread above 0' })
    expect(session.state.notice).toBeNull() // a typo in the dialog is the dialog's to say, not a notice
  })

  it('asks for the table of outcomes of a cell', async () => {
    const { session, link } = await opened()
    link.handlers.outcome_table = () => ({ revision: 'main:3', table: { inputs: [], rows: [], sampled: false, sensitivity: [] } })
    expect(await session.outcomeTable('s1', 8, 1)).toEqual({ inputs: [], rows: [], sampled: false, sensitivity: [] })
    expect(link.last('outcome_table')).toEqual({ sheet: 's1', row: 8, col: 1, combine: 'all' })
    await session.outcomeTable('s1', 8, 1, 'pair')
    expect(link.last('outcome_table').combine).toBe('pair')
  })

  it('has no table for a cell that depends on no alternatives, and false when the server refuses', async () => {
    const { session, link } = await opened()
    link.handlers.outcome_table = () => ({ revision: 'main:3', table: null })
    expect(await session.outcomeTable('s1', 4, 1)).toBeNull()
    link.handlers.outcome_table = () => {
      throw new ProtocolError('command_error', 'pairing needs as many alternatives each')
    }
    expect(await session.outcomeTable('s1', 8, 1, 'pair')).toBe(false)
  })

  it('follows a computation: asks for the window and keeps what lights up', async () => {
    const { session, link } = await opened()
    link.handlers.trace = () => TRACE
    await session.follow('s1', 7, 1, 'group', [0, 0, 50, 15])
    expect(link.last('trace')).toEqual({ sheet: 's1', row: 7, col: 1, reach: 'group', window: [0, 0, 50, 15] })
    expect(session.state.trace?.cells).toEqual([[1, 1, 'input'], [7, 1, 'calc']])
    expect(session.state.trace?.connected).toBe(true)
  })

  it('stops following', async () => {
    const { session, link } = await opened()
    link.handlers.trace = () => TRACE
    await session.follow('s1', 7, 1, 'group', [0, 0, 50, 15])
    session.unfollow()
    expect(session.state.trace).toBeNull()
  })

  it('asks again when cells change while a computation is followed', async () => {
    const { session, link } = await opened()
    link.handlers.trace = () => TRACE
    await session.follow('s1', 7, 1, 'chain', [0, 0, 50, 15])
    link.push('cells', { sheet: 's1', positions: [[1, 1]], cells: [[1, 1, { t: 'int', v: 5 }]] })
    link.push('cells', { sheet: 's1', positions: [[2, 1]], cells: [[2, 1, { t: 'int', v: 6 }]] })
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(link.count('trace')).toBe(2) // once for the call, once for both changes
    expect(link.last('trace').reach).toBe('chain')
  })

  it('does not ask again when nothing is followed', async () => {
    const { link } = await opened()
    link.push('cells', { sheet: 's1', positions: [[1, 1]], cells: [[1, 1, { t: 'int', v: 5 }]] })
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(link.count('trace')).toBe(0)
  })

  it('stops following a computation whose cell cannot be found any more', async () => {
    const { session, link } = await opened()
    link.handlers.trace = () => TRACE
    await session.follow('s1', 7, 1, 'group', [0, 0, 50, 15])
    link.handlers.trace = () => {
      throw new ProtocolError('command_error', 'there is no such sheet')
    }
    link.push('sheets', {})
    await new Promise((resolve) => setTimeout(resolve, 5))
    expect(session.state.trace).toBeNull()
  })
})

describe('the language of the server’s own messages (D323)', () => {
  const openWith = async () => {
    const link = new FakeLink()
    link.handlers.set_locale = (params) => ({ locale: params.locale })
    link.handlers.snapshot = () => ({ state: { sheets: [], order: [] }, revision: 'main:3', app: 'computes' })
    const session = new Session(() => link, {})
    return { link, session }
  }

  it('tells the server when the person picks another language, and stops when the session closes', async () => {
    const { useI18n } = await import('~/lib/i18n')
    await useI18n().choose('en')
    const { link, session } = await openWith()
    await session.open().catch(() => undefined) // what the other handlers lack is not what this is about
    await useI18n().choose('de')
    expect(link.calls.filter((c) => c.method === 'set_locale')).toEqual([{ method: 'set_locale', params: { locale: 'de' } }])
    session.close()
    await useI18n().choose('en')
    expect(link.calls.filter((c) => c.method === 'set_locale')).toHaveLength(1)
  })

  it('tells a renewed connection the language that was chosen since the first one began', async () => {
    const { useI18n } = await import('~/lib/i18n')
    await useI18n().choose('de')
    const { link, session } = await openWith()
    link.welcome = { ...WELCOME, locale: 'en' }
    await session.open().catch(() => undefined)
    expect(link.calls.filter((c) => c.method === 'set_locale')).toEqual([{ method: 'set_locale', params: { locale: 'de' } }])
    session.close()
    await useI18n().choose('en')
  })
})
