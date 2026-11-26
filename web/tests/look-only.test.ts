// What someone who may only look is told when she tries a change (CODE-98): the sentence is written once, with the rule
// "role: editor or owner" that it belongs to (D1650), the session says it, and no component writes it out itself.
import { readdirSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { Session } from '~/lib/session'

const LOOK_ONLY = 'You can only look at this document.'

describe('telling someone that she may only look', () => {
  it('is a warning that she can only look at this document', () => {
    const session = new Session(() => {
      throw new Error('a notice needs no connection')
    })
    session.tellLookOnly()
    expect(session.state.notice).toMatchObject({ kind: 'warning', text: LOOK_ONLY })
  })
})

describe('where the sentence is written', () => {
  const app = new URL('../app/', import.meta.url)
  const sources = readdirSync(app, { recursive: true, encoding: 'utf8' }).filter((path) => /\.(vue|ts)$/.test(path))

  it('is only in the rules of what fits, and every part of the app asks the session to say it', () => {
    const writers = sources.filter((path) => readFileSync(new URL(path, app), 'utf8').includes(LOOK_ONLY))
    expect(writers).toEqual(['lib/fits/conditions.ts'])
  })
})
