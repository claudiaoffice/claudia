// A browser whose storages are there but refuse every call, as a full storage or an old private window does; for the
// tests that check a module still works through `safeStorage` there (CODE-36).

function refuse(): never {
  throw new Error('QuotaExceededError')
}

export function refuseEveryCall(): void {
  for (const name of ['localStorage', 'sessionStorage']) {
    ;(globalThis as Record<string, unknown>)[name] = { getItem: refuse, setItem: refuse, removeItem: refuse }
  }
}

/** Back to no browser storage at all, as in Node. */
export function forgetBrowser(): void {
  delete (globalThis as Record<string, unknown>).localStorage
  delete (globalThis as Record<string, unknown>).sessionStorage
}
