// File ▸ Open… inside a document (sheet 10, B1): the dialog opens another document, and this window then shows it in
// place of the one before. The dialog lives deep inside a workspace; the window's session lives in `app.vue`. This
// one reference is how the first hands the new session to the second, without every workspace passing an event on.
import { shallowRef } from 'vue'
import type { AnySession } from './open'

/** A session opened from inside a document, waiting for the window to show it. */
export const openedFromDocument = shallowRef<AnySession | null>(null)
