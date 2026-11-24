import { describe, expect, it } from 'vitest'
import { failureHint, failureSentence, claudePayload, applyState, type AiForm } from '~/lib/admin-ai'

const form = (over: Partial<AiForm> = {}): AiForm => ({
  provider: 'claude',
  modelDir: '',
  device: 'GPU',
  maxTokens: 512,
  timeout: 180,
  model: 'claude-sonnet-5-5',
  key: '',
  removeKey: false,
  confirmed: false,
  ...over,
})
const saved = { provider: 'local', key_set: false }

describe('the words of a failure, for the administrator', () => {
  it('has a sentence for every cause, with the model and the time where they belong', () => {
    const ctx = { model: 'claude-x', seconds: 180 }
    expect(failureSentence('key_refused', ctx, '')).toBe('Anthropic refused the key.')
    expect(failureSentence('credit_used_up', ctx, '')).toBe('The credit balance at Anthropic is used up.')
    expect(failureSentence('rate_limited', ctx, '')).toBe("Anthropic's rate limit was reached.")
    expect(failureSentence('overloaded', ctx, '')).toBe('Anthropic is overloaded at the moment.')
    expect(failureSentence('unreachable', ctx, '')).toBe('Anthropic cannot be reached from this server.')
    expect(failureSentence('unknown_model', ctx, '')).toBe('Anthropic does not know the model “claude-x”.')
    expect(failureSentence('timed_out', ctx, '')).toBe('Anthropic did not answer within 180 seconds.')
  })

  it('keeps what the server said for a cause it has no sentence for', () => {
    expect(failureSentence('other', { model: '', seconds: 1 }, 'Anthropic answered with an error: 500')).toBe('Anthropic answered with an error: 500')
  })

  it('says what to do: the administrator decides, nothing switches by itself', () => {
    expect(failureHint('credit_used_up')).toBe('Questions to Claude fail until credit is added or another provider is chosen.')
    expect(failureHint('overloaded')).toBe('Questions to Claude fail until this is solved or another provider is chosen.')
  })
})

describe('when Apply is possible', () => {
  it('asks for a key and the sentence when Claude is chosen from another provider', () => {
    expect(applyState(form(), saved)).toEqual({ needsKey: true, needsConfirm: true, canApply: false })
    expect(applyState(form({ key: 'sk-ant-x' }), saved)).toMatchObject({ needsKey: false, needsConfirm: true, canApply: false })
    expect(applyState(form({ key: 'sk-ant-x', confirmed: true }), saved).canApply).toBe(true)
  })

  it('does not ask for the sentence again while Claude is already the provider, and keeps the saved key', () => {
    expect(applyState(form(), { provider: 'claude', key_set: true })).toEqual({ needsKey: false, needsConfirm: false, canApply: true })
  })

  it('asks for nothing of Claude when another provider is chosen', () => {
    expect(applyState(form({ provider: 'stand-in' }), saved).canApply).toBe(true)
    expect(applyState(form({ provider: 'local' }), saved).canApply).toBe(false) // the local model needs its folder
    expect(applyState(form({ provider: 'local', modelDir: '/models/qwen' }), saved).canApply).toBe(true)
  })
})

describe('what is sent', () => {
  it('sends the key only when one was typed, and the confirmation only when it was given', () => {
    expect(claudePayload(form({ key: 'sk-ant-x', confirmed: true }))).toEqual({ model: 'claude-sonnet-5-5', key: 'sk-ant-x', confirm: true })
    expect(claudePayload(form())).toEqual({ model: 'claude-sonnet-5-5' })
    expect(claudePayload(form({ removeKey: true }))).toEqual({ model: 'claude-sonnet-5-5', remove_key: true })
  })
})
