// The trial (D1606): whether what does not fit is hidden or greyed, one setting per reason, every reason at hide to
// begin with, and an entry's own setting, grey or hide (D1653), that beats its reason's. It travels in the page's
// address (D1647): `?fits=role:grey,document:grey&fits-entry=edit.undo:grey`; the desktop apps add it from their
// settings file.
import { REASONS, type Reason } from './facts'

/** What becomes of an entry that does not fit: left out, or kept in its menu and greyed. */
export type Display = 'hide' | 'grey'

export interface FitPolicy {
  byReason: Readonly<Record<Reason, Display>>
  byEntry: Readonly<Record<string, Display>>
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
  const byEntry: Record<string, Display> = {}
  for (const [id, display] of pairs(query.get('fits-entry'))) {
    if (display === 'hide' || display === 'grey') byEntry[id] = display
  }
  return { byReason, byEntry }
}
