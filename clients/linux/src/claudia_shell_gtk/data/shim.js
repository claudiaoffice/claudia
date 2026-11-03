// The page adapter of the Linux shell: it speaks the shell contract (clients/contract) on the page's side.
//
// It is a compatibility layer. The web app does not speak the contract itself (yet), so this script, which the shell
// injects into its own pages only, carries out the shell's `action` messages by using the web app's menus exactly as a
// person would, and reports which of them are enabled or ticked. When the web app implements the contract, this file
// goes away and nothing in the shell changes.
//
// It runs in a separate JavaScript world ("claudia-shell"): the page's scripts cannot see or change it, and it sees
// the same DOM. `install` is called by the shell with {app, origin, routes}: it does nothing on a page whose origin is
// not `origin`, and `routes` is data/webroutes.json.
(function install(config) {
  'use strict'
  const handler = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.claudia
  if (!handler || window.__claudiaShell || location.origin !== config.origin) return

  const CONTRACT = 1
  const POLL_MS = 750
  const routes = config.routes
  let ready = false
  let last = {}
  let queue = Promise.resolve()

  const post = (message) => handler.postMessage(JSON.stringify(message))
  const report = (code, message) => post({ type: 'error', code, message })
  const tick = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms))
  const serial = (work) => (queue = queue.then(work, work).catch((e) => report('internal', String((e && e.message) || e))))

  // The shell draws the menus, so the web menu bar is hidden. Its element stays (the page's layout has a row for it)
  // and its items stay clickable: they are how actions are carried out.
  const style = document.createElement('style')
  style.textContent =
    'nav.menus{visibility:hidden!important;height:0!important;min-height:0!important;padding:0!important;border:0!important;overflow:visible!important}'
  document.documentElement.appendChild(style)

  // ------------------------------------------------------------------------------------------- the web menus
  const menuRoot = () => document.querySelector('nav.menus')
  const titleOf = (name) =>
    [...document.querySelectorAll('nav.menus .menu > button.title')].find((b) => b.textContent.trim() === name)
  const openTitle = () => document.querySelector('nav.menus .menu > button.title.open')

  async function closeMenus() {
    const open = openTitle()
    if (open) {
      open.click()
      await tick()
    }
  }

  async function openMenu(name) {
    let title = titleOf(name)
    if (!title) return null
    if (!title.classList.contains('open')) {
      await closeMenus()
      title.click()
      await tick()
      title = titleOf(name) // the page may have drawn its menu again: look the title up anew
    }
    return title ? title.parentElement : null
  }

  const textOf = (button) => {
    const span = button.querySelector('span') || button
    const copy = span.cloneNode(true)
    copy.querySelectorAll('.tick').forEach((t) => t.remove())
    return copy.textContent.trim()
  }

  function findItem(menuElement, route) {
    const items = [...menuElement.querySelectorAll('ul.drop button[role=menuitem]')]
    return items.find((b) => (route.prefix ? textOf(b).startsWith(route.label) : textOf(b) === route.label)) || null
  }

  const isChecked = (item) => item.getAttribute('aria-checked') === 'true'

  // Reads the state of one route from an open menu.
  function stateOf(menuElement, route) {
    const item = findItem(menuElement, route)
    if (!item) return { enabled: false }
    const state = { enabled: !item.disabled }
    if (item.hasAttribute('aria-checked')) state.checked = isChecked(item)
    return state
  }

  // ------------------------------------------------------------------------------------------- shell -> page
  async function perform(id, target) {
    const route = routes[id]
    if (!route) return report('unknown_action', `no such action: ${id}`)
    // For a pair like Page/Flow the "off" side is the other item of the pair.
    const useOff = target === 'off' && route.off
    const chosen = useOff ? route.off : route
    const menuElement = await openMenu(chosen.menu)
    const item = menuElement && findItem(menuElement, chosen)
    if (!item) {
      await closeMenus()
      return report('internal', `the page has no menu item for ${id} right now`)
    }
    if (item.disabled) {
      await closeMenus()
      return
    }
    const checked = item.hasAttribute('aria-checked') ? isChecked(item) : null
    // An action with a target is idempotent: "on" when it is on already (or "off" when it is off) does nothing.
    const alreadyThere = (target === 'on' && checked === true) || (target === 'off' && !route.off && checked === false) ||
      (useOff && checked === true)
    if (alreadyThere) await closeMenus()
    else item.click()
    await tick(60)
    await closeMenus()
    await poll()
  }

  // ------------------------------------------------------------------------------------------- page -> shell
  async function poll() {
    if (!ready) return
    const states = {}
    const byMenu = {}
    for (const [id, route] of Object.entries(routes)) (byMenu[route.menu] = byMenu[route.menu] || []).push([id, route])
    const present = !!menuRoot()
    for (const [name, entries] of Object.entries(byMenu)) {
      const menuElement = present ? await openMenu(name) : null
      for (const [id, route] of entries) states[id] = menuElement ? stateOf(menuElement, route) : { enabled: false }
    }
    await closeMenus()
    const changed = {}
    for (const [id, state] of Object.entries(states)) {
      if (JSON.stringify(state) !== JSON.stringify(last[id])) changed[id] = state
    }
    if (Object.keys(changed).length) {
      last = { ...last, ...changed }
      post({ type: 'action_state', states: changed })
    }
  }

  function receive(raw) {
    let message
    try {
      message = JSON.parse(raw)
    } catch (e) {
      return report('bad_json', 'the shell sent text that is not JSON')
    }
    if (message.type === 'welcome') {
      ready = true
      last = {}
      serial(poll)
    } else if (message.type === 'action') {
      serial(() => perform(message.action, message.target))
    } else if (message.type === 'error') {
      console.warn('[claudia shell]', message.code, message.message)
    }
  }

  window.__claudiaShell = { receive, contract: CONTRACT }
  post({ type: 'hello', contract: CONTRACT, app: config.app })
  setInterval(() => {
    if (ready && !document.hidden) serial(poll)
  }, POLL_MS)
})
