// Saving and choosing files of this computer (D501): the shell's dialogs in a desktop window, the browser's in a tab.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadBase64, downloadJSON, downloadText, saveBlob } from '~/lib/download'
import { chooseLocalFile } from '~/lib/local-files'
import { createShellBridge } from '~/lib/shell-bridge'

const WELCOME = JSON.stringify({ type: 'welcome', contract: 1, shell: { name: 'gtk', platform: 'linux', version: '1' }, capabilities: ['native-menu', 'files'] })

/** A shell that answers every `save_file` with `saved` and every `pick_file` with one small file. */
function shellThatAnswers() {
  const posted: Record<string, unknown>[] = []
  let bridge: ReturnType<typeof createShellBridge> | null = null
  const sink = {
    post: (m: Record<string, unknown>) => {
      posted.push(m)
      const answer = (reply: Record<string, unknown>) => queueMicrotask(() => bridge?.receive(JSON.stringify(reply)))
      if (m.type === 'file_done') answer({ type: 'file_result', request: m.request, outcome: 'saved', path: '/home/ann/out' })
      if (m.type === 'pick_file') {
        answer({ type: 'file_result', request: m.request, outcome: 'picked', name: 'a.docx', size: 2 })
        answer({ type: 'file_chunk', request: m.request, index: 0, data: btoa('hi') })
        answer({ type: 'file_done', request: m.request, chunks: 1 })
      }
    },
    listen: () => () => {},
  }
  bridge = createShellBridge('composes', sink)
  bridge.receive(WELCOME)
  return { bridge, posted }
}

describe('saving a file', () => {
  const detachers: Array<() => void> = []
  afterEach(() => {
    for (const detach of detachers.splice(0)) detach()
    vi.unstubAllGlobals()
  })

  it('in a desktop window goes through the shell, and says where it went', async () => {
    const { bridge, posted } = shellThatAnswers()
    detachers.push(bridge.detach)
    expect(await downloadText('notes.md', '# hi', 'text/markdown')).toEqual({ kind: 'saved', path: '/home/ann/out' })
    expect(posted.find((m) => m.type === 'save_file')).toMatchObject({ name: 'notes.md', size: 4, mime: 'text/markdown' })
    expect(await downloadJSON('a.json', { a: 1 })).toEqual({ kind: 'saved', path: '/home/ann/out' })
    expect(await downloadBase64('a.bin', 'application/octet-stream', btoa('xyz'))).toEqual({ kind: 'saved', path: '/home/ann/out' })
  })

  it('in a browser tab is a download', async () => {
    const clicked: string[] = []
    vi.stubGlobal('document', { createElement: () => ({ click() { clicked.push(this.download) } }) })
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:x', revokeObjectURL: () => {} })
    expect(await saveBlob('a.txt', new Blob(['x']))).toEqual({ kind: 'downloaded' })
    expect(clicked).toEqual(['a.txt'])
  })
})

describe('choosing a file', () => {
  it('in a desktop window asks the shell, with the extensions of the input', async () => {
    const { bridge, posted } = shellThatAnswers()
    const taken: File[] = []
    const input = { accept: '.docx,.odt', click: vi.fn() } as unknown as HTMLInputElement
    await chooseLocalFile(input, (file) => taken.push(file))
    expect(input.click).not.toHaveBeenCalled()
    expect(posted.find((m) => m.type === 'pick_file')).toMatchObject({ accept: ['docx', 'odt'] })
    expect(taken.map((f) => f.name)).toEqual(['a.docx'])
    bridge.detach()
  })

  it('in a browser tab clicks the input, whose change handler takes the file', async () => {
    const input = { accept: '.docx', click: vi.fn() } as unknown as HTMLInputElement
    await chooseLocalFile(input, () => {})
    expect(input.click).toHaveBeenCalledOnce()
  })
})
