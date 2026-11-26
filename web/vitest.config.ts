import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  resolve: { alias: { '~': fileURLToPath(new URL('./app', import.meta.url)) } },
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    // E11.7: the fake server every session test talks to is held to the server's own description of its protocol;
    // this makes a test fail afterwards if it was asked for what the real server would refuse.
    setupFiles: ['tests/support/setup.ts'],
    // CODE-01: `npm run coverage`. Only `app/lib` is measured: the tests run in Node without a DOM and test the
    // logic the components call, never a mounted component (the e2e scripts see those). The thresholds are what the
    // tests reached when they were set, rounded down; raise them by hand when a change lifts them, never lower them
    // without saying why in the commit.
    //
    // 2026-11-11 (vitest 3 -> 5): the thresholds were re-based, not lowered for lack of tests. The same 545 tests that
    // reached 88 / 91 / 81 / 88 (statements, branches, functions, lines) under vitest 3 measure 85.3 / 82.4 / 78.3 /
    // 86.9 under vitest 5, which also counts fewer statements (2369 instead of 3506): the two versions measure
    // differently, so the figures are not comparable. These are the new ones, rounded down.
    //
    // 2026-11-24 (CODE-36): raised to what the tests reach now, rounded down (90.2 / 87.1 / 86.2 / 91.5).
    coverage: {
      provider: 'v8',
      include: ['app/lib/**'],
      reporter: ['text-summary'],
      thresholds: { statements: 90, branches: 87, functions: 86, lines: 91 },
    },
  },
})
