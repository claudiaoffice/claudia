import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    globalSetup: ['tests/setup.ts'],
    testTimeout: 30_000,
    coverage: { include: ['src/**'], reporter: ['text-summary'] },
  },
})
