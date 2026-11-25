---
id: D1620
title: "A person's apps use only her own server, which proves to be hers with a key from her state folder"
status: current
applies-to: all
date: 2026-11-25
round: "E8.5 macOS installer, part 1: Private on this computer (branch `mac-installer`; CODE-99, CODE-100)"
supersedes: []
superseded-by: []
---

# D1620 · A person's apps use only her own server, which proves to be hers with a key from her state folder

**Her desktop apps (macOS, Windows, Linux) start her private server with a key from her own state folder
(`--owner-key-file <state>/owner.key`: 32 random bytes as 64 hex digits, made at the first start, readable by her only) and
use a Claudia server they find on her port only when it answers a fresh challenge with it: `GET /api/owner?challenge=<64
lower-case hex digits>` → `{"answer": hex(HMAC-SHA256(key, "claudia owner proof\n" + port + "\n" + challenge))}`.** The
port in the answer is the one the server listens on, from its socket, not from the request. A server without a key (every
shared one) has no `/api/owner`; one answers only a client on this computer, as the version in `/api/health` (D445). A
Claudia server that does not prove to be hers is treated like any program that holds her port (D1621): her apps neither use
it nor complain about its version (CODE-100); the version check stays for her own server, whose message ("stops by itself
ten minutes after its last window has closed") is now true. When two of her windows start at once, the one that lost uses
the winner only when it proves to be hers.

**Why.** Before, any Claudia server of this version on 8765 was "this computer's server, whoever started it" (D445,
`desktop-server.ts`): with two people logged in, the second one's documents were written into the first one's home folder
(CODE-99), and a service of another version locked every app out (CODE-100). The owner's rule (grilling of 2026-11-25, Q13):
a person's apps only ever use her own server; a service is a place of its own (D1622).

**The port in the answer**: a program that holds her usual address could otherwise pass her challenge on to her real server,
which then runs elsewhere (D1621), and take the answer for its own. **Loopback only**: nobody else needs it.

**Alternatives.** The access secret (`--access-secret-file`) as the proof: a server with one refuses the page's list and
creation, which the web app cannot answer yet (E5.22 adds that, to keep other accounts out of her list altogether). The
state folder's path in `/api/health`: tells every program where she keeps her files, and proves nothing. A Unix socket with
the peer's credentials: WKWebView, WebView2 and WebKitGTK reach a server over TCP only.

**Notes.** The key never leaves her state folder and the server; an answer reveals nothing of it. A file that holds no key is
made anew (a server started with the old one then no longer proves to be hers, and her apps start their own beside it). Not
guarded against: another account that reads her state folder (her files' permissions are the guard), and another account
that reaches her server on purpose and lists her documents' titles (E5.22). The answers are pinned by
`clients/contract/private-port.vectors.json`, which the server's, the macOS/Windows client's and the Linux client's tests read.
Code: `owner_proof.py` (server), `owner-key.ts` / `owner_key.py`, `private-server.ts` / `private_server.py` (clients).
