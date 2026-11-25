// The core's side of the page's files (D501, D502): the dialogs are fakes, the files are real, in a temporary folder.
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FILE_CHUNK_BYTES } from '../src/contract.js'
import { isFileMessage, isFileRequest } from '../src/file-protocol.js'
import { Files, type Dialogs, type FileMessage } from '../src/files.js'

/** Is `message` the last the core sends for a request: its result, or the last piece of a file it reads? */
const ends = (message: FileMessage) => message.kind === 'file_done' || (message.kind === 'file_result' && message.outcome !== 'picked')

/** Until the core has answered `requests` requests (PROC-62: the files are real, and a disk can be slow, so a test waits
 *  for the answer, not for a time). */
const answered = (sent: FileMessage[], requests = 1) =>
  vi.waitFor(() => expect(sent.filter(ends).length).toBeGreaterThanOrEqual(requests), { timeout: 5000 })

describe('Files', () => {
  let dir: string
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'claudia-files-'))
  })
  afterEach(() => rmSync(dir, { recursive: true, force: true }))

  function harness(answers: { open?: string | null; save?: string | null; fails?: boolean } = {}) {
    const sent: FileMessage[] = []
    const asked: Array<{ kind: string; options: unknown }> = []
    const shown: string[] = []
    const dialogs: Dialogs = {
      open: async (options) => {
        asked.push({ kind: 'open', options })
        if (answers.fails) throw new Error('no panel')
        return answers.open ?? null
      },
      save: async (options) => {
        asked.push({ kind: 'save', options })
        if (answers.fails) throw new Error('no panel')
        return answers.save ?? null
      },
      show: async (path) => void shown.push(path),
    }
    const files = new Files({ dialogs, send: (m) => sent.push(m), documents: join(dir, 'Documents'), printFolder: join(dir, 'print') })
    return { files, sent, asked, shown }
  }

  /** The pieces of `bytes` as the page sends them. */
  function send(files: Files, request: string, name: string, bytes: Buffer, purpose: 'save' | 'print' = 'save') {
    files.handle({ kind: 'save_begin', request, name, size: bytes.length, purpose })
    let index = 0
    for (let at = 0; at < bytes.length; at += FILE_CHUNK_BYTES) {
      files.handle({ kind: 'save_chunk', request, index, data: bytes.subarray(at, at + FILE_CHUNK_BYTES).toString('base64') })
      index += 1
    }
    files.handle({ kind: 'save_done', request, chunks: index })
  }

  it('reads the chosen file and sends it in pieces, after saying its name, size and path (SEC-27)', async () => {
    const path = join(dir, 'Budget.docx')
    const bytes = Buffer.alloc(FILE_CHUNK_BYTES + 10, 7)
    writeFileSync(path, bytes)
    const { files, sent, asked } = harness({ open: path })
    files.handle({ kind: 'pick_file', request: 'f1', accept: ['docx', 'odt'] })
    await answered(sent)
    expect(asked[0]).toEqual({ kind: 'open', options: { title: 'Open a File', extensions: ['docx', 'odt'], folder: null } })
    expect(sent[0]).toEqual({ kind: 'file_result', request: 'f1', outcome: 'picked', name: 'Budget.docx', size: bytes.length, path })
    const pieces = sent.filter((m) => m.kind === 'file_chunk')
    expect(pieces.map((m) => m.index)).toEqual([0, 1])
    expect(Buffer.concat(pieces.map((m) => Buffer.from(m.data, 'base64')))).toEqual(bytes)
    expect(sent.at(-1)).toEqual({ kind: 'file_done', request: 'f1', chunks: 2 })
  })

  it('says cancelled when the person closed the dialog, and failed with a reason when it could not be shown', async () => {
    const cancelled = harness({ open: null })
    cancelled.files.handle({ kind: 'pick_file', request: 'f1', accept: [] })
    await answered(cancelled.sent)
    expect(cancelled.sent).toEqual([{ kind: 'file_result', request: 'f1', outcome: 'cancelled' }])
    const broken = harness({ fails: true })
    broken.files.handle({ kind: 'pick_file', request: 'f2', accept: [] })
    await answered(broken.sent)
    expect(broken.sent).toEqual([{ kind: 'file_result', request: 'f2', outcome: 'failed', message: expect.stringContaining('no panel') }])
  })

  it('says why a chosen file could not be read', async () => {
    const { files, sent } = harness({ open: join(dir, 'gone.docx') })
    files.handle({ kind: 'pick_file', request: 'f1', accept: [] })
    await answered(sent)
    expect(sent).toEqual([{ kind: 'file_result', request: 'f1', outcome: 'failed', message: expect.stringContaining('gone.docx') }])
  })

  it('saves a file where the person chose, starting in Documents with the suggested name, and says where', async () => {
    const target = join(dir, 'Budget 2027.xlsx')
    const { files, sent, asked } = harness({ save: target })
    const bytes = Buffer.from(Array.from({ length: FILE_CHUNK_BYTES * 2 + 3 }, (_, i) => i % 256))
    send(files, 'f2', 'Budget 2027.xlsx', bytes)
    await answered(sent)
    expect(asked[0]).toEqual({ kind: 'save', options: { title: 'Save', name: 'Budget 2027.xlsx', extensions: ['xlsx'], folder: join(dir, 'Documents') } })
    expect(readFileSync(target)).toEqual(bytes)
    expect(sent).toEqual([{ kind: 'file_result', request: 'f2', outcome: 'saved', path: target }])
  })

  it('starts the next dialog in the folder of the last file', async () => {
    const { files, sent, asked } = harness({ save: join(dir, 'a.txt') })
    send(files, 'f1', 'a.txt', Buffer.from('a'))
    await answered(sent)
    send(files, 'f2', 'b.txt', Buffer.from('b'))
    await answered(sent, 2)
    expect((asked[1]!.options as { folder: string }).folder).toBe(dir)
  })

  it('writes nothing when the Save dialog was cancelled', async () => {
    const { files, sent } = harness({ save: null })
    send(files, 'f2', 'a.txt', Buffer.from('abc'))
    await answered(sent)
    expect(sent).toEqual([{ kind: 'file_result', request: 'f2', outcome: 'cancelled' }])
  })

  it('refuses a file that lost a piece or came incomplete, and asks nothing', async () => {
    const { files, sent, asked } = harness({ save: join(dir, 'a.txt') })
    files.handle({ kind: 'save_begin', request: 'f2', name: 'a.txt', size: 6, purpose: 'save' })
    files.handle({ kind: 'save_chunk', request: 'f2', index: 1, data: Buffer.from('abc').toString('base64') })
    files.handle({ kind: 'save_done', request: 'f2', chunks: 1 })
    files.handle({ kind: 'save_begin', request: 'f3', name: 'a.txt', size: 6, purpose: 'save' })
    files.handle({ kind: 'save_chunk', request: 'f3', index: 0, data: Buffer.from('abc').toString('base64') })
    files.handle({ kind: 'save_done', request: 'f3', chunks: 1 })
    await answered(sent, 2)
    expect(asked).toEqual([])
    expect(sent.map((m) => m.kind === 'file_result' && m.outcome)).toEqual(['failed', 'failed'])
  })

  it('opens a PDF to print in the computer\'s viewer, from a folder of its own, without asking where (D502)', async () => {
    const { files, sent, asked, shown } = harness()
    send(files, 'f4', '../../Quarterly.pdf', Buffer.from('%PDF-1.7'), 'print')
    await answered(sent)
    expect(asked).toEqual([])
    expect(shown).toEqual([join(dir, 'print', 'Quarterly.pdf')])
    expect(readFileSync(join(dir, 'print', 'Quarterly.pdf'), 'utf8')).toBe('%PDF-1.7')
    expect(sent).toEqual([{ kind: 'file_result', request: 'f4', outcome: 'opened', path: join(dir, 'print', 'Quarterly.pdf') }])
    expect(existsSync(join(dir, 'Quarterly.pdf'))).toBe(false) // the name could not climb out of its folder
  })
})

