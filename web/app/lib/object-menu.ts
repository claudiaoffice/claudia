// Right-click on a slide object (bug report, 2026-11-07): "Edit text" and "Delete" already exist on the Edit menu
// and on the keyboard (Enter/F2, Del) — what was missing was a *context* menu offering the same two actions where
// the person actually clicked, so the browser's own menu (Back, Inspect, …) stops showing up over an object instead.
// Pure here on purpose: SlideCanvas.vue supplies the live `edit`/`remove` callbacks (already wired to `beginEdit`/
// `session.remove`, never duplicated) and renders the result with the generic `ContextMenu.vue`, which composes and
// computes can reuse for their own objects the same way, by handing it their own `MenuItem[]`.
import type { MenuItem } from '../components/MenuBar.vue'
import type { SlideObject } from './slide-session'

export function contextMenuItems(o: SlideObject, readonly: boolean, actions: { edit: () => void; remove: () => void }): MenuItem[] {
  const items: MenuItem[] = []
  if (o.kind !== 'image') {
    // A picture has no text to write — `SlideCanvas.vue`'s own `beginEdit` already refuses it for the same reason
    // (Enter/F2 does nothing on an image either), so the item is left off entirely rather than shown disabled.
    items.push({ label: 'Edit text', hint: 'Enter', action: actions.edit, disabled: readonly })
    items.push({ label: '', separator: true })
  }
  items.push({ label: 'Delete', hint: 'Del', action: actions.remove, disabled: readonly })
  return items
}
