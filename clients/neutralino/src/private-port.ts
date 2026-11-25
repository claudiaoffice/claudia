// The port of a person's private server (E8.5, D1621): her own, the same at every start, so that what the page keeps
// for that address (Mine, collections, server bookmarks) stays hers. The twin of clients/linux/.../private_port.py; both
// are held to clients/contract/private-port.vectors.json.
//
// Below the ports the systems hand out by themselves (macOS and Windows from 49152, Linux from 32768), and away from
// 8765, the port of every shared Claudia server (D1621).

/** Who the person is, as her computer knows her: an account number where there is one (macOS, Linux), else her
 * profile folder (Windows). */
export type Account = { uid: number } | { profileFolder: string }

export const PRIVATE_PORTS = { first: 20000, last: 29999 } as const
const SPAN = PRIVATE_PORTS.last - PRIVATE_PORTS.first + 1

/** Her port: by her account number; on Windows by her profile folder, whatever its case. Two accounts of one Mac or
 * Linux computer never get the same one (their numbers are below 10000 apart); on Windows they rarely might, and then
 * the second one is held like any port that somebody else holds. */
export function privatePort(account: Account): number {
  const number = 'uid' in account ? account.uid : fnv1a(account.profileFolder.toLowerCase())
  return PRIVATE_PORTS.first + (((number % SPAN) + SPAN) % SPAN) // in her range for any number, -1 included
}

/** The other ports of her range, in the order her apps try them while hers is held: the ones after it, then from the
 * first. Every window of hers walks the same order, so two that start at once try the same port, and one of them wins
 * it (D435). */
export function* walkFrom(usual: number): Generator<number> {
  for (let step = 1; step < SPAN; step++) yield PRIVATE_PORTS.first + ((usual - PRIVATE_PORTS.first + step) % SPAN)
}

/** FNV-1a, 32 bits, over the UTF-8 bytes of `text`. */
function fnv1a(text: string): number {
  let hash = 0x811c9dc5
  for (const byte of new TextEncoder().encode(text)) {
    hash = Math.imul(hash ^ byte, 0x01000193) >>> 0
  }
  return hash
}
