// The trial (D1606): whether what does not fit is hidden or greyed, one setting per reason, every reason at hide to
// begin with, and an entry's own setting that beats its reason's. It travels in the page's address (D1647):
// `?fits=role:grey,document:grey&fits-entry=edit.undo:show`; the desktop apps add it from their settings file.
import { REASONS, type Reason } from './facts'

export type Display = 'hide' | 'grey'
/** "show" keeps an entry in its menu, greyed while it does not fit; "grey" does the same, "hide" takes it out. */
export type EntryDisplay = 'show' | Display

export interface FitPolicy {
  byReason: Readonly<Record<Reason, Display>>
  byEntry: Readonly<Record<string, EntryDisplay>>
}

export const DEFAULT_POLICY: FitPolicy = {
  byReason: Object.fromEntries(REASONS.map((reason) => [reason, 'hide'])) as Record<Reason, Display>,
  byEntry: {},
}

function pairs(value: string | null): [string, string][] {
  return (value ?? '')
    .split(',')
    .map((pair) => pair.split(':') as [string, string])
    .filter((pair) => pair.length === 2)
}

/** The policy an address asks for; a reason, an entry setting or a value it does not know is left out. */
export function policyFromAddress(search: string): FitPolicy {
  const query = new URLSearchParams(search)
  const byReason = { ...DEFAULT_POLICY.byReason }
  for (const [reason, display] of pairs(query.get('fits'))) {
    if ((REASONS as readonly string[]).includes(reason) && (display === 'hide' || display === 'grey')) byReason[reason as Reason] = display
  }
  const byEntry: Record<string, EntryDisplay> = {}
  for (const [id, display] of pairs(query.get('fits-entry'))) {
    if (display === 'show' || display === 'grey' || display === 'hide') byEntry[id] = display
  }
  return { byReason, byEntry }
}
