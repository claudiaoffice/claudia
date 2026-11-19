// The state behind the Name & describe… dialog (D1317), one for the three apps: what the server says about the thing
// when the dialog opens, and the one request that saves name and description together. The dialog itself is
// `NameAndDescribeDialog.vue`; `done` is where the caller puts the focus back.

import { ref } from 'vue'
import { nameAndDescribeParams, unnamedRangeDetails, type NameAndDescribeForm, type ThingDetails } from './name-and-describe'
import type { NameRegion } from './names'

/** What the dialog needs of a session; computes adds the request for cells that have no name yet. */
export interface NameAndDescribeHost {
  thingDetails(id: string): Promise<ThingDetails | false>
  nameAndDescribe(params: { id: string; name: string; description: string; decorative: boolean }): Promise<boolean>
  nameAndDescribeRange?(range: NameRegion, name: string, description: string): Promise<string | false>
}

export function useNameAndDescribe(session: NameAndDescribeHost, done: () => void = () => undefined) {
  const details = ref<ThingDetails | null>(null)
  let region: NameRegion | null = null

  /** Open for a thing that has an id; stays shut (the reason has been shown) when the server does not know it. */
  async function open(id: string): Promise<void> {
    region = null
    const found = await session.thingDetails(id)
    if (found) details.value = found
  }
  /** Open for cells that have no name: the name is required, and they become a thing when it is saved. */
  function openRange(range: NameRegion): void {
    region = range
    details.value = unnamedRangeDetails()
  }
  async function save(form: NameAndDescribeForm): Promise<void> {
    const current = details.value
    details.value = null
    if (current) {
      if (region && session.nameAndDescribeRange) await session.nameAndDescribeRange(region, form.name.trim(), form.decorative ? '' : form.description.trim())
      else await session.nameAndDescribe(nameAndDescribeParams(current.id, form))
    }
    region = null
    done()
  }
  function close(): void {
    details.value = null
    region = null
    done()
  }
  return { details, open, openRange, save, close }
}
