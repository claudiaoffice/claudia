import type { Region } from './protocol'

/** How a place is marked while the history is replayed (D553): `now` is what the step on show changed, `since` what a
 * later step changed ("Show differences from now"). Never by colour alone: the views draw the two differently. */
export type Tint = 'now' | 'since'

export interface CellTint {
  r0: number
  c0: number
  r1: number
  c1: number
  tint: Tint
}

/** The places to mark, asked by each view for what it draws. */
export interface Tints {
  /** The cell ranges of one sheet, corners put the right way round. */
  cells(sheet: string): CellTint[]
  /** How a floating object (on a slide or a sheet) is marked, by id; what the step did wins over what came later. */
  object(id: string): Tint | null
  /** How a paragraph is marked, by paragraph id: the whole paragraph, whichever stretch of it changed. */
  paragraph(id: string): Tint | null
  /** How many places differ from now (the `since` ones), for a person who does not see the tint. */
  count: number
}

/** Sort the regions of a replay (the step's own, and the ones changed since) into what each view asks for. */
export function tintsOf(focus: Region[], changed: Region[]): Tints {
  const all: [Region, Tint][] = [...focus.map((r): [Region, Tint] => [r, 'now']), ...changed.map((r): [Region, Tint] => [r, 'since'])]
  const objects = new Map<string, Tint>()
  const paragraphs = new Map<string, Tint>()
  for (const [region, tint] of all) {
    if (region.kind === 'objects') for (const id of region.ids) if (!objects.has(id)) objects.set(id, tint)
    if (region.kind === 'text' && !paragraphs.has(region.paragraph)) paragraphs.set(region.paragraph, tint)
  }
  const count = changed.reduce((n, r) => n + (r.kind === 'objects' ? r.ids.length : 1), 0)
  return {
    cells(sheet) {
      const out: CellTint[] = []
      for (const [region, tint] of all) {
        if (region.kind !== 'cells' || region.range.first.sheet !== sheet) continue
        const { first, last } = region.range
        out.push({
          r0: Math.min(first.row, last.row),
          c0: Math.min(first.col, last.col),
          r1: Math.max(first.row, last.row),
          c1: Math.max(first.col, last.col),
          tint,
        })
      }
      return out
    },
    object: (id) => objects.get(id) ?? null,
    paragraph: (id) => paragraphs.get(id) ?? null,
    count,
  }
}

const NONE = tintsOf([], [])

/** The tints of the replay a session is in (what the step changed, and what changed after it if asked), or nothing in
 * the present. */
export function replayTints(replay: { focus: Region[]; differences: boolean; changed: Region[] } | null): Tints {
  return replay ? tintsOf(replay.focus, replay.differences ? replay.changed : []) : NONE
}

/** The tints of what the views show: a replay's, or the places a redaction would change while it is previewed (D721),
 * marked as what "this step" changed. */
export function viewTints(state: {
  replay: { focus: Region[]; differences: boolean; changed: Region[] } | null
  preview?: { regions: Region[] } | null
}): Tints {
  if (state.replay) return replayTints(state.replay)
  return state.preview ? tintsOf(state.preview.regions, []) : NONE
}
