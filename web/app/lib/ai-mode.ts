// How the AI treats a request (D262): *act* does what was asked at once, *suggest* shows it first and leaves the
// decision to the person. Each person chooses for each document, and the choice is theirs alone — so it lives in
// this browser, next to the person, and goes to the server with every chat message (`ai_mode`, protocol v-chat).
// Anybody who never chose gets *suggest*: a person has to opt in to an AI that edits for them.

export type AiMode = 'act' | 'suggest'
export const DEFAULT_AI_MODE: AiMode = 'suggest'

/** What the browser keeps; narrower than `Storage` so a test can hand in a map. */
export type ModeStorage = { getItem(key: string): string | null; setItem(key: string, value: string): void }

/** One key per server and document. JSON, so that `a:1`/`b` and `a`/`1:b` can never meet. */
export function aiModeKey(host: string, doc: string): string {
  return `claudia.ai-mode.${JSON.stringify([host, doc])}`
}

/** The stored choice for this document, or *suggest*. Anything else in the storage counts as no choice. */
export function readAiMode(host: string, doc: string, storage: ModeStorage = safeStorage()): AiMode {
  try {
    return storage.getItem(aiModeKey(host, doc)) === 'act' ? 'act' : DEFAULT_AI_MODE
  } catch {
    return DEFAULT_AI_MODE
  }
}

export function storeAiMode(host: string, doc: string, mode: AiMode, storage: ModeStorage = safeStorage()): void {
  try {
    storage.setItem(aiModeKey(host, doc), mode)
  } catch {
    /* private window: the choice still holds for this visit */
  }
}

/** The browser's storage, or one that forgets when the page closes, where the browser has none. */
export function safeStorage(): ModeStorage {
  try {
    return localStorage
  } catch {
    const memory = new Map<string, string>()
    return { getItem: (k) => memory.get(k) ?? null, setItem: (k, v) => void memory.set(k, v) }
  }
}
