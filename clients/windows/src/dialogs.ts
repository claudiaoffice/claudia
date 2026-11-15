// Windows' own Open and Save dialogs for the core (D501), and its application for a PDF to print (D502).
//
// The core is a Node process with no window of its own, so the dialogs are shown by PowerShell with Windows Forms
// (the common file dialogs every Windows has, no download). A dialog of another process opens behind the Claudia
// window unless it has an owner that is in front, so it gets a top-most, invisible form as its owner. What it needs
// (title, filter, folder, name) is handed over in the environment, not on the command line, so nothing in it can change
// what PowerShell runs; the chosen path comes back as UTF-8 on stdout. A cancelled dialog is `null`; a dialog that
// could not be shown is an error, with what PowerShell said.
//
// Not run on a real Windows machine yet (README, "Not verified").

import { execFile } from 'node:child_process'
import type { Dialogs } from './files.js'

type Run = (program: string, args: string[], env: Record<string, string>) => Promise<{ code: number; stdout: string; stderr: string }>

/** The PowerShell script of both dialogs. Reads CLAUDIA_DIALOG (`open`/`save`), CLAUDIA_TITLE, CLAUDIA_FILTER,
 * CLAUDIA_FOLDER and CLAUDIA_NAME; prints the chosen path, or nothing when the person cancelled. */
export const DIALOG_SCRIPT = [
  '$ErrorActionPreference = "Stop"',
  '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8',
  'Add-Type -AssemblyName System.Windows.Forms',
  '[System.Windows.Forms.Application]::EnableVisualStyles()',
  '$owner = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true; ShowInTaskbar = $false; Opacity = 0; StartPosition = "CenterScreen"; Width = 1; Height = 1 }',
  '$owner.Show(); $owner.Activate()',
  'if ($env:CLAUDIA_DIALOG -eq "save") { $dialog = New-Object System.Windows.Forms.SaveFileDialog; $dialog.OverwritePrompt = $true; $dialog.FileName = $env:CLAUDIA_NAME }',
  'else { $dialog = New-Object System.Windows.Forms.OpenFileDialog; $dialog.Multiselect = $false; $dialog.CheckFileExists = $true }',
  '$dialog.Title = $env:CLAUDIA_TITLE',
  'if ($env:CLAUDIA_FILTER) { $dialog.Filter = $env:CLAUDIA_FILTER }',
  'if ($env:CLAUDIA_FOLDER) { $dialog.InitialDirectory = $env:CLAUDIA_FOLDER }',
  '$answer = $dialog.ShowDialog($owner)',
  '$owner.Close()',
  'if ($answer -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($dialog.FileName) }',
].join('\n')

/** The dialog's filter: the extensions given (`Claudia's files (*.docx;*.odt)|*.docx;*.odt`) and every file. */
export function filterFor(extensions: readonly string[]): string {
  const safe = extensions.filter((e) => /^[a-z0-9]{1,16}$/.test(e))
  const all = 'All files (*.*)|*.*'
  if (safe.length === 0) return all
  const patterns = safe.map((e) => `*.${e}`).join(';')
  return `${safe.map((e) => e.toUpperCase()).join(', ')} (${patterns})|${patterns}|${all}`
}

function defaultRun(program: string, args: string[], env: Record<string, string>): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    execFile(program, args, { env: { ...process.env, ...env }, windowsHide: true, maxBuffer: 1024 * 1024 }, (problem, stdout, stderr) => {
      const code = problem ? (typeof (problem as { code?: unknown }).code === 'number' ? (problem as { code: number }).code : 1) : 0
      resolve({ code, stdout: String(stdout), stderr: String(stderr || (problem ? problem.message : '')) })
    })
  })
}

/** Windows' dialogs, through PowerShell. `run` is replaced by the tests. */
export function windowsDialogs(run: Run = defaultRun): Dialogs {
  const dialog = async (mode: 'open' | 'save', title: string, name: string, folder: string | null, extensions: readonly string[]) => {
    const answer = await run('powershell.exe', ['-NoProfile', '-NonInteractive', '-STA', '-ExecutionPolicy', 'Bypass', '-Command', DIALOG_SCRIPT], {
      CLAUDIA_DIALOG: mode,
      CLAUDIA_TITLE: title,
      CLAUDIA_NAME: name,
      CLAUDIA_FOLDER: folder ?? '',
      CLAUDIA_FILTER: filterFor(extensions),
    })
    if (answer.code !== 0) throw new Error(answer.stderr.trim() || `PowerShell ended with ${answer.code}`)
    const path = answer.stdout.trim()
    return path === '' ? null : path
  }
  return {
    open: ({ title, extensions, folder }) => dialog('open', title, '', folder, extensions),
    save: ({ title, name, extensions, folder }) => dialog('save', title, name, folder, extensions),
    show: async (path) => {
      // Explorer opens a file with the application Windows has for its kind (the PDF viewer, Edge by default). Its
      // exit code says nothing about that, so only a failure to start it at all is an error.
      const answer = await run('explorer.exe', [path], {})
      if (/ENOENT/.test(answer.stderr)) throw new Error(answer.stderr.trim())
    },
  }
}

/** The dialogs of this computer. */
export function defaultDialogs(_log?: (message: string) => void): Dialogs {
  return windowsDialogs()
}
