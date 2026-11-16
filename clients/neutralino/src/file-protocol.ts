// What the shell page and the core say to each other about files (D501, D502): the requests and messages, and the
// checks of both. No Node and no browser import, so the shell page (bundled for the browser) and the core share it.

import type { FileOutcome } from './contract.js'

/** What the core tells the shell page about a file (passed on to the page as contract messages). */
export type FileMessage =
  | { kind: 'file_result'; request: string; outcome: FileOutcome; name?: string; size?: number; path?: string; message?: string }
  | { kind: 'file_chunk'; request: string; index: number; data: string }
  | { kind: 'file_done'; request: string; chunks: number }

/** The shell page's requests about files. */
export type FileRequest =
  | { kind: 'pick_file'; request: string; accept: string[]; title?: string }
  | { kind: 'save_begin'; request: string; name: string; size: number; purpose: 'save' | 'print' }
  | { kind: 'save_chunk'; request: string; index: number; data: string }
  | { kind: 'save_done'; request: string; chunks: number }

/** Is `value` a request about files, as the shell page sends it? */
export function isFileRequest(value: Record<string, unknown>): boolean {
  const request = typeof value.request === 'string' && value.request.length <= 32
  switch (value.kind) {
    case 'pick_file':
      return request && Array.isArray(value.accept) && value.accept.every((e) => typeof e === 'string') && (value.title === undefined || typeof value.title === 'string')
    case 'save_begin':
      return request && typeof value.name === 'string' && Number.isInteger(value.size) && (value.purpose === 'save' || value.purpose === 'print')
    case 'save_chunk':
      return request && Number.isInteger(value.index) && typeof value.data === 'string'
    case 'save_done':
      return request && Number.isInteger(value.chunks)
    default:
      return false
  }
}

/** Is `value` a message about files, as the core sends it? */
export function isFileMessage(value: Record<string, unknown>): boolean {
  const request = typeof value.request === 'string'
  switch (value.kind) {
    case 'file_result':
      return request && typeof value.outcome === 'string'
    case 'file_chunk':
      return request && Number.isInteger(value.index) && typeof value.data === 'string'
    case 'file_done':
      return request && Number.isInteger(value.chunks)
    default:
      return false
  }
}
