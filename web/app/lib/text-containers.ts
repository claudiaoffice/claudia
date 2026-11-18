// Where a container hangs in the text, on the screen (D560, D1023): at the character it is anchored to, moved by the
// offset the model keeps (`dx`, `dy`), floating over the words without pushing any aside (D179). That is the rule the
// printed page follows (`layoutText`, D907), so what is seen here is what is printed, up to the small differences
// between the browser's lines and the layout engine's. Pure arithmetic over rectangles, so it can be tested.

export interface Box {
  left: number
  top: number
  width: number
  height: number
}

/** A point on the screen: the top-left corner of the anchor character. */
export interface Spot {
  left: number
  top: number
}

/** How far an object is moved off its anchor, as the model keeps it. */
export interface Away {
  dx?: number
  dy?: number
}

/**
 * The box of an object `w` by `h` anchored at `spot` and moved by `away`, in the coordinates of the layer `layer` is
 * the box of. It is kept inside the text `column` across (the page's margins in print), the left edge winning when the
 * object is wider than the column, and never put above the layer's top.
 */
export function floatBox(layer: Box, spot: Spot, away: Away, w: number, h: number, column?: Box): Box {
  let left = spot.left + (away.dx ?? 0)
  if (column) left = Math.max(column.left, Math.min(left, column.left + column.width - w))
  return { left: left - layer.left, top: Math.max(0, spot.top + (away.dy ?? 0) - layer.top), width: w, height: h }
}

/** The text column of a box whose words are inset by `left` and `right` (its padding): where an object may hang. */
export function columnOf(box: Box, left: number, right: number): Box {
  return { left: box.left + left, top: box.top, width: Math.max(0, box.width - left - right), height: box.height }
}

/**
 * Whether a press at `target` should let go of the selected object: any press that is not on an object (or on its
 * grip, which is inside it). Takes anything with a `closest`, so that it can be tested without a DOM.
 */
export function letsGoOfObject(target: { closest?: (selector: string) => unknown } | null): boolean {
  return !target?.closest?.('[data-object]')
}

/** The paragraph to hang from after a step with the arrow keys: the next or the previous, staying at the ends. */
export function neighbour(blocks: readonly string[], current: string, step: 1 | -1): string {
  const at = blocks.indexOf(current)
  if (at < 0) return current
  return blocks[Math.min(blocks.length - 1, Math.max(0, at + step))]!
}
