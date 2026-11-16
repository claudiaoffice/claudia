// The Mac's own Open and Save panels for the core (D501), and its viewer for a PDF to print (D502).
//
// The core is a Node process with no window of its own, and Neutralino's `os.showOpenDialog` runs AppleScript's `choose
// file` in an `osascript` process that nothing brings to the front: the panel can open behind the window, which looks
// exactly like "nothing happens" (notes/e5-11-macos-client.md, fourth run). So the panel here is AppKit's own
// NSOpenPanel / NSSavePanel, run by `osascript` in JavaScript for Automation, which first makes its process an
// accessory application and activates it: the panel comes up in front, with the keyboard focus. Should JXA not be
// usable, AppleScript's `choose file` / `choose file name` follows, with an `activate` first. A cancelled panel is
// `null`; a panel that could not be shown is an error, with what osascript said.
//
// Not run on a real Mac yet (README, "Not verified").

import { execFile } from 'node:child_process'
import type { Dialogs } from '../files.js'

type Run = (program: string, args: string[]) => Promise<{ code: number; stdout: string; stderr: string }>

/** NSOpenPanel / NSSavePanel, brought to the front. Arguments: mode (`open`/`save`), title, name, folder, extensions…;
 * prints the chosen path, or nothing when the person cancelled. */
export const PANEL_SCRIPT = `
function run(argv) {
  ObjC.import('AppKit')
  var mode = argv[0], title = argv[1], name = argv[2], folder = argv[3], extensions = argv.slice(4)
  var app = $.NSApplication.sharedApplication
  app.setActivationPolicy(1) // NSApplicationActivationPolicyAccessory: no Dock icon, but allowed in front
  app.activateIgnoringOtherApps(true)
  var panel = mode === 'save' ? $.NSSavePanel.savePanel : $.NSOpenPanel.openPanel
  panel.title = $(title)
  panel.message = $(title)
  if (folder) panel.directoryURL = $.NSURL.fileURLWithPathIsDirectory($(folder), true)
  if (extensions.length) panel.allowedFileTypes = $(extensions)
  if (mode === 'save') {
    panel.nameFieldStringValue = $(name)
    panel.canCreateDirectories = true
  } else {
    panel.canChooseFiles = true
    panel.canChooseDirectories = false
    panel.allowsMultipleSelection = false
  }
  if (panel.runModal != 1) return '' // NSModalResponseOK; the panel is in front, the app was activated above
  var url = mode === 'save' ? panel.URL : panel.URLs.objectAtIndex(0)
  return url.path.js
}
`

function defaultRun(program: string, args: string[]): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    execFile(program, args, { maxBuffer: 1024 * 1024 }, (problem, stdout, stderr) => {
      const code = problem ? (typeof (problem as { code?: unknown }).code === 'number' ? ((problem as { code: number }).code) : 1) : 0
      resolve({ code, stdout: String(stdout), stderr: String(stderr || (problem ? problem.message : '')) })
    })
  })
}

/** An AppleScript string literal. */
function quoted(text: string): string {
  return `"${text.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
}

/** AppleScript's own dialogs, for when the panel script could not run: the same answer, a little less pretty. */
export function appleScriptFor(mode: 'open' | 'save', title: string, name: string, folder: string | null, extensions: readonly string[]): string[] {
  const where = folder ? ` default location (POSIX file ${quoted(folder)})` : ''
  const command =
    mode === 'save'
      ? `POSIX path of (choose file name with prompt ${quoted(title)} default name ${quoted(name)}${where})`
      : `POSIX path of (choose file with prompt ${quoted(title)}${extensions.length ? ` of type {${extensions.map(quoted).join(', ')}}` : ''}${where})`
  return ['-e', 'activate', '-e', command]
}

/** The Mac's dialogs, through `osascript`. `run` is replaced by the tests. */
export function macDialogs(log?: (message: string) => void, run: Run = defaultRun): Dialogs {
  const panel = async (mode: 'open' | 'save', title: string, name: string, folder: string | null, extensions: readonly string[]): Promise<string | null> => {
    const answer = await run('osascript', ['-l', 'JavaScript', '-e', PANEL_SCRIPT, mode, title, name, folder ?? '', ...extensions])
    if (answer.code === 0) {
      const path = answer.stdout.trim()
      return path === '' ? null : path
    }
    log?.(`the ${mode} panel could not be shown with JXA (${answer.stderr.trim()}); AppleScript's dialog instead`)
    const fallback = await run('osascript', appleScriptFor(mode, title, name, folder, extensions))
    if (fallback.code === 0) return fallback.stdout.trim() || null
    if (/-128|User canceled|Benutzer hat abgebrochen/i.test(fallback.stderr)) return null // the person cancelled
    throw new Error(fallback.stderr.trim() || `osascript ended with ${fallback.code}`)
  }
  return {
    open: ({ title, extensions, folder }) => panel('open', title, '', folder, extensions),
    save: ({ title, name, extensions, folder }) => panel('save', title, name, folder, extensions),
    show: async (path) => {
      const answer = await run('open', [path]) // the application the Mac opens PDFs with: Preview, unless the person chose another
      if (answer.code !== 0) throw new Error(answer.stderr.trim() || `open ended with ${answer.code}`)
    },
  }
}
