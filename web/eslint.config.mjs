// CODE-01: the web app's linter. `@nuxt/eslint-config` is Nuxt's own recommended set (JavaScript, TypeScript and Vue),
// without its stylistic rules: the code's look is consistent already, and a formatter would be a decision of its own.
// Every rule switched off or narrowed below says why.
import { createConfigForNuxt } from '@nuxt/eslint-config/flat'

export default createConfigForNuxt({ features: { stylistic: false } })
  .append({
    ignores: ['.nuxt/', '.output/', 'dist/', 'node_modules/', 'coverage/'],
  })
  .append({
    rules: {
      // The sessions keep their state in plain reactive records keyed by id, and Vue tracks `delete` on those; a Map
      // instead (what this rule wants) would change every component that reads them.
      '@typescript-eslint/no-dynamic-delete': 'off',
      // These four single words were the components' names long before the linter. None of them is, or is likely
      // to become, an HTML element's name, which is what the rule protects against.
      'vue/multi-word-component-names': ['error', { ignores: ['Modal', 'Popover', 'Wordmark', 'Workspace'] }],
    },
  })
  .append({
    // A test's fakes stand in for a WebSocket, a shell or a server frame, and only need the parts a test touches.
    files: ['tests/**'],
    rules: { '@typescript-eslint/no-explicit-any': 'off' },
  })
