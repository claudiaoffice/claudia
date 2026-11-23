import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { ProtocolError, type LinkLike } from '~/lib/protocol'
import { Session } from '~/lib/session'
import { SlideSession } from '~/lib/slide-session'
import { TextSession } from '~/lib/text-session'
import { DESCRIPTIONS, FakeServer, type AppName } from './support/fake-server'

// E11.7: the one fake server of the web tests, and what holds it to the server's own description of its protocol.

const APPS: AppName[] = ['computes', 'composes', 'creates']

/** A test that asks for what the real server would refuse clears the note the fake made of it, or it would fail. */
function forgive(server: FakeServer) {
  const seen = [...server.violations]
  server.violations.length = 0
  return seen
}

describe('what the fake server refuses, as the real one does', () => {
  it('has no method the description does not have', async () => {
    const server = new FakeServer('computes')
    await expect(server.request('set_cell', { sheet: 's1' })).rejects.toMatchObject({ code: 'unknown_method' })
    expect(forgive(server)).toEqual(['computes has no method "set_cell"'])
  })

  it('has no parameter that the description does not have', async () => {
    const server = new FakeServer('computes').on('set_cells', { revision: 'main:4' })
    await expect(server.request('set_cells', { sheet: 's1', cells: [], row: 3 })).rejects.toMatchObject({ code: 'bad_request' })
    expect(forgive(server)).toEqual(['set_cells: unknown parameter "row"'])
  })

  it('wants the parameters the description says are required', async () => {
    const server = new FakeServer('computes').on('set_cells', { revision: 'main:4' })
    await expect(server.request('set_cells', { sheet: 's1' })).rejects.toBeInstanceOf(ProtocolError)
    expect(forgive(server)).toEqual(['set_cells: missing parameter "cells"'])
  })

  it('wants a parameter of the kind the description says (the kinds the protocol itself defines)', async () => {
    const server = new FakeServer('computes').on('set_cells', { revision: 'main:4' })
    await expect(server.request('set_cells', { sheet: 's1', cells: 'A1' })).rejects.toBeInstanceOf(ProtocolError)
    expect(forgive(server)).toEqual(['set_cells: cells is not a list'])
  })

  it('takes a request that keeps to the description, and answers it with the handler of the test', async () => {
    const server = new FakeServer('computes').on('set_cells', ({ sheet }: any) => ({ revision: 'main:4', sheet }))
    expect(await server.request('set_cells', { sheet: 's1', cells: [], base: 'main:3' })).toEqual({ revision: 'main:4', sheet: 's1' })
    expect(server.violations).toEqual([])
  })

  it('does not let a method that is described but has no answer pass for one: it is unknown, as on an older server', async () => {
    const server = new FakeServer('computes')
    await expect(server.request('undo')).rejects.toMatchObject({ code: 'unknown_method' })
    expect(server.violations).toEqual([])
  })

  it('refuses to push an event the description does not have', () => {
    const server = new FakeServer('creates')
    expect(() => server.push('slide_moved', {})).toThrow('creates has no event "slide_moved"')
    expect(forgive(server)).toEqual(['creates has no event "slide_moved" in its description'])
    server.push('slides', {}) // a state event of the apps is in it
  })

  it('records what was asked, and sends the events it is told to push to what listens', async () => {
    const server = new FakeServer('creates')
    const heard: [string, unknown][] = []
    server.onEvent((name, data) => heard.push([name, data]))
    await server.request('slides')
    await server.request('slide', { slide: 's1' })
    await server.request('slide', { slide: 's2' })
    server.push('ephemeral', { kind: 'typing' })
    expect(server.methods()).toEqual(['slides', 'slide', 'slide'])
    expect(server.count('slide')).toBe(2)
    expect(server.last('slide')).toEqual({ slide: 's2' })
    expect(server.sent('slide')).toEqual([{ slide: 's1' }, { slide: 's2' }])
    expect(heard).toEqual([['ephemeral', { kind: 'typing' }]])
  })

  it('fails the test afterwards when a session was refused and carried on (setup.ts)', async () => {
    // A session tells the person that a request failed and goes on; the note the fake made of it is what fails the test.
    const server = new FakeServer('computes')
    await server.request('no_such_method').catch(() => undefined)
    expect(server.violations).toHaveLength(1)
    forgive(server)
  })
})

describe('what a document needs to open, for each app, without a handler of the test', () => {
  const sessions: Record<AppName, (link: () => LinkLike) => { open(): Promise<void>; state: { status: string } }> = {
    computes: (link) => new Session(link, { retryDelays: [] }),
    composes: (link) => new TextSession(link, { retryDelays: [] }),
    creates: (link) => new SlideSession(link, { retryDelays: [] }),
  }

  for (const app of APPS) {
    it(`opens a ${app} document, and asks for nothing the server does not have`, async () => {
      const server = new FakeServer(app)
      const session = sessions[app](() => server)
      await session.open()
      expect(session.state.status).toBe('open')
      expect(server.violations).toEqual([])
      expect(server.count('log')).toBe(1)
    })
  }
})

describe('the description the fake uses', () => {
  it('is one file for each app, from the one protocol', () => {
    expect(new Set(APPS.map((app) => DESCRIPTIONS[app].protocol)).size).toBe(1)
    for (const app of APPS) expect(DESCRIPTIONS[app].app).toBe(app)
  })

  it('has every method that the sessions and their parts call', () => {
    // A method that is renamed on the server, or in the page, breaks this and not only the test that uses it.
    const root = fileURLToPath(new URL('../app', import.meta.url))
    // Only `lib`: the components go through the sessions (the one `request` in a component is the browser's wake lock).
    const files = readdirSync(`${root}/lib`)
      .map((name) => `${root}/lib/${name}`)
      .filter((path) => path.endsWith('.ts'))
    const called = new Map<string, string>()
    const shape = /\b(?:write|attempt|changed|asked|request|optional|port\.write)\b(?:<.*?>)?\(\s*'([a-z_0-9]+)'/g
    for (const path of files) {
      for (const match of readFileSync(path, 'utf8').matchAll(shape)) called.set(match[1]!, path.slice(root.length + 1))
    }
    const described = new Set(APPS.flatMap((app) => Object.keys(DESCRIPTIONS[app].methods)))
    const missing = [...called].filter(([method]) => !described.has(method)).map(([method, where]) => `${method} (${where})`)
    expect(called.size).toBeGreaterThan(100) // the scan found the calls
    expect(missing).toEqual([])
  })

  it('takes a revision for each change that the page bases on one, and for no request it sends without', () => {
    // `write` adds `base` to a change; a method that does not name it would be sent a parameter it does not know.
    for (const app of APPS) {
      const { methods } = DESCRIPTIONS[app]
      for (const name of ['undo', 'redo', 'lock', 'chat', 'save_checkpoint', 'propose_restore']) {
        expect(methods[name]?.params.map((p) => p.name) ?? [], `${app} ${name}`).not.toContain('base')
      }
    }
  })
})
