// Vitest global setup: fetch the starter fonts and the hyphenation patterns the tests use into layout/.fonts, once,
// each checked by SHA-256.
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { CACHE, hyphenationLock, lock } from './fonts'

export default async function setup(): Promise<void> {
  mkdirSync(CACHE, { recursive: true })
  const files = [...lock().flatMap((c) => c.files.filter((f) => f.name.endsWith('.ttf'))), ...hyphenationLock()]
  for (const file of files) {
    const target = join(CACHE, file.name)
    if (existsSync(target) && createHash('sha256').update(readFileSync(target)).digest('hex') === file.sha256) continue
    const answer = await fetch(file.url)
    if (!answer.ok) throw new Error(`cannot fetch the test fixture ${file.url}: HTTP ${answer.status}`)
    const bytes = new Uint8Array(await answer.arrayBuffer())
    const got = createHash('sha256').update(bytes).digest('hex')
    if (got !== file.sha256) throw new Error(`${file.name}: SHA-256 ${got}, the lock file says ${file.sha256}`)
    writeFileSync(target, bytes)
  }
}
