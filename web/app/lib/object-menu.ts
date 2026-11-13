// Right-click on a slide object (bug report, 2026-11-07): "Edit text" and "Delete" already exist on the Edit menu
// and on the keyboard (Enter/F2, Del) — what was missing was a *context* menu offering the same actions where the
// person actually clicked, so the browser's own menu (Back, Inspect, …) stops showing up over an object instead.
// An image's menu was later asked to add Cut, Copy and Properties too (2026-11-07 follow-up) — Cut/Copy exactly as
// the Edit menu's own `cutSelection`/`copySelection` already behave, Properties opening `ImagePropertiesDialog.vue`.
// Left for a shape/text object, and left off an image, for now: anything beyond this exact set is undecided.
// Pure here on purpose: SlideCanvas.vue supplies the live callbacks (never duplicated logic) and renders the result
// with the generic `ContextMenu.vue`, which composes and computes can reuse for their own objects the same way.
import type { MenuItem } from '../components/MenuBar.vue'
import type { SlideObject } from './slide-session'

export interface ObjectMenuActions {
  edit: () => void
  /** Open the style menu on this object: its fill, its border, and the style its words follow (E9.7, D203). */
  style: () => void
  remove: () => void
  cut: () => void
  copy: () => void
  properties: () => void
  setSnap: (snap: boolean) => void
}

export function contextMenuItems(o: SlideObject, readonly: boolean, actions: ObjectMenuActions): MenuItem[] {
  const items: MenuItem[] = []
  // "Style…" first and for every kind: a picture has no fill and no words, but it does have a border and a place
  // in the stacking order, so the menu has something to offer for all four kinds (D178, D181).
  items.push({ label: 'Style…', action: actions.style, disabled: readonly })
  items.push({ label: '', separator: true })
  if (o.kind === 'image') {
    // Cut/Copy: the very same `cutSelection`/`copySelection` the Edit menu's own items call — not a second,
    // image-specific clipboard. Copy never needs write access, same as `edit.copy` is never disabled either.
    items.push({ label: 'Cut', hint: 'Ctrl+X', action: actions.cut, disabled: readonly })
    items.push({ label: 'Copy', hint: 'Ctrl+C', action: actions.copy })
    items.push({ label: '', separator: true })
    items.push({ label: 'Properties', action: actions.properties })
    items.push({ label: '', separator: true })
  } else {
    // A picture has no text to write — `SlideCanvas.vue`'s own `beginEdit` already refuses it for the same reason
    // (Enter/F2 does nothing on an image either), so the item is left off entirely rather than shown disabled.
    items.push({ label: 'Edit text', hint: 'Enter', action: actions.edit, disabled: readonly })
    items.push({ label: '', separator: true })
  }
  // The grid is only a helper the view draws; whether this object follows it is real document state (E10.15).
  // One item whose label swaps, like "Undo <label>" does, rather than a checkbox: ContextMenu.vue renders a
  // label and a hint only, and a swapping label needs no change there.
  items.push({ label: o.snap ? 'Release from grid' : 'Snap to grid', action: () => actions.setSnap(!o.snap), disabled: readonly })
  items.push({ label: '', separator: true })
  items.push({ label: 'Delete', hint: 'Del', action: actions.remove, disabled: readonly })
  return items
}