describe('the file messages between the shell page and the core', () => {
  it('knows a request about files when it sees one', () => {
    expect(isFileRequest({ kind: 'pick_file', request: 'f1', accept: ['docx'] })).toBe(true)
    expect(isFileRequest({ kind: 'save_begin', request: 'f1', name: 'a', size: 1, purpose: 'print' })).toBe(true)
    expect(isFileRequest({ kind: 'save_chunk', request: 'f1', index: 0, data: '' })).toBe(true)
    expect(isFileRequest({ kind: 'save_done', request: 'f1', chunks: 0 })).toBe(true)
    expect(isFileRequest({ kind: 'save_begin', request: 'f1', name: 'a', size: 1, purpose: 'mail' })).toBe(false)
    expect(isFileRequest({ kind: 'pick_file', request: 'x'.repeat(33), accept: [] })).toBe(false)
    expect(isFileRequest({ kind: 'delete_everything' })).toBe(false)
  })

  it('knows a message about files when it sees one', () => {
    expect(isFileMessage({ kind: 'file_result', request: 'f1', outcome: 'saved' })).toBe(true)
    expect(isFileMessage({ kind: 'file_chunk', request: 'f1', index: 0, data: '' })).toBe(true)
    expect(isFileMessage({ kind: 'file_done', request: 'f1', chunks: 0 })).toBe(true)
    expect(isFileMessage({ kind: 'file_chunk', request: 'f1', index: 'x', data: '' })).toBe(false)
  })
})
