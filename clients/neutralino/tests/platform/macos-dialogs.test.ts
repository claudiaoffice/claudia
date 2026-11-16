// The Mac's panels through osascript (D501, D502), with a fake osascript: what it is asked, and what its answers mean.
import { describe, expect, it } from 'vitest'
import { PANEL_SCRIPT, appleScriptFor, macDialogs } from '../../src/platform/macos-dialogs.js'

type Answer = { code: number; stdout: string; stderr: string }

function fake(...answers: Answer[]) {
  const calls: Array<{ program: string; args: string[] }> = []
  const run = async (program: string, args: string[]) => {
    calls.push({ program, args })
    return answers.shift() ?? { code: 0, stdout: '', stderr: '' }
  }
  return { calls, run }
}

describe('macDialogs', () => {
  it('asks AppKit for the panel in front, with the title, the folder and the extensions', async () => {
    const { calls, run } = fake({ code: 0, stdout: '/Users/ann/Budget.docx\n', stderr: '' })
    const path = await macDialogs(undefined, run).open({ title: 'Open a File', extensions: ['docx', 'odt'], folder: '/Users/ann' })
    expect(path).toBe('/Users/ann/Budget.docx')
    expect(calls[0]!.program).toBe('osascript')
    expect(calls[0]!.args).toEqual(['-l', 'JavaScript', '-e', PANEL_SCRIPT, 'open', 'Open a File', '', '/Users/ann', 'docx', 'odt'])
    expect(PANEL_SCRIPT).toContain('activateIgnoringOtherApps(true)') // the panel comes up in front (the fourth run's theory)
  })

  it('suggests the name in a Save panel', async () => {
    const { calls, run } = fake({ code: 0, stdout: '/Users/ann/Documents/a.pdf', stderr: '' })
    expect(await macDialogs(undefined, run).save({ title: 'Save', name: 'a.pdf', extensions: ['pdf'], folder: null })).toBe('/Users/ann/Documents/a.pdf')
    expect(calls[0]!.args.slice(4)).toEqual(['save', 'Save', 'a.pdf', '', 'pdf'])
  })

  it('takes an empty answer for a cancelled panel', async () => {
    const { run } = fake({ code: 0, stdout: '\n', stderr: '' })
    expect(await macDialogs(undefined, run).open({ title: 't', extensions: [], folder: null })).toBeNull()
  })

  it("falls back to AppleScript's own dialog when the panel script could not run, and knows its cancel", async () => {
    const logged: string[] = []
    const { calls, run } = fake(
      { code: 1, stdout: '', stderr: 'execution error: ObjC is not defined' },
      { code: 1, stdout: '', stderr: 'execution error: User canceled. (-128)' },
    )
    expect(await macDialogs((m) => logged.push(m), run).open({ title: 'Open a File', extensions: ['docx'], folder: null })).toBeNull()
    expect(calls[1]!.args).toEqual(appleScriptFor('open', 'Open a File', '', null, ['docx']))
    expect(logged[0]).toContain('ObjC is not defined')
  })

  it('says what went wrong when neither could show a dialog', async () => {
    const { run } = fake({ code: 1, stdout: '', stderr: 'nope' }, { code: 1, stdout: '', stderr: 'still nope' })
    await expect(macDialogs(undefined, run).save({ title: 't', name: 'a', extensions: [], folder: null })).rejects.toThrow('still nope')
  })

  it("opens a PDF with the Mac's application for PDFs", async () => {
    const { calls, run } = fake()
    await macDialogs(undefined, run).show('/tmp/claudia-print/a.pdf')
    expect(calls).toEqual([{ program: 'open', args: ['/tmp/claudia-print/a.pdf'] }])
  })
})

describe('appleScriptFor', () => {
  it('quotes what it is given, activates first, and gives a POSIX path back', () => {
    const [, activate, , command] = appleScriptFor('save', 'Save "it"', 'a\\b.pdf', '/Users/ann', [])
    expect(activate).toBe('activate')
    expect(command).toBe('POSIX path of (choose file name with prompt "Save \\"it\\"" default name "a\\\\b.pdf" default location (POSIX file "/Users/ann"))')
    expect(appleScriptFor('open', 'Open', '', null, ['docx', 'odt'])[3]).toBe('POSIX path of (choose file with prompt "Open" of type {"docx", "odt"})')
  })
})
