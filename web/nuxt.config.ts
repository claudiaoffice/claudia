// A single-page app: it only talks to a claudia server over a WebSocket, so there is nothing to render on a server.
// Fonts come from npm packages and are bundled into the build: the page makes no request to any other site.
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  ssr: false,
  devtools: { enabled: false },
  telemetry: false,
  css: [
    '@fontsource/inter/latin-400.css',
    '@fontsource/inter/latin-500.css',
    '@fontsource/fraunces/latin-400.css',
    '@fontsource/fraunces/latin-500.css',
    '@fontsource/jetbrains-mono/latin-400.css',
    '@fontsource/sacramento/latin-400.css',
    '~/assets/tokens.css',
    '~/assets/app.css',
  ],
  app: {
    head: {
      title: 'claudia computes',
      meta: [{ name: 'viewport', content: 'width=device-width, initial-scale=1' }],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    },
  },
  typescript: { strict: true },
})
