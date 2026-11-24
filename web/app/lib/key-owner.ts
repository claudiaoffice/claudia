import { takesTyping } from './dragging'

/** Whose a key press is. The slide and the grid take Delete, Backspace and the arrows for the object that is selected,
 * but a dialog or a popover is drawn inside them, so every key typed there bubbles up to them as well. A key typed into
 * a field, or anywhere in a dialog, is for that and not for the object behind it (UX-76). A native `<dialog>` has no
 * `role` attribute, so it has to be asked for by its element name. */
export function keysAreTheirs(target: { closest?: (selector: string) => unknown; isContentEditable?: boolean } | null): boolean {
  return takesTyping(target) || !!target?.closest?.('dialog, [role=dialog]')
}
