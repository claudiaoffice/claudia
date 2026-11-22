// The AI page of the server settings (E7.11): what Apply needs, what it sends, and the words of a failure. The server
// puts its sentences for the administrator in English; the page says them in the person's language by the cause.
import { translate as t } from './i18n'

export const PROVIDERS = ['stand-in', 'local', 'claude'] as const
export type Provider = (typeof PROVIDERS)[number]

export interface AiForm {
  provider: Provider
  modelDir: string
  device: string
  maxTokens: number
  timeout: number
  model: string
  /** A key typed or pasted just now; empty keeps the saved one. */
  key: string
  removeKey: boolean
  /** The administrator confirmed that document content is sent to Anthropic. */
  confirmed: boolean
}

/** One cause of a failure, in the administrator's words. `detail` is what the server said, used where no sentence is known. */
export function failureSentence(reason: string, context: { model: string; seconds: number }, detail: string): string {
  switch (reason) {
    case 'key_refused':
      return t('Anthropic refused the key.')
    case 'credit_used_up':
      return t('The credit balance at Anthropic is used up.')
    case 'rate_limited':
      return t("Anthropic's rate limit was reached.")
    case 'overloaded':
      return t('Anthropic is overloaded at the moment.')
    case 'unreachable':
      return t('Anthropic cannot be reached from this server.')
    case 'unknown_model':
      return t('Anthropic does not know the model “{model}”.', { model: context.model })
    case 'timed_out':
      return t('Anthropic did not answer within {seconds} seconds.', { seconds: context.seconds })
    default:
      return detail
  }
}

/** What follows from a last error: nothing switches by itself, so the administrator has to. */
export function failureHint(reason: string): string {
  return reason === 'credit_used_up'
    ? t('Questions to Claude fail until credit is added or another provider is chosen.')
    : t('Questions to Claude fail until this is solved or another provider is chosen.')
}

/** What Apply needs, given what the server has saved: Claude needs a key, and the sentence when it was not Claude before. */
export function applyState(form: AiForm, saved: { provider: string; key_set: boolean }) {
  if (form.provider === 'local') return { needsKey: false, needsConfirm: false, canApply: form.modelDir.trim() !== '' }
  if (form.provider !== 'claude') return { needsKey: false, needsConfirm: false, canApply: true }
  const needsKey = form.key.trim() === '' && (form.removeKey || !saved.key_set)
  const needsConfirm = saved.provider !== 'claude'
  return { needsKey, needsConfirm, canApply: !needsKey && (!needsConfirm || form.confirmed) }
}

/** The `claude` part of what `PUT /settings/ai` takes: the key is sent only when one was typed. */
export function claudePayload(form: AiForm) {
  return {
    model: form.model.trim(),
    ...(form.key.trim() ? { key: form.key.trim() } : {}),
    ...(form.removeKey && !form.key.trim() ? { remove_key: true } : {}),
    ...(form.confirmed ? { confirm: true } : {}),
  }
}
