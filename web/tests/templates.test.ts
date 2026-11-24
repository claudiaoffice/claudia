import { describe, expect, it } from 'vitest'
import {
  cardMeta,
  createLabel,
  fetchTemplates,
  languageName,
  layoutsLabel,
  needsChoice,
  startFromTemplate,
  type TemplateCard,
} from '~/lib/templates'
import { createTranslator } from '~/lib/i18n'

const t = createTranslator({})

const basic: TemplateCard = { id: 'basic', name: 'Basic', purpose: 'A single empty slide', language: 'en', builtin: true, layouts: ['Basic'] }
const talk: TemplateCard = { id: 'conference-talk', name: 'Conference talk', purpose: 'A 20-minute talk', language: 'de', builtin: false, layouts: ['Title', 'Two lists'] }

function fake(answer: unknown, status = 200) {
  const seen: { url: string; init?: RequestInit }[] = []
  const fetchImpl = (async (url: string, init?: RequestInit) => {
    seen.push({ url: String(url), init })
    return { status, ok: status < 400, json: async () => answer } as Response
  }) as typeof fetch
  return { fetchImpl, seen }
}

describe('the words of a template card', () => {
  it('counts the layouts, one by one', () => {
    expect(layoutsLabel(basic, t)).toBe('1 layout')
    expect(layoutsLabel(talk, t)).toBe('2 layouts')
  })

  it('names a language as its own people write it, whatever the language of the page, or gives the tag', () => {
    expect(languageName('de')).toBe('Deutsch')
    expect(languageName('en')).toBe('English')
    expect(languageName('en-GB')).toBe('British English')
    expect(languageName('zz-invalid-tag-x')).toBe('zz-invalid-tag-x')
  })

  it('says under a card how many layouts it has and in which language, and that the first is built in', () => {
    expect(cardMeta(talk, t)).toBe('2 layouts · Deutsch')
    expect(cardMeta(basic, t)).toBe('built in')
  })

  it('names the button after the template', () => {
    expect(createLabel(talk, t)).toBe('Create from “Conference talk”')
  })
})

describe('asking the server', () => {
  it('lists the templates in the language of the person', async () => {
    const { fetchImpl, seen } = fake({ templates: [basic, talk] })
    await expect(fetchTemplates('https://x.test', 'de', fetchImpl)).resolves.toEqual({ templates: [basic, talk] })
    expect(seen[0]!.url).toBe('https://x.test/api/templates?locale=de')
  })

  it('answers with the sentence of the server when it refuses', async () => {
    const { fetchImpl } = fake({ detail: 'an access secret is needed' }, 403)
    await expect(fetchTemplates('https://x.test', 'en', fetchImpl)).resolves.toEqual({ error: 'an access secret is needed' })
  })

  it('has nothing to choose from on a server that does not know templates', async () => {
    const { fetchImpl } = fake({}, 404)
    await expect(fetchTemplates('https://x.test', 'en', fetchImpl)).resolves.toEqual({ templates: [] })
  })

  it('starts a presentation from a template as an upload to create from', async () => {
    const { fetchImpl, seen } = fake({ upload: 'tok1', name: 'talk.claudia-export.zip', size: 10, hosted: true })
    await expect(startFromTemplate('https://x.test', 'conference/talk', 'de', fetchImpl)).resolves.toEqual({ upload: 'tok1' })
    expect([seen[0]!.init?.method, seen[0]!.url]).toEqual(['POST', 'https://x.test/api/templates/conference%2Ftalk/upload?locale=de'])
  })

  it('says why a presentation could not be started', async () => {
    const { fetchImpl } = fake({ detail: 'too many uploads waiting' }, 429)
    await expect(startFromTemplate('https://x.test', 'basic', 'en', fetchImpl)).resolves.toEqual({ error: 'too many uploads waiting' })
  })
})

describe('when there is something to choose', () => {
  it('has nothing to choose when the built-in template is all there is', () => {
    expect(needsChoice([basic])).toBe(false)
    expect(needsChoice([])).toBe(false)
  })

  it('has a choice as soon as there is another template', () => {
    expect(needsChoice([basic, talk])).toBe(true)
  })
})
