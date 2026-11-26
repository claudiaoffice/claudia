// The service of a computer, "Shared on this computer" (E8.5 part 2, D1622, D1624): a shared server that the
// computer starts for everyone, never a person's own (D1620). Its installer writes the service file `service.json`
// (`{"origin": "http://127.0.0.1:8765", "state": "<its state folder>"}`, where `HostPlatform.sharedServiceFile` says)
// and removes it with the service; the core reads it at start and lists the service after her private place.
//
// While the service has no administrator, its setup code is in its state folder, which only the computer's
// administrators may read (the installers see to that): for them the core sends it with the service's page, as it does
// for her own server (D1373); anyone else's page is told to ask an administrator of this computer.

import { readFileSync } from 'node:fs'
import { isAbsolute } from 'node:path'
import { setupCodeAccess, type SetupCodeAccess } from './private-server.js'

export interface SharedService {
  /** `http://127.0.0.1:<port>`, as the service file says. */
  readonly origin: string
  /** Read anew at every call: the service may have been started again, or been given an administrator. */
  setupCode(): SetupCodeAccess
}

type ServiceFile = { origin?: unknown; state?: unknown }

const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]'])

/** The service that the service file `file` names, or `null`: no file (nothing to say), or one that is broken or points
 * away from this computer (it can only name a server of this computer), which is logged. */
export function findSharedService(file: string, log?: (line: string) => void): SharedService | null {
  let text: string
  try {
    text = readFileSync(file, 'utf8')
  } catch {
    return null // no service on this computer
  }
  let named: ServiceFile | null = null
  try {
    named = JSON.parse(text) as ServiceFile | null
  } catch {
    // reported below
  }
  const origin = loopbackOrigin(named?.origin)
  const state = named?.state
  if (origin === null || typeof state !== 'string' || !isAbsolute(state)) {
    log?.(`The shared service is not listed: ${file} does not name a server of this computer and its state folder`)
    return null
  }
  return { origin, setupCode: () => setupCodeAccess(state) }
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
