import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  resolve: { alias: { '~': fileURLToPath(new URL('./app', import.meta.url)) } },
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    // CODE-01: `npm run coverage`. Only `app/lib` is measured: the tests run in Node without a DOM and test the
    // logic the components call, never a mounted component (the e2e scripts see those). The thresholds are what the
    // tests reached when they were set, rounded down; raise them by hand when a change lifts them, never lower them
    // without saying why in the commit.
    //
    // 2026-11-11 (vitest 3 -> 5): the thresholds were re-based, not lowered for lack of tests. The same 545 tests that
    // reached 88 / 91 / 81 / 88 (statements, branches, functions, lines) under vitest 3 measure 85.3 / 82.4 / 78.3 /
    // 86.9 under vitest 5, which also counts fewer statements (2369 instead of 3506): the two versions measure
    // differently, so the figures are not comparable. These are the new ones, rounded down.
    coverage: {
      provider: 'v8',
      include: ['app/lib/**'],
      reporter: ['text-summary'],
      thresholds: { statements: 85, branches: 82, functions: 78, lines: 86 },
    },
  },
})
