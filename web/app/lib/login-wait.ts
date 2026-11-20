// What a person is told when failed logins make her wait (D1266, E2.7), for the document's login and the
// administrator's sign-in alike. The server refuses a login inside a wait before it hashes anything and says how many
// seconds are left; this counts them down so that the person can see when to try again.
//
// BITV: the spoken text (`said`, for a polite live region) changes twice only, when the wait begins and when it is
// over; the seconds that run down are for the eyes (`left`, which belongs in an `aria-hidden` element), so a screen
// reader is not interrupted every second.

import { computed, ref } from 'vue'
import { translate as t } from './i18n'

/** "Too many tries. Try again in N seconds." */
export function tooManyTries(seconds: number): string {
  return seconds === 1 ? t('Too many tries. Try again in 1 second.') : t('Too many tries. Try again in {seconds} seconds.', { seconds })
}

export function useLoginWait() {
  const left = ref(0)
  const said = ref('')
  let timer: ReturnType<typeof setInterval> | null = null

  function stop() {
    if (timer !== null) clearInterval(timer)
    timer = null
  }

  function clear() {
    stop()
    left.value = 0
    said.value = ''
  }

  function begin(seconds: number) {
    stop()
    if (!(seconds > 0)) return
    left.value = Math.ceil(seconds)
    said.value = tooManyTries(left.value)
    timer = setInterval(() => {
      left.value -= 1
      if (left.value <= 0) {
        stop()
        left.value = 0
        said.value = t('You can try again now.')
      }
    }, 1000)
  }

  return { left, said, waiting: computed(() => left.value > 0), begin, clear }
}
