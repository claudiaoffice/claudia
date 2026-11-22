// The one Name & describe… dialog (D1317), the same in all three apps: what the server says about a thing
// (`thing_details`), what the dialog checks before it sends, and what it sends (`name_and_describe`). Pure, so every
// rule has a test (`tests/name-and-describe.test.ts`); the server checks again and has the last word.

import { MAX_DESCRIPTION, descriptionProblem } from './descriptions'
import { translate as t } from './i18n'
import { nameProblem as rangeNameProblem } from './names'

/** `claudia_core.MAX_THING_NAME`. */
export const MAX_THING_NAME = 60

/** What `thing_details` sends. `name_fixed`: the name is worked out (a heading is called by its words) and is shown
 * locked; `drawn`: it can be marked decorative (a picture, a chart, a shape, a container, a text box). */
export interface ThingDetails {
  id: string
  kind: string
  name: string
  name_fixed: boolean
  description: string
  drawn: boolean
  decorative: boolean
}

/** What the dialog starts from for cells that have no name: a range is not a thing until it has one, so there is no id
 * yet, and the name is required (`name_and_describe_range`). */
export function unnamedRangeDetails(): ThingDetails {
  return { id: '', kind: 'range', name: '', name_fixed: false, description: '', drawn: false, decorative: false }
}

export interface NameAndDescribeForm {
  name: string
  description: string
  decorative: boolean
}

/** What is wrong with each field, as a sentence for the dialog (`null`: nothing). */
export interface NameAndDescribeProblems {
  name: string | null
  description: string | null
}

/** The rule for the name of a thing (`claudia_core.name_problem`): spaces, umlauts and `#` are all fine. */
function thingNameProblem(text: string): string | null {
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f-\u009f]/.test(text)) return t('a name has no control characters')
  const cleaned = text.trim().replace(/\s+/g, ' ')
  if (!cleaned) return t('a name needs some text')
  if (cleaned.length > MAX_THING_NAME) return t('a name has at most {max} characters', { max: MAX_THING_NAME })
  return null
}

export function checkNameAndDescribe(details: ThingDetails, form: NameAndDescribeForm): NameAndDescribeProblems {
  let name: string | null = null
  if (!details.name_fixed) {
    if (details.id === '') name = rangeNameProblem(form.name.trim())
    else if (form.name.trim() !== details.name) name = thingNameProblem(form.name) // unchanged (also: still none) is fine
  }
  let description: string | null = null
  const problem = descriptionProblem(details.kind === 'image' ? 'image' : 'shape', form.description, form.decorative)
  if (problem === 'empty') description = t('Describe the picture, or tick "Decorative" if it adds nothing a reader would miss.')
  else if (problem === 'too-long') description = t('At most {max} characters.', { max: MAX_DESCRIPTION })
  else if (problem === 'decorative-with-words') description = t('A decoration has no description.')
  return { name, description }
}

/** The parameters of `name_and_describe`: trimmed, and a decoration is sent with no words. */
export function nameAndDescribeParams(id: string, form: NameAndDescribeForm): { id: string; name: string; description: string; decorative: boolean } {
  return { id, name: form.name.trim(), description: form.decorative ? '' : form.description.trim(), decorative: form.decorative }
}
