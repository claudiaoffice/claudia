// The service of a computer, "Shared on this computer" (E8.5 part 2, D1622, D1624): a shared server that the
// computer starts for everyone, never a person's own (D1620). Its installer writes a marker, `service.json`
// (`{"origin": "http://127.0.0.1:8765", "state": "<its state folder>"}`, where `HostPlatform.sharedServiceFile` says),
// and removes it with the service; the core reads it at start and lists the service after her private place.
//
// While the service has no administrator, its setup code is in its state folder, which only the computer's
// administrators may read (the installers see to that): for them the core sends it with the service's page, as it does
// for her own server (D1373); anyone else's page is told to ask an administrator of this computer.

import { accessSync, constants, readFileSync } from 'node:fs'
import { isAbsolute, join } from 'node:path'
import { readSetupCode } from './private-server.js'

/** What a person may learn of the service's setup code: the code, that there is none (it has an administrator), or
 * that she may not read it. */
export type SetupCodeAccess = { kind: 'code'; code: string } | { kind: 'none' } | { kind: 'may not' }

export interface SharedService {
  /** `http://127.0.0.1:<port>`, as the marker says. */
  readonly origin: string
  /** Read anew at every call: the service may have been started again. */
  setupCode(): SetupCodeAccess
}

const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]'])

/** The service the marker `file` names, or `null`: no marker, or one that is broken or points away from this computer
 * (a marker can only name a server of this computer). */
export function findSharedService(file: string): SharedService | null {
  let marker: { origin?: unknown; state?: unknown }
  try {
    marker = JSON.parse(readFileSync(file, 'utf8')) as typeof marker
  } catch {
    return null
  }
  const origin = loopbackOrigin(marker.origin)
  const state = marker.state
  if (origin === null || typeof state !== 'string' || !isAbsolute(state)) return null
  return { origin, setupCode: () => setupCodeIn(state) }
}

function loopbackOrigin(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    if ((url.protocol !== 'http:' && url.protocol !== 'https:') || !LOOPBACK_HOSTS.has(url.hostname)) return null
    return url.origin === value ? value : null
  } catch {
    return null
  }
}

function setupCodeIn(state: string): SetupCodeAccess {
  try {
    accessSync(join(state, 'admin'), constants.R_OK | constants.X_OK)
  } catch {
    return { kind: 'may not' }
  }
  const code = readSetupCode(state)
  return code === null ? { kind: 'none' } : { kind: 'code', code }
}
