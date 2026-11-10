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
    coverage: {
      provider: 'v8',
      include: ['app/lib/**'],
      reporter: ['text-summary'],
      thresholds: { statements: 88, branches: 90, functions: 80, lines: 88 },
    },
  },
})
