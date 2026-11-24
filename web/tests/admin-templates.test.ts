import { describe, expect, it } from 'vitest'
import {
  addSentence,
  checkDetails,
  removeSentence,
  type TemplateCheck,
  type TemplateView,
  type TemplatesPage,
} from '~/lib/admin-templates'
import { createAdminApi } from '~/lib/admin-api'
import { createTranslator } from '~/lib/i18n'

const t = createTranslator({})

const basic: TemplateView = { id: 'basic', name: 'Basic', purpose: 'Slides with nothing prepared', language: 'en', builtin: true, layouts: ['Basic'], removable: false }
const talk: TemplateView = {
  id: 'conference-talk',
  name: 'Conference talk',
  purpose: 'Talks of twenty minutes',
  language: 'de',
  builtin: false,
  layouts: ['Title', 'Two lists'],
  removable: true,
}
const page: TemplatesPage = { format: 1, templates: [basic, talk] }

describe('what adding and removing say before they happen', () => {
  const check: TemplateCheck = { name: 'Conference talk', purpose: 'Talks of twenty minutes', language: 'de', layouts: ['Title', 'Two lists'] }

  it('says what the file would become, and for whom it is there', () => {
    expect(addSentence(check, 'this server', t)).toBe(
      'Adds “Conference talk” with 2 layouts to this server. Everyone who makes a presentation here can start from it.',
    )
  })

  it('names the language of the file in its own words and the layouts it has, before anything is added', () => {
    expect(checkDetails(check)).toBe('Deutsch · Title, Two lists')
  })

  it('says that removing keeps what was made with the template', () => {
    expect(removeSentence(talk, t)).toBe(
      'Removes “Conference talk” from this server. Presentations made from it keep their layouts, styles and colours.',
    )
  })
})

describe('the admin API for templates', () => {
  function fake(answer: unknown, status = 200) {
    const seen: { url: string; init?: RequestInit }[] = []
    const api = createAdminApi((async (url: string, init?: RequestInit) => {
      seen.push({ url: String(url), init })
      return { status, ok: status < 400, json: async () => answer } as Response
    }) as typeof fetch)
    return { api, seen }
  }

  it('asks for the page with the administrator’s token', async () => {
    const { api, seen } = fake(page)
    await expect(api.templatesPage('tok')).resolves.toEqual(page)
    expect([seen[0]!.init?.method, seen[0]!.url]).toEqual(['GET', '/api/admin/templates'])
    expect((seen[0]!.init?.headers as Record<string, string>).authorization).toBe('Bearer tok')
  })

  it('sends the file as the body, with its name in a header, to check it and again to add it', async () => {
    const { api, seen } = fake({})
    const file = new Blob([new Uint8Array([1, 2, 3])])
    await api.checkTemplate('tok', file, 'talk.claudia-export.zip')
    await api.addTemplate('tok', file, 'talk.claudia-export.zip')
    expect(seen.map((s) => [s.init?.method, s.url])).toEqual([
      ['POST', '/api/admin/templates/check'],
      ['POST', '/api/admin/templates'],
    ])
    expect(seen.every((s) => s.init?.body === file)).toBe(true)
    expect((seen[0]!.init?.headers as Record<string, string>)['x-claudia-name']).toBe('talk.claudia-export.zip')
  })

  it('names a template by its id in the address when removing it', async () => {
    const { api, seen } = fake(page)
    await api.removeTemplate('tok', 'a/b')
    expect([seen[0]!.init?.method, seen[0]!.url]).toEqual(['DELETE', '/api/admin/templates/a%2Fb'])
  })
})
