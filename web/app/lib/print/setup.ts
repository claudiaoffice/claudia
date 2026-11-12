// The choices of the print preview's bar (paper, orientation, margins) and the page setup they make (D904, D906).
// Plain functions over the layout library's paper sizes, so the menu and the stored setup cannot disagree.
import { PAPER_SIZES, umToMpt, type PageSetupData } from '@claudia/layout'

/** A new text's page (the server's default, for a server that does not know pages yet). */
export const DEFAULT_PAGE: PageSetupData = {
  paper: 'a4',
  width: 595276,
  height: 841890,
  orientation: 'portrait',
  margins: [70866, 70866, 70866, 70866],
  page_numbers: false,
}

/** The margins the bar offers, all four sides alike. */
export const MARGINS: readonly { id: string; label: string; mpt: number }[] = [
  { id: 'narrow', label: '1.27 cm', mpt: umToMpt(12_700) },
  { id: 'normal', label: '2.5 cm', mpt: umToMpt(25_000) },
  { id: 'wide', label: '3.5 cm', mpt: umToMpt(35_000) },
]

/** The bar's label for a paper: "A4 · 210 × 297 mm", or the custom size. */
export function paperLabel(page: PageSetupData): string {
  const preset = PAPER_SIZES.find((p) => p.id === page.paper)
  if (preset) return `${preset.name} · ${preset.label}`
  return `${mm(page.width)} × ${mm(page.height)} mm`
}

/** mpt to whole millimetres, for people. */
export const mm = (mpt: number): number => Math.round((mpt * 25.4) / 72000)

/** The setup on another preset paper (`custom` keeps the current size). */
export function withPaper(page: PageSetupData, id: string): PageSetupData {
  const preset = PAPER_SIZES.find((p) => p.id === id)
  return preset ? { ...page, paper: preset.id, width: preset.width, height: preset.height } : { ...page, paper: 'custom' }
}

/** The setup on a custom paper of `width` × `height` millimetres (either order; short side first in the result). */
export function withCustomSize(page: PageSetupData, width: number, height: number): PageSetupData {
  const [a, b] = [umToMpt(Math.round(width * 1000)), umToMpt(Math.round(height * 1000))]
  return { ...page, paper: 'custom', width: Math.min(a, b), height: Math.max(a, b) }
}

/** The margin preset the setup uses, or `null` when its four margins are not one of them. */
export function marginPreset(page: PageSetupData): string | null {
  const [t, r, b, l] = page.margins
  return MARGINS.find((m) => [t, r, b, l].every((v) => v === m.mpt))?.id ?? null
}

/** A one-line description for the status line: "3 pages · A4 portrait". */
export function describe(page: PageSetupData, pages: number): string {
  const preset = PAPER_SIZES.find((p) => p.id === page.paper)
  return `${pages} ${pages === 1 ? 'page' : 'pages'} · ${preset?.name ?? `${mm(page.width)} × ${mm(page.height)} mm`} ${page.orientation}`
}
