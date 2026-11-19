// The object clipboard, the same in all three apps (D1229): Cut and Copy of a selected picture, and Paste of it. A
// picture is the only kind that has one (the menus workbook: "Cut / Copy: images only").
//
// What is held is a copy of the picture and how it was shown (its bytes, its description and its size); a paste puts it
// where the app puts any new picture (a cell, a place in the text, the slide) as an object of its own, through the app's
// own `add_image`, so that it is one step in the history and the server checks it like any import.
//
// The system clipboard is told too: it gets the picture's description as text, which is what another program makes of
// it. That text is also how a paste knows the held picture is still the thing that was copied last: if the system
// clipboard holds something else by then (text copied elsewhere), the paste is a text paste. Nothing here reads the
// page's selection; the apps say what is selected.
import { onBeforeUnmount, onMounted, shallowRef } from 'vue'
import type { ImageAsset, PictureImport } from './images'
import type { ObjectBody } from './objects'
import { translate as t } from './i18n'

/** A picture as it was when it was cut or copied. */
export interface ClippedPicture {
  /** The picture's file, base64, as `add_image` takes it. */
  data: string
  description: string
  decorative: boolean
  sourceName: string
  /** The size the object had, in its app's units; the paste keeps it where the app can. */
  w: number
  h: number
  /** The text the system clipboard was given with it. */
  marker: string
}

/** What a picture's object and asset make of a clip; `null` for any object that is not a picture, or one whose asset has
 * not arrived. */
export function clipOf(body: ObjectBody, asset: ImageAsset | undefined): ClippedPicture | null {
  if (body.kind !== 'image' || !asset) return null
  const description = body.description || body.imported?.alt || ''
  return {
    data: asset.data,
    description,
    decorative: body.decorative,
    sourceName: body.imported?.source_name ?? '',
    w: body.w,
    h: body.h,
    marker: description || t('Picture'),
  }
}

/** The import a paste hands to the app's `add_image` (never from a file, so there is no path). */
export function pictureOf(clip: ClippedPicture): PictureImport {
  return { data: clip.data, alt: clip.decorative ? '' : clip.description, sourceName: clip.sourceName, sourcePath: null, decorative: clip.decorative }
}

const held = shallowRef<ClippedPicture | null>(null)

/** The picture held, if the system clipboard still holds what it was given with it (`text`: what the clipboard says). */
export function heldFor(text: string | null | undefined): ClippedPicture | null {
  return held.value && text === held.value.marker ? held.value : null
}
export const hold = (clip: ClippedPicture) => void (held.value = clip)
export const drop = () => void (held.value = null)
/** Whether a picture is held at all (a menu may offer Paste). */
export const holding = () => held.value !== null

/** What an app says to the clipboard: the one picture selected, how it is put somewhere new, and how it is taken away. */
export interface ClipboardHost {
  selected(): { id: string; body: ObjectBody; asset: ImageAsset | undefined } | null
  readonly(): boolean
  remove(id: string): Promise<unknown>
  /** Put the picture where the app puts a new one; it is selected there. */
  add(clip: ClippedPicture): Promise<unknown>
}

/** Whether the person has text selected, in a field or on the page: then Cut and Copy are about that text. */
export function textIsSelected(doc: Document = document): boolean {
  const active = doc.activeElement as (HTMLInputElement | HTMLTextAreaElement) | null
  if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA') && active.selectionStart !== active.selectionEnd) return true
  const selection = doc.getSelection?.()
  return !!selection && !selection.isCollapsed
}

/** Cut, Copy and Paste of the selected picture, as plain functions (the menus call them; `useObjectClipboard` hands the
 * keys to them). */
export function objectClipboard(host: ClipboardHost) {
  const chosenPicture = () => {
    const chosen = host.selected()
    const clip = chosen && clipOf(chosen.body, chosen.asset)
    return chosen && clip ? { id: chosen.id, clip } : null
  }
  async function toSystem(clip: ClippedPicture) {
    try {
      await navigator.clipboard.writeText(clip.marker)
    } catch {
      /* no permission or no secure context: the held picture is still pasted by the keys of this window */
    }
  }

  /** Copy the selected picture; `false` if none is selected. */
  function copy(): boolean {
    const chosen = chosenPicture()
    if (!chosen) return false
    hold(chosen.clip)
    void toSystem(chosen.clip)
    return true
  }
  /** Cut it: copy, then take it away (one step in the history). */
  async function cut(): Promise<boolean> {
    const chosen = chosenPicture()
    if (!chosen || host.readonly() || !copy()) return false
    await host.remove(chosen.id)
    return true
  }
  /** Paste the held picture if it is still what was copied last (`text`: what the system clipboard says, or read now). */
  async function paste(text?: string): Promise<boolean> {
    if (host.readonly()) return false
    let said = text
    if (said === undefined) {
      try {
        said = await navigator.clipboard.readText()
      } catch {
        said = held.value?.marker // no permission to read: this window's own last copy stands
      }
    }
    const clip = heldFor(said)
    if (!clip) return false
    await host.add(clip)
    return true
  }

  /** The browser's own copy or cut event (Ctrl+C, Ctrl+X): a picture selected and no text selected is this clipboard's. */
  function onCopyEvent(event: ClipboardEvent, cutting: boolean, textSelected: boolean) {
    const chosen = chosenPicture()
    if (!chosen || textSelected) return drop() // text was copied: the picture is no longer what was copied last
    event.preventDefault()
    event.stopPropagation()
    hold(chosen.clip)
    event.clipboardData?.setData('text/plain', chosen.clip.marker)
    if (cutting && !host.readonly()) void host.remove(chosen.id)
  }
  /** The browser's own paste event: the held picture if the clipboard still says it, else the text paste goes on. */
  function onPasteEvent(event: ClipboardEvent) {
    const clip = heldFor(event.clipboardData?.getData('text/plain'))
    if (!clip || host.readonly()) return
    event.preventDefault()
    event.stopPropagation() // the text paste of the page must not run as well
    void host.add(clip)
  }
  return { copy, cut, paste, onCopyEvent, onPasteEvent }
}

/** The same for a window: the three browser events are listened to while the component is mounted. */
export function useObjectClipboard(host: ClipboardHost) {
  const clipboard = objectClipboard(host)
  const copying = (event: Event) => clipboard.onCopyEvent(event as ClipboardEvent, false, textIsSelected())
  const cutting = (event: Event) => clipboard.onCopyEvent(event as ClipboardEvent, true, textIsSelected())
  const pasting = (event: Event) => clipboard.onPasteEvent(event as ClipboardEvent)
  onMounted(() => {
    // in the capture phase, so that the page's own copy and paste do not take the event first
    document.addEventListener('copy', copying, true)
    document.addEventListener('cut', cutting, true)
    document.addEventListener('paste', pasting, true)
  })
  onBeforeUnmount(() => {
    document.removeEventListener('copy', copying, true)
    document.removeEventListener('cut', cutting, true)
    document.removeEventListener('paste', pasting, true)
  })
  return clipboard
}
