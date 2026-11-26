// Runs around every web test (`vitest.config.ts`, `setupFiles`): a fake server that was asked for something the real
// one would refuse fails the test, even where the session told the person "something went wrong" and carried on.
import { afterEach } from 'vitest'
import { made } from './fake-server'

afterEach(() => {
  const refused = made.flatMap((server) => server.violations)
  made.length = 0
  if (refused.length) throw new Error(`the fake server was asked for what the real one would refuse:\n  ${[...new Set(refused)].join('\n  ')}`)
})
