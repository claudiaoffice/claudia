// Where a container hangs in the text, on the screen (D560): at the top of its paragraph, against the right edge of the
// text, floating over it without pushing any word aside (D179). Pure arithmetic over rectangles, so it can be tested.

export interface Box {
  left: number
  top: number
  width: number
  height: number
}

export const MIN_SIDE = 60

/** The box of an object `w` by `h` that hangs from a paragraph whose box is `para`, in the layer `layer` is the box of. */
export function floatBox(layer: Box, para: Box, w: number, h: number): Box {
  const left = Math.max(para.left - layer.left, para.left - layer.left + para.width - w)
  return { left, top: para.top - layer.top, width: w, height: h }
}

/** A size after the corner was dragged by (dx, dy), never smaller than the least that can be seen and grabbed. */
export function resizedBy(w: number, h: number, dx: number, dy: number): { w: number; h: number } {
  return { w: Math.max(MIN_SIDE, Math.round(w + dx)), h: Math.max(MIN_SIDE, Math.round(h + dy)) }
}

/** The paragraph to hang from after a step with the arrow keys: the next or the previous, staying at the ends. */
export function neighbour(blocks: readonly string[], current: string, step: 1 | -1): string {
  const at = blocks.indexOf(current)
  if (at < 0) return current
  return blocks[Math.min(blocks.length - 1, Math.max(0, at + step))]!
}
