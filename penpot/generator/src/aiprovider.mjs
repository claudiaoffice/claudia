// The designs of E7.11 "Claude as an AI provider" as Penpot components and pages: the AI page of the server settings
// (and the states of it), the owners' consent in Preferences ▸ AI…, and the History & Chat panel with the badge that says
// who answers. They are the mocks agreed with the owner (claudiaoffice-log/notes/mockups/ai-provider-1 to 4), drawn
// with the tokens, text styles and components the file already has; nothing here adds a token or a text style.
//
// Built AFTER everything else: the ids of a file's shapes come from the order they are made in, and must not move.
import { board, circle, instance, pick, text, variantSet } from './model.mjs'
import { PANEL_TEXT, WHITE, hline, sidePanel, withNotes } from './workspace.mjs'
import { dialogShell } from './dialogs.mjs'

const RED = { raw: '#9A2F4A' }
const RED_WASH = { raw: '#9A2F4A', opacity: 0.09 }
const GREEN = { raw: '#13917F' }
const AMBER = { raw: '#F2A057' }
const AMBER_WASH = { raw: '#FDF3E6' }

// --- the library -----------------------------------------------------------------------------------------------

export function buildAiProviderLibrary() {
  const a = {}

  // AI provider / Provider badge: Where (who answers, and whether the content leaves the server)
  a.badge = variantSet(
    'Provider badge',
    'AI provider',
    { Where: ['remote', 'here', 'here on dark'] },
    ({ Where }) => {
      const remote = Where === 'remote'
      const dark = Where === 'here on dark'
      return board(
        'Provider badge',
        { layout: 'row', align: 'center', gap: 'space.6', pad: ['space.2', 'space.8'], radius: 'radius.pill', fill: remote ? 'color.iris' : undefined, stroke: remote ? undefined : dark ? { raw: '#E6E0F5', opacity: 0.5, width: 'border.1' } : { color: 'color.line-field', width: 'border.1' } },
        text('label', remote ? 'Claude · remote' : 'Qwen2.5-7B · this server', { style: 'badge', color: remote ? WHITE : dark ? PANEL_TEXT(0.9) : 'color.text' }),
      )
    },
    { w: 600 },
  )
  return a
}

// --- pieces ----------------------------------------------------------------------------------------------------

