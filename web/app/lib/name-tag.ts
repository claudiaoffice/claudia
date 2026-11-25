// Where a colleague's name tag goes on her outline in a sheet (UX-86). It sits above her box; above the first row shown
// that is under the column letters, which would hide her name, so there it goes inside the box's top edge.

/** The room a name tag needs above a box, in pixels: the taller of the cell outline's tag and the object's. */
export const NAME_TAG_HEIGHT = 20

/** Where the name tag goes on a box whose top is `top` pixels below the top of the sheet area (after scrolling):
 * `null` above the box, else this many pixels down inside it, so that a box scrolled partly out of the area still
 * shows the name at the area's top. */
export function nameTagInside(top: number): number | null {
  return top < NAME_TAG_HEIGHT ? Math.max(0, -top) : null
}
