// What a tag took the view to (E5.20, D551): the thing is brought into the middle and marked for a moment. The mark is
// an outline, not only a colour (BITV), and it needs no motion: with reduced motion the view jumps instead of gliding.
import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'
import { POINT_MS, type BaseState } from './base-session'

export const POINTED_CLASS = 'pointed'

/** Whether the person asked their system for less motion. */
export function reducedMotion(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** Mark the element `selector(id)` finds inside `root` whenever a tag points at a thing, and bring it into view. */
export function usePointed(state: Pick<BaseState, 'pointed'>, root: Ref<HTMLElement | null>, selector: (id: string) => string): void {
  let marked: HTMLElement | null = null
  let timer: ReturnType<typeof setTimeout> | undefined
  const clear = () => {
    marked?.classList.remove(POINTED_CLASS)
    marked = null
    clearTimeout(timer)
  }
  watch(
    () => state.pointed,
    async (pointed) => {
      clear()
      if (!pointed) return
      await nextTick() // the view may have just switched to the slide or sheet the thing is on
      const el = root.value?.querySelector<HTMLElement>(selector(pointed.id))
      if (!el) return
      marked = el
      el.classList.add(POINTED_CLASS)
      el.scrollIntoView({ block: 'center', inline: 'center', behavior: reducedMotion() ? 'auto' : 'smooth' })
      timer = setTimeout(clear, POINT_MS)
    },
  )
  onBeforeUnmount(clear)
}