const hint = (t, o = {}) => text('hint', t, { style: 'hint', color: 'color.muted', w: 'fill', ...o })
const row = (name, kids, o = {}) => board(name, { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.8', ...o }, ...kids)
const col = (name, kids, o = {}) => board(name, { w: 'fill', h: 'auto', layout: 'column', gap: 'space.6', ...o }, ...kids)
const mono = (t, o = {}) => text('value', t, { style: 'mono-small', color: 'color.text', ...o })

const segmented = (options, chosen) =>
  board(
    'segmented',
    { w: 'auto', h: 'auto', layout: 'row', gap: 'space.2', pad: 'space.2', radius: 'radius.control', fill: 'color.mist' },
    ...options.map((o) => board(o, { layout: 'row', align: 'center', pad: ['space.6', 'space.14'], radius: 'radius.chip', fill: o === chosen ? 'color.surface' : undefined, shadow: o === chosen ? 'shadow.raised' : undefined }, text('label', o, { style: 'switch', color: o === chosen ? 'color.text' : 'color.muted' }))),
  )

const chip = (label, on) => board('model', { layout: 'row', pad: ['space.3', 'space.12'], radius: 'radius.pill', stroke: { color: on ? 'color.app' : 'color.line-field', width: on ? 'border.2' : 'border.1' } }, text('label', label, { style: 'chip', color: on ? 'color.text' : 'color.muted' }))

const button = (lib, Kind, label, State = 'default') => instance(pick(lib.button, { Kind, Size: 'regular', State }), { edit: { label: { content: label } } })
const smallButton = (lib, label) => instance(pick(lib.button, { Kind: 'default', Size: 'small', State: 'default' }), { edit: { label: { content: label } } })
const field = (lib, label, value, Value = 'filled', Trailing = 'none') => instance(pick(lib.field, { Value, Trailing }), { w: 'fill', edit: { label: { content: label }, value: { content: value } } })
const badge = (a, Where) => instance(pick(a.badge, { Where }), {})

const callout = (kind, title, ...lines) =>
  board(
    'callout',
    { w: 'fill', h: 'auto', layout: 'column', gap: 'space.4', pad: ['space.10', 'space.12'], radius: 'radius.field', fill: kind === 'amber' ? AMBER_WASH : kind === 'red' ? RED_WASH : 'color.mist', stroke: kind === 'amber' ? { raw: '#F2A057', width: 'border.1' } : kind === 'red' ? { raw: '#9A2F4A', width: 'border.1' } : undefined },
    text('title', title, { style: 'control-strong', color: kind === 'red' ? RED : 'color.text', w: 'fill' }),
    ...lines.map((l) => text('line', l, { style: 'hint', color: 'color.text', w: 'fill' })),
  )

const result = (ok, t, detail) =>
  row('result', [circle('dot', { w: 10, h: 10, fill: ok ? GREEN : RED }), board('said', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.2' }, text('text', t, { style: 'control-strong', color: ok ? 'color.text' : RED, w: 'fill' }), ...(detail ? [hint(detail)] : []))], { align: 'start' })

/** The server settings page's shell (AdminShell.vue): the server's name, the sections on the left, the section on the right. */
function shell(name, content) {
  const nav = (t, on) => board(t, { w: 'fill', h: 'auto', layout: 'row', pad: ['space.6', 'space.10'], radius: 'radius.row', fill: on ? 'color.mist' : undefined }, text('label', t, { style: on ? 'control-strong' : 'control', color: on ? 'color.text' : 'color.muted' }))
  return board(
    name,
    { w: 980, h: 'auto', layout: 'column', fill: 'color.page', stroke: { color: 'color.line', width: 'border.1' }, radius: 'radius.dialog', clip: true },
    row('head', [text('title', 'Server settings', { style: 'panel-title', color: 'color.text' }), text('server', 'Studio server', { style: 'hint', color: 'color.muted', w: 'fill' }), mono('claudia.example.org', { color: 'color.muted' }), hint('Signed in as anna', { w: 'auto' })], { pad: ['space.12', 'space.18'], gap: 'space.14', fill: 'color.surface' }),
    hline('line', 0),
    board('body', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.24', pad: ['space.18', 'space.18'], align: 'start' }, board('sections', { w: 170, h: 'auto', layout: 'column', gap: 'space.2' }, nav('AI', true), nav('Typesetting'), nav('Access & documents'), nav('Sign out')), content),
  )
}

const approval = (confirmed) =>
  callout(
    'amber',
    'Document content is sent to Anthropic when someone asks @ai.',
    'Documents are encrypted on this server; Claude reads what it is shown in plain text.',
    ...(confirmed
      ? ['Confirmed by anna, today 09:12', 'This is not enough on its own: the owners of each document must also allow Claude (Preferences ▸ AI…, off by default). Until they do, @ai in that document uses the local model or the stand-in, and says so.']
      : ['The owners of each document must also allow Claude there (Preferences ▸ AI…). Until they do, @ai in that document uses the local model or the stand-in.']),
  )

// --- 1. the AI page of the server settings -----------------------------------------------------------------------

function settingsPage(lib, a, w) {
  const now = row('answering', [text('label', 'Answering now:', { style: 'hint', color: 'color.muted' }), text('who', 'Claude · claude-sonnet-5-5', { style: 'control-strong', color: 'color.text' }), badge(a, 'remote'), hint('Last changed by anna, today 09:12', { w: 'fill' })], { pad: ['space.8', 'space.12'], radius: 'radius.field', fill: 'color.mist' })
  const keyRow = col('provider key', [
    text('label', 'Provider key', { style: 'hint', color: 'color.muted' }),
    row('key', [board('input', { w: 'fill', h: 'auto', layout: 'row', pad: ['space.9', 'space.11'], radius: 'radius.field', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }, mono('sk-ant-•••••••••••••••••••• a7Q2', { w: 'fill' })), smallButton(lib, 'Replace'), smallButton(lib, 'Remove')]),
    hint('Kept on this server only. It is never shown again, never sent to a client or into a document.'),
    hint('A key of your Anthropic account. Anthropic bills its use apart from any Claude subscription.'),
  ])
  const model = col('model', [text('label', 'Model', { style: 'hint', color: 'color.muted' }), row('chips', [chip('claude-sonnet-5-5', true), chip('sonnet-5-5'), chip('opus-5-5'), chip('haiku-5-5'), chip('fable-5-2')], { gap: 'space.6' }), hint('Type any model id: the list of models changes faster than this app does.')])
  const limits = row('limits', [field(lib, 'Longest answer (tokens)', '1024'), field(lib, 'Timeout (seconds)', '60')], { align: 'start', gap: 'space.14' })
  const test = result(true, 'Test answered in 1.4 s', 'Apply asks Claude one test question first.')
  const buttons = row('buttons', [board('space', { w: 'fill', h: 1 }), button(lib, 'default', 'Cancel'), button(lib, 'primary', 'Apply')], { gap: 'space.10' })
  const page = shell(
    'Server settings - AI',
    col('AI', [text('title', 'AI', { style: 'editor-title', color: 'color.text' }), hint('What answers @ai in every document on this server.'), now, col('provider', [text('label', 'AI provider', { style: 'hint', color: 'color.muted' }), segmented(['Scripted stand-in', 'Local model', 'Claude'], 'Claude')]), keyRow, model, limits, approval(true), test, buttons], { gap: 'space.14' }),
  )
  return withNotes(
    w,
    page,
    [
      'What is answering: always said in words, with the "remote" badge, so the page tells the truth about where content goes (D32). Under it, the last error and when it happened is the place an administrator looks first.',
      'One switch, three providers: stand-in, local model (today\'s folder, device, limits) and Claude. The local fields stay as they are, so an old settings file loads unchanged.',
      'The provider key is write-only: only its last four characters show afterwards. An operator can give it as ANTHROPIC_API_KEY or a key file, which wins over the saved one (D154).',
      'Two approvals, not one: the administrator confirms the sentence (recorded with who and when). It is not enough: the owners of each document allow Claude there. The administrator is not an owner and cannot open sealed documents.',
      'Test before apply: one question through the new provider. A refused key or an unreachable API is refused here with its reason, not found out by the first person who asks @ai.',
    ],
  )
}

// --- 2. what goes wrong, and where it is said --------------------------------------------------------------------

function settingsStates(lib, a) {
  const cut = (name, title, ...kids) => board(name, { w: 520, h: 'auto', layout: 'column', gap: 'space.12', pad: ['space.16', 'space.18'], radius: 'radius.dialog', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }, text('title', title, { style: 'control-strong', color: 'color.muted', w: 'fill' }), ...kids)
  const buttons = (apply = true) => row('buttons', [board('space', { w: 'fill', h: 1 }), button(lib, 'default', 'Cancel'), button(lib, 'primary', 'Apply', apply ? 'default' : 'disabled')], { gap: 'space.10' })
  const keyOnly = (value, Trailing = 'none') => field(lib, 'Provider key', value, value.startsWith('Paste') ? 'placeholder' : 'filled', Trailing)

  const A = cut('A - Claude chosen, nothing applied yet', 'A · Claude chosen, nothing applied yet', segmented(['Scripted stand-in', 'Local model', 'Claude'], 'Claude'), keyOnly('Paste the key of your Anthropic account', 'eye'), approval(false), hint('Apply needs a key and the confirmed sentence.'), buttons(false))
  const B = cut(
    'B - The test failed',
    'B · The test failed: nothing is changed',
    field(lib, 'Provider key', 'sk-ant-•••••••••••••••••••• 9ZkP'),
    result(false, 'Anthropic refused the key.', 'Nothing was changed: @ai still answers with Qwen2.5-7B · this server. Check the key in your Anthropic account, then Apply again.'),
    mono('Test question sent today 09:31 · HTTP 401', { color: 'color.muted' }),
    hint('Why it is refused here: the first person to ask @ai would otherwise find it out.'),
    buttons(),
  )
  const C = cut(
    'C - Later, a question fails',
    'C · Later, a question fails: the page says why',
    row('answering', [text('label', 'Answering now:', { style: 'hint', color: 'color.muted' }), text('who', 'Claude · claude-sonnet-5-5', { style: 'control-strong', color: 'color.text' }), badge(a, 'remote')], { pad: ['space.8', 'space.12'], radius: 'radius.field', fill: 'color.mist' }),
    callout('red', 'Last error · today 14:02', 'The credit balance at Anthropic is used up.', 'Questions to Claude fail until credit is added or another provider is chosen. It stays until the next question to Claude is answered.'),
    hint('No automatic switch to the local model: the person asking would not know who answered. The administrator decides: add credit, or choose another provider above.'),
  )
  const reason = (cause, t) => row(cause, [text('cause', cause, { style: 'control-strong', color: 'color.text', w: 150 }), text('text', t, { style: 'control', color: 'color.text', w: 'fill' })], { align: 'start' })
  const D = cut(
    'D - The words',
    'D · The words: one sentence for her, the reason for him',
    hint('In the chat, for the person who asked, whatever the cause:'),
    board('said', { w: 'fill', h: 'auto', layout: 'row', pad: ['space.10', 'space.12'], radius: 'radius.row', fill: 'color.mist' }, text('text', 'Claude is not available at the moment. The administrator can see why.', { style: 'sentence', color: 'color.text', w: 'fill' })),
    hint('On the settings page, for the administrator:'),
    reason('Key refused', 'Anthropic refused the key.'),
    reason('Credit used up', 'The credit balance at Anthropic is used up.'),
    reason('Rate limit', "Anthropic's rate limit was reached."),
    reason('Overloaded', 'Anthropic is overloaded at the moment.'),
    reason('No network', 'Anthropic cannot be reached from this server.'),
    reason('Unknown model', 'Anthropic does not know the model “claude-x”.'),
    hint('"<AI type>" is the provider\'s name: Claude here, and the same sentence for the local model if it fails.'),
  )
  return [board('States of the AI page', { w: 'auto', h: 'auto', layout: 'column', gap: 'space.24' }, board('top', { layout: 'row', gap: 'space.24', align: 'start' }, A, B), board('bottom', { layout: 'row', gap: 'space.24', align: 'start' }, C, D))]
}

// --- 3. Preferences ▸ AI… and the owners' consent ------------------------------------------------------------------

function consent(lib, a, d, w) {
  const entry = (label, key, State = 'default') => instance(pick(w.menuEntry, { State }), { edit: { label: { content: label }, key: { content: key } } })
  const menu = (name, title, ...kids) => board(name, { w: 'auto', h: 'auto', layout: 'column', gap: 'space.4' }, text('title', title, { style: 'hint', color: 'color.muted' }), board('menu', { w: 'size.menu-min', h: 'auto', layout: 'column', pad: 'space.4', radius: 'radius.control', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' }, shadow: 'shadow.card' }, ...kids))
  const prefs = menu('Preferences menu', 'Preferences', entry('App language', '▸'), entry('Shortcuts', 'Ctrl+?'), instance(w.menuSep, {}), entry('AI…', 'Ctrl+Shift+Alt+H', 'active'))
  const mac = menu('macOS app menu', 'macOS: the app menu', entry('About claudia', ''), entry('Settings…', 'Cmd+,'), entry('AI…', 'Cmd+Shift+Option+H'), instance(w.menuSep, {}), entry('Quit claudia', 'Cmd+Q'))

  const check = (Checked, label, enabled = true) => instance(pick(d.check, { Checked }), { edit: { label: { content: label } }, ...(enabled ? {} : { opacity: 0.5 }) })
  const sends = () => col('what is sent', [text('title', 'If you allow it, Anthropic is sent:', { style: 'control-strong', color: 'color.text' }), text('one', '•  the question, and the earlier chat between the person who asks and the ai', { style: 'control', color: 'color.text', w: 'fill' }), text('two', '•  the parts of this document the ai looks at to answer her', { style: 'control', color: 'color.text', w: 'fill' }), hint('Documents are encrypted on this server. Claude reads what it is shown in plain text.')], { gap: 'space.4' })
  const answering = (who, Where) => row('answering', [text('label', 'Answering @ai in this document now', { style: 'hint', color: 'color.muted', w: 'fill' }), badge(a, Where)], { pad: ['space.8', 'space.12'], radius: 'radius.field', fill: 'color.mist' })
  const buttons = (kids) => board('buttons', { w: 'fill', h: 'auto', layout: 'row', justify: 'end', gap: 'space.10', m: ['space.8', 0, 0, 0] }, ...kids)
  const dlg = (name, ...kids) => dialogShell(name, 470, instance(d.dialogHeader, { edit: { title: { content: 'AI in this document' } } }), ...kids)

  const off = dlg('1 - An owner, Claude off', answering('Qwen2.5-7B', 'here'), check('no', 'Allow Claude to answer @ai in this document'), hint('Off by default. Only the owners can change it.'), sends(), buttons([button(lib, 'default', 'Cancel'), button(lib, 'primary', 'Save')]), hint('Enter saves · Esc cancels', { w: 'auto' }))
  const on = dlg('2 - An owner, Claude on', answering('Claude', 'remote'), check('yes', 'Allow Claude to answer @ai in this document'), hint('Allowed by anna, today 09:40 · for Claude (Anthropic)'), sends(), hint('Switching it off stops a question that is running before its next step.'), buttons([button(lib, 'default', 'Cancel'), button(lib, 'primary', 'Save')]))
  const readOnly = dlg('3 - An editor or viewer', answering('Claude', 'remote'), check('yes', 'Allow Claude to answer @ai in this document', false), hint('Allowed by anna, today 09:40 · for Claude (Anthropic)'), hint('Only the owners can change this: anna and jonas.'), hint('What Claude is sent when someone asks @ai is listed here for everybody: the question, the earlier chat with the person who asks, and the parts of the document the ai looks at.'), buttons([button(lib, 'primary', 'Close')]))
  const none = dlg('4 - The server offers no remote provider', answering('Qwen2.5-7B', 'here'), text('says', 'This server has no remote AI, so nothing in this document leaves it.', { style: 'control', color: 'color.text', w: 'fill' }), hint('An administrator can add Claude in the server settings. Then the owners can allow it here.'), buttons([button(lib, 'primary', 'Close')]))

  const caption = (t) => text('caption', t, { style: 'control-strong', color: 'color.muted', w: 'fill' })
  const states = board(
    'Dialog states',
    { w: 'auto', h: 'auto', layout: 'row', gap: 'space.24', align: 'start' },
    col('left', [caption('1 · An owner, Claude off (the default for every document)'), off, caption('3 · An editor or viewer: she sees it, and cannot change it'), readOnly], { w: 470, gap: 'space.12' }),
    col('right', [caption('2 · An owner, Claude on: who allowed it and when is shown'), on, caption('4 · The server offers no remote provider: nothing to switch'), none], { w: 470, gap: 'space.12' }),
  )
  const page = board('Preferences - AI', { w: 'auto', h: 'auto', layout: 'column', gap: 'space.24' }, board('menus', { layout: 'row', gap: 'space.24', align: 'start' }, prefs, mac), states)
  return withNotes(
    w,
    page,
    [
      'What the dialog says is what Claude is sent: the question, the earlier chat between the asker and the ai, and the parts of the document the ai looks at for her. The owners agree to exactly that.',
      'The consent names one provider. If the server later uses a different remote provider, this dialog says it is not allowed yet and the owners are asked again; removing and re-adding Claude keeps it.',
      'Saving takes effect at once: a question running through Claude stops before its next round and the chat says so. The title says "in this document" because the menu holds the person\'s own settings.',
      'Config is renamed Preferences in this story, in all three apps, the web app and both desktop clients. Key Ctrl+Shift+Alt+H is free in all three apps and clear of AltGr on a German keyboard.',
      'Never disabled: a viewer opens the dialog too, because the document\'s privacy is everybody\'s business. Menu entry and key go into claudia-menus.xlsx once agreed.',
    ],
  )
}

// --- 4. the History & Chat panel ----------------------------------------------------------------------------------

function chatPanels(a) {
  const who = (t, Where, extra) => board('ai row', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.6' }, text('who', t, { style: 'panel-tab', color: PANEL_TEXT(0.85) }), instance(pick(a.badge, { Where }), {}), ...(extra ? [text('extra', extra, { style: 'panel-label', color: PANEL_TEXT(0.62) })] : []))
  const bubble = (name, t, accent) => board('message', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.2', pad: ['space.7', 'space.10'], radius: 'radius.control', fill: accent ? { raw: '#5B4BC4', opacity: 0.38 } : { raw: '#FFFFFF', opacity: 0.08 } }, text('who', name, { style: 'panel-tab', color: PANEL_TEXT(0.7) }), text('text', t, { style: 'hint', color: PANEL_TEXT(0.95), w: 'fill' }))
  const under = (t, o = {}) => text('under', t, { style: 'panel-label', color: PANEL_TEXT(0.62), w: 'fill', ...o })
  const system = (t) => text('system', t, { style: 'mono-small', color: PANEL_TEXT(0.7), w: 'fill' })
  const input = () => board('field', { w: 'fill', h: 'auto', layout: 'row', pad: ['space.8', 'space.10'], radius: 'radius.control', stroke: { raw: '#FFFFFF', opacity: 0.28, width: 'border.1' } }, text('hint', '@ai …', { style: 'hint', color: PANEL_TEXT(0.6) }))
  const panel = (name, Where, kids) => board(name, { w: 'auto', h: 800, layout: 'column', gap: 'space.8' }, board('caption', { w: 'size.dock', h: 'auto', layout: 'row' }, text('caption', name, { style: 'control-strong', color: 'color.muted', w: 'fill' })), board('frame', { w: 'size.dock', h: 'fill', layout: 'row', clip: true }, sidePanel([], [who('ai', Where === 'remote' ? 'remote' : 'here on dark', Where === 'remote' ? 'allowed' : undefined), ...kids, board('spacer', { w: 'fill', h: 'fill' }), input()])))
  const ask = () => bubble('anna', '@ai why is B7 an error?', true)
  const answer = (t) => bubble('ai', t, false)

  const A = panel('A · Claude answers', 'remote', [ask(), answer("B7 divides by C7, which is empty. I'll divide by the 52 weeks."), under('answered by Claude (remote)')])
  const B = panel('B · Not allowed in this document', 'here', [ask(), answer("B7 divides by C7, which is empty. I'll divide by the 52 weeks."), under('answered by Qwen2.5-7B · this server'), system('Claude is not allowed in this document. The owners can change that in Preferences ▸ AI…')])
  const C = panel('C · Claude is not available', 'remote', [ask(), answer('Claude is not available at the moment. The administrator can see why.'), under('Claude · remote · no answer was made')])
  const D = panel('D · The owners switch it off mid-answer', 'remote', [ask(), system('ai is reading Budget!A1:F8 …'), system('jonas switched Claude off for this document.'), answer('Stopped: Claude was switched off.'), under('Claude · remote · stopped at its next step')])
  return board('Chat panel states', { w: 'auto', h: 'auto', layout: 'row', gap: 'space.24', align: 'start' }, A, B, C, D)
}

export function aiProviderPages(lib, a, d, w) {
  return {
    settings: [settingsPage(lib, a, w)],
    states: settingsStates(lib, a),
    consent: [consent(lib, a, d, w)],
    chat: [withNotes(w, chatPanels(a), [
      'The ai\'s row names who answers: "Claude · remote" (filled) or "Qwen2.5-7B · this server" (outlined). The same badge is on the settings page and in the connection hover. It is always there and always true.',
      'B: without the server\'s approval or the owners\' consent the question goes to the local model, or to the stand-in when there is none, and the chat says so under the answer. It is not an error.',
      'C: one sentence for every cause, "<AI type> is not available at the moment. The administrator can see why." No fallback to another provider; she asks again when she likes.',
      'D: the stop message is "Stopped: Claude was switched off." What was already sent cannot be taken back; the point is that nothing more is. The next question in that document goes to the local model or the stand-in.',
    ])],
  }
}
