// The page's files on this computer (D501, D502), on the core's side: the Open and Save dialogs, reading the chosen
// file and writing the saved one, and handing a PDF to the computer's viewer to print it. The page cannot do any of
// this itself in a window: the web view may show no dialog for a file input at all (WKWebView in the macOS client does not),
// none opens from a menu item, and a download goes to some folder without a word.
//
// A file travels in pieces (`file_chunk`, at most 36 KiB each, as base64), because a message of the shell contract has
// at most 64 KiB; the shell page passes them between the page and this core unchanged. How a dialog is shown is the
// operating system's business (dialogs.ts); everything else here is the same on macOS and Windows (the twin of
// clients/macos/src/files.ts), and is tested with fake dialogs and a temporary folder.

import { mkdir, readFile, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, dirname, join } from 'node:path'
import { FILE_CHUNK_BYTES, MAX_FILE_BYTES } from './contract.js'
import type { FileMessage, FileRequest } from './file-protocol.js'

export type { FileMessage, FileRequest } from './file-protocol.js'

/** The computer's own dialogs and viewer. Each answers `null` when the person cancelled. */
export interface Dialogs {
  open(options: { title: string; extensions: readonly string[]; folder: string | null }): Promise<string | null>
  save(options: { title: string; name: string; extensions: readonly string[]; folder: string | null }): Promise<string | null>
  /** Open `path` with the computer's application for its kind (the PDF viewer, which prints). */
  show(path: string): Promise<void>
}

interface Incoming {
  name: string
  size: number
  purpose: 'save' | 'print'
  pieces: Buffer[]
  received: number
  broken: string | null
}

export interface FilesOptions {
  dialogs: Dialogs
  send: (message: FileMessage) => void
  /** Where a Save dialog starts the first time: the person's Documents folder. */
  documents: string
  /** Where a PDF to print is put before the viewer opens it. */
  printFolder?: string
  log?: (message: string) => void
}

/** A name that is a file name and nothing else: no folder, nothing that would climb out of the print folder. */
function plainName(name: string): string {
  const base = basename(name.replace(/\\/g, '/'))
  return base && base !== '.' && base !== '..' ? base : 'claudia-file'
}

function extensionOf(name: string): string[] {
  const dot = name.lastIndexOf('.')
  const extension = dot > 0 ? name.slice(dot + 1).toLowerCase() : ''
  return /^[a-z0-9]{1,16}$/.test(extension) ? [extension] : []
}

export class Files {
  private readonly incoming = new Map<string, Incoming>()
  /** The folder of the last file opened or saved: the next dialog starts there. */
  private lastFolder: string | null = null

  constructor(private readonly options: FilesOptions) {}

  private log(message: string): void {
    this.options.log?.(message)
  }

  handle(request: FileRequest): void {
    switch (request.kind) {
      case 'pick_file':
        void this.pick(request.request, request.accept, request.title)
        return
      case 'save_begin':
        this.incoming.set(request.request, { name: plainName(request.name), size: request.size, purpose: request.purpose, pieces: [], received: 0, broken: null })
        return
      case 'save_chunk':
        this.chunk(request.request, request.index, request.data)
        return
      case 'save_done':
        void this.finish(request.request, request.chunks)
        return
    }
  }

  private fail(request: string, message: string): void {
    this.log(`file ${request}: ${message}`)
    this.options.send({ kind: 'file_result', request, outcome: 'failed', message })
  }

  // --------------------------------------------------------------------------------------------- choosing

  private async pick(request: string, accept: string[], title?: string): Promise<void> {
    let path: string | null
    try {
      path = await this.options.dialogs.open({ title: title || 'Open a File', extensions: accept, folder: this.lastFolder })
    } catch (problem) {
      return this.fail(request, `The Open dialog could not be shown: ${(problem as Error).message}`)
    }
    if (path === null) {
      this.options.send({ kind: 'file_result', request, outcome: 'cancelled' })
      return
    }
    let bytes: Buffer
    try {
      const { size } = await stat(path)
      if (size > MAX_FILE_BYTES) return this.fail(request, `${basename(path)} is larger than ${MAX_FILE_BYTES / 1024 / 1024} MB.`)
      bytes = await readFile(path)
    } catch (problem) {
      return this.fail(request, `${basename(path)} could not be read: ${(problem as Error).message}`)
    }
    this.lastFolder = dirname(path)
    const { send } = this.options
    send({ kind: 'file_result', request, outcome: 'picked', name: basename(path), size: bytes.length })
    let index = 0
    for (let at = 0; at < bytes.length; at += FILE_CHUNK_BYTES) {
      send({ kind: 'file_chunk', request, index, data: bytes.subarray(at, at + FILE_CHUNK_BYTES).toString('base64') })
      index += 1
    }
    send({ kind: 'file_done', request, chunks: index })
  }

  // ----------------------------------------------------------------------------------------------- saving

  private chunk(request: string, index: number, data: string): void {
    const file = this.incoming.get(request)
    if (file === undefined || file.broken !== null) return
    if (index !== file.pieces.length) {
      file.broken = 'a piece of the file went missing on the way'
      return
    }
    const piece = Buffer.from(data, 'base64')
    file.received += piece.length
    if (file.received > file.size) {
      file.broken = 'more of the file arrived than was announced'
      return
    }
    file.pieces.push(piece)
  }

  private async finish(request: string, chunks: number): Promise<void> {
    const file = this.incoming.get(request)
    this.incoming.delete(request)
    if (file === undefined) return
    if (file.broken === null && (chunks !== file.pieces.length || file.received !== file.size)) file.broken = 'the file did not arrive whole'
    if (file.broken !== null) return this.fail(request, `The file could not be saved: ${file.broken}.`)
    const bytes = Buffer.concat(file.pieces)
    if (file.purpose === 'print') return this.print(request, file.name, bytes)
    let path: string | null
    try {
      path = await this.options.dialogs.save({
        title: 'Save',
        name: file.name,
        extensions: extensionOf(file.name),
        folder: this.lastFolder ?? this.options.documents,
      })
    } catch (problem) {
      return this.fail(request, `The Save dialog could not be shown: ${(problem as Error).message}`)
    }
    if (path === null) {
      this.options.send({ kind: 'file_result', request, outcome: 'cancelled' })
      return
    }
    try {
      await writeFile(path, bytes)
    } catch (problem) {
      return this.fail(request, `${path} could not be written: ${(problem as Error).message}`)
    }
    this.lastFolder = dirname(path)
    this.log(`file ${request}: saved ${bytes.length} bytes as ${path}`)
    this.options.send({ kind: 'file_result', request, outcome: 'saved', path })
  }

  /** D502: the PDF goes into a folder of its own and the computer's viewer opens it; its Print prints it. */
  private async print(request: string, name: string, bytes: Buffer): Promise<void> {
    const folder = this.options.printFolder ?? join(tmpdir(), 'claudia-print')
    const path = join(folder, name)
    try {
      await mkdir(folder, { recursive: true })
      await writeFile(path, bytes)
      await this.options.dialogs.show(path)
    } catch (problem) {
      return this.fail(request, `The pages could not be opened to print: ${(problem as Error).message}`)
    }
    this.options.send({ kind: 'file_result', request, outcome: 'opened', path })
  }
}
