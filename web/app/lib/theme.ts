// Dark/light mode (UX-05): a `data-theme` attribute on `<html>`, so `tokens.css` can override the light tokens under
// `:root[data-theme='dark']` without waiting on `prefers-color-scheme` alone (a person can still ask for dark on a
// light system, or the reverse — the View menu item D120 asks for needs a tri-state: Light, Dark, or Match system).
import { onBeforeUnmount, onMounted, ref, watch } from 'vue' // only the Vue wiring at the end uses these

export type ThemeChoice = 'light' | 'dark' | 'system'
const KEY = 'claudia.theme'
const CHOICES: readonly ThemeChoice[] = ['light', 'dark', 'system']

export function readStoredTheme(storage: Pick<Storage, 'getItem'> = safeStorage()): ThemeChoice {
  try {
    const value = storage.getItem(KEY)
    return (CHOICES as readonly string[]).includes(value ?? '') ? (value as ThemeChoice) : 'system'
  } catch {
    return 'system'
  }
}

export function storeTheme(choice: ThemeChoice, storage: Pick<Storage, 'setItem'> = safeStorage()): void {
  try {
    storage.setItem(KEY, choice)
  } catch {
    /* private window: nothing to remember, the choice still applies for this visit */
  }
}

/** What `choice` resolves to right now, given whether the system is in dark mode. */
export function resolvedTheme(choice: ThemeChoice, systemPrefersDark: boolean): 'light' | 'dark' {
  return choice === 'system' ? (systemPrefersDark ? 'dark' : 'light') : choice
}

/** Applies the resolved theme to `root` (the `<html>` element in real use). `'light'` clears the attribute: it is
 * `tokens.css`'s default, not a value to carry around. */
export function applyTheme(root: { setAttribute(name: string, value: string): void; removeAttribute(name: string): void }, resolved: 'light' | 'dark'): void {
  if (resolved === 'dark') root.setAttribute('data-theme', 'dark')
  else root.removeAttribute('data-theme')
}

function safeStorage(): Pick<Storage, 'getItem' | 'setItem'> {
  try {
    return localStorage
  } catch {
    const memory = new Map<string, string>()
    return { getItem: (k) => memory.get(k) ?? null, setItem: (k, v) => void memory.set(k, v) }
  }
}

// ------------------------------------------------------------------------------------------------------- Vue wiring

/**
 * The View menu's "Dark mode" item is one checkbox (the schema gives it one line), not a three-way pick: before it
 * is ever touched the page follows the system, and the first click fixes an explicit choice (D120, UX-05).
 */
export function useTheme() {
  const choice = ref<ThemeChoice>(readStoredTheme())
  const systemPrefersDark = ref(false)
  let media: MediaQueryList | null = null
  const onChange = () => (systemPrefersDark.value = media!.matches)

  onMounted(() => {
    if (typeof matchMedia !== 'function') return
    media = matchMedia('(prefers-color-scheme: dark)')
    systemPrefersDark.value = media.matches
    media.addEventListener('change', onChange)
  })
  onBeforeUnmount(() => media?.removeEventListener('change', onChange))

  function apply() {
    applyTheme(document.documentElement, resolvedTheme(choice.value, systemPrefersDark.value))
  }
  onMounted(apply)
  watch(systemPrefersDark, apply)

  const dark = () => resolvedTheme(choice.value, systemPrefersDark.value) === 'dark'
  function toggle() {
    choice.value = dark() ? 'light' : 'dark'
    storeTheme(choice.value)
    apply()
  }
  return { dark, toggle }
}
