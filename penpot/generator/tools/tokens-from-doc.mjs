// A resolver over a tokens.json (the multi-set DTCG document of a .penpot file): the value of a token under the
// themes ("Group/Name") that are active, later sets overriding earlier ones, references followed.
export function buildTokensFromDoc(doc, themeNames) {
  const meta = doc.$metadata
  const themes = doc.$themes
  const active = themeNames ?? meta.activeThemes
  const sets = new Set()
  for (const t of themes) if (active.includes(`${t.group}/${t.name}`)) for (const [s, st] of Object.entries(t.selectedTokenSets)) if (st === 'enabled') sets.add(s)
  const order = meta.tokenSetOrder.filter((s) => sets.has(s))
  const flat = (node, path, out) => {
    if (node && typeof node === 'object' && '$value' in node) out[path.join('.')] = node
    else if (node && typeof node === 'object') for (const [k, v] of Object.entries(node)) if (!k.startsWith('$')) flat(v, [...path, k], out)
    return out
  }
  const merged = {}
  for (const s of order) Object.assign(merged, flat(doc[s], [], {}))
  const resolve = (v) => {
    if (typeof v === 'string') {
      const m = v.match(/^\{([\w.-]+)\}$/)
      return m ? resolve(merged[m[1]].$value) : v
    }
    if (Array.isArray(v)) return v.map(resolve)
    if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, resolve(x)]))
    return v
  }
  return { value: (name) => resolve(merged[name].$value), sets: order }
}
