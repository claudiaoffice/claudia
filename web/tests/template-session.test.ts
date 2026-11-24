// What a presentation's session does about templates (E10.4, E10.22, D1539, D1540): Change theme, Change template and
// the count of what the latter would do, and Save as template.
import { describe, expect, it } from 'vitest'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Welcome } from '~/lib/protocol'
import { SlideSession } from '~/lib/slide-session'

const WELCOME: Welcome = {
  user: 'ann',
  role: 'owner',
  doc: 'talk',
  app: 'creates',
  branch: 'main',
  revision: 'main:0',
  id: 1,
  color: '#e6194b',
  people: [],
  presence: [],
  checkpoints: [],
  limits: { max_text: 32767 },
  branches: [{ name: 'main', head: 'main:0', active: true, forked_from: null }],
  proposal: null,
  returned: null,
}

class FakeLink implements LinkLike {
  calls: { method: string; params: any }[] = []
  handlers: Record<string, (params: any) => any> = {}
  events: EventHandler[] = []
  closers: CloseHandler[] = []
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
  onClose(h: CloseHandler) {
    this.closers.push(h)
  }
  close() {}
  sent(method: string) {
    return this.calls.filter((c) => c.method === method).map((c) => c.params)
  }
}

const STYLE = { id: 'body-text', name: 'Body text', purpose: '', based_on: null, to_name: false, kind: 'paragraph', css: {}, computed: {}, resolved: { color: '#1f1a33' } }
const PREVIEW = { styles_changed: 9, styles_added: 0, styles_kept: 2, colours_changed: 1, colours_added: 0, layouts_matched: 5, layouts_added: 1, layouts_kept: 1, slides_reframed: 11, slides_unchanged: 6 }
const SAVED = { format: 'claudia-template', filename: 'talk.claudia-export.zip', content_type: 'application/zip', data: 'UEs=', parts: ['content'] }

async function opened(extra: Record<string, (params: any) => any> = {}, role = 'owner') {
  const link = new FakeLink()
  link.handlers = {
    slides: () => [{ id: 's1', objects: 0 }],
    slide: ({ slide }) => ({ revision: 'main:0', slide, objects: [] }),
    shapes: () => ({ library: [], document: [] }),
    images: () => [],
    styles: () => [STYLE],
    style_model: () => ({}),
    palette: () => ({ type: 'palette', roles: [], readings: [] }),
    log: () => [],
    chat_log: () => [],
    checkpoints: () => [],
    audit_log: () => [],
    history: () => ({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
    branches: () => [{ name: 'main', head: 'main:0', active: true, forked_from: null }],
    restore_policy: () => ({ policy: 'consensus' }),
    presence: () => ({}),
    ...extra,
  }
  const session = new SlideSession(() => link, { retryDelays: [1] })
  await session.open()
  session.state.me.role = role
  return { link, session }
}

describe('Change theme and Change template', () => {
  it('send the chosen template with the revision the person sees, and say whether anything changed', async () => {
    const { link, session } = await opened({ change_theme: () => ({ changed: true, revision: 'main:1' }) })
    await expect(session.changeTheme('conference-talk')).resolves.toEqual({ changed: true })
    expect(link.sent('change_theme')).toEqual([{ template: 'conference-talk', base: 'main:0' }])
    session.close()
  })

  it('change the template the same way', async () => {
    const { link, session } = await opened({ change_template: () => ({ changed: true, revision: 'main:1' }) })
    await expect(session.changeTemplate('basic')).resolves.toEqual({ changed: true })
    expect(link.sent('change_template')).toEqual([{ template: 'basic', base: 'main:0' }])
    session.close()
  })

  it('are refused before anything is sent to someone who may only look', async () => {
    const { link, session } = await opened({ change_theme: () => ({ changed: true, revision: 'main:1' }) }, 'viewer')
    await expect(session.changeTheme('basic')).resolves.toBe(false)
    expect(link.sent('change_theme')).toEqual([])
    session.close()
  })
})

describe('the count of what Change template would do', () => {
  it('asks the server and does not change the document', async () => {
    const { link, session } = await opened({ template_change_preview: () => PREVIEW })
    await expect(session.templateChangePreview('conference-talk')).resolves.toEqual(PREVIEW)
    expect(link.sent('template_change_preview')).toEqual([{ template: 'conference-talk' }])
    session.close()
  })

  it('is false, after telling the person, when the server has no such template', async () => {
    const { session } = await opened({
      template_change_preview: () => {
        throw new ProtocolError('command_error', 'there is no template')
      },
    })
    await expect(session.templateChangePreview('nothing')).resolves.toBe(false)
    expect(session.state.notice?.text).toBe('there is no template')
    session.close()
  })
})

describe('Save as template', () => {
  it('sends the note and answers the file', async () => {
    const { link, session } = await opened({ save_as_template: () => SAVED })
    await expect(session.saveAsTemplate({ name: 'Talk', purpose: 'Talks', language: 'en' })).resolves.toEqual(SAVED)
    expect(link.sent('save_as_template')).toEqual([{ name: 'Talk', purpose: 'Talks', language: 'en' }])
    session.close()
  })
})
