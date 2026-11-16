// Windows' dialogs through PowerShell (D501, D502), with a fake PowerShell: what it is asked, and what its answers mean.
import { describe, expect, it } from 'vitest'
import { DIALOG_SCRIPT, filterFor, windowsDialogs } from '../../src/platform/windows-dialogs.js'

type Answer = { code: number; stdout: string; stderr: string }

function fake(...answers: Answer[]) {
  const calls: Array<{ program: string; args: string[]; env: Record<string, string> }> = []
  const run = async (program: string, args: string[], env: Record<string, string>) => {
    calls.push({ program, args, env })
    return answers.shift() ?? { code: 0, stdout: '', stderr: '' }
  }
  return { calls, run }
}

describe('windowsDialogs', () => {
  it('shows the Open dialog in front of the window, with what it needs in the environment, never in the command', async () => {
    const { calls, run } = fake({ code: 0, stdout: 'C:\\Users\\ann\\Budget.docx', stderr: '' })
    const path = await windowsDialogs(run).open({ title: 'Open a File', extensions: ['docx', 'odt'], folder: 'C:\\Users\\ann' })
    expect(path).toBe('C:\\Users\\ann\\Budget.docx')
    expect(calls[0]!.program).toBe('powershell.exe')
    expect(calls[0]!.args).toEqual(['-NoProfile', '-NonInteractive', '-STA', '-ExecutionPolicy', 'Bypass', '-Command', DIALOG_SCRIPT])
    expect(calls[0]!.env).toEqual({
      CLAUDIA_DIALOG: 'open',
      CLAUDIA_TITLE: 'Open a File',
      CLAUDIA_NAME: '',
      CLAUDIA_FOLDER: 'C:\\Users\\ann',
      CLAUDIA_FILTER: 'DOCX, ODT (*.docx;*.odt)|*.docx;*.odt|All files (*.*)|*.*',
    })
    expect(DIALOG_SCRIPT).toContain('TopMost = $true') // the owner that keeps the dialog in front
    expect(DIALOG_SCRIPT).not.toMatch(/\$\{/) // nothing is put into the script itself
  })

  it('suggests the name in the Save dialog, and takes an empty answer for cancelled', async () => {
    const { calls, run } = fake({ code: 0, stdout: '', stderr: '' })
    expect(await windowsDialogs(run).save({ title: 'Save', name: 'a.pdf', extensions: ['pdf'], folder: null })).toBeNull()
    expect(calls[0]!.env).toMatchObject({ CLAUDIA_DIALOG: 'save', CLAUDIA_NAME: 'a.pdf', CLAUDIA_FOLDER: '' })
  })

  it('says what went wrong when PowerShell could not show it', async () => {
    const { run } = fake({ code: 1, stdout: '', stderr: 'Add-Type: cannot load' })
    await expect(windowsDialogs(run).open({ title: 't', extensions: [], folder: null })).rejects.toThrow('cannot load')
  })

  it('opens a PDF with the application Windows has for it, whatever Explorer\'s exit code', async () => {
    const { calls, run } = fake({ code: 1, stdout: '', stderr: '' })
    await windowsDialogs(run).show('C:\\Temp\\claudia-print\\a.pdf')
    expect(calls[0]).toEqual({ program: 'explorer.exe', args: ['C:\\Temp\\claudia-print\\a.pdf'], env: {} })
  })
})

describe('filterFor', () => {
  it('offers the extensions, then every file; leaves out what is not an extension', () => {
    expect(filterFor([])).toBe('All files (*.*)|*.*')
    expect(filterFor(['pdf', 'a|b'])).toBe('PDF (*.pdf)|*.pdf|All files (*.*)|*.*')
  })
})
