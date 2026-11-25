---
id: D1621
title: "Her own server is on a port of her account, 20000–29999; 8765 stays the port of every shared server"
status: current
applies-to: all
date: 2026-11-25
round: "E8.5 macOS installer, part 1: Private on this computer (branch `mac-installer`; CODE-99)"
supersedes: [D504]
superseded-by: []
---

# D1621 · Her own server is on a port of her account, 20000–29999; 8765 stays the port of every shared server

**A person's private server is on her own port: `20000 + uid % 10000` on macOS and Linux, `20000 + FNV-1a-32(her profile
folder, lower-cased, UTF-8) % 10000` on Windows, which has no account numbers.** It is worked out at every start, not
stored. `CLAUDIA_SERVER_PORT` still takes its place (a person who needs that port, tests). 8765 stays the port of every
shared server: `./start.sh`, Docker, the cloud, and the service (D1622). **When something else holds her port** (a program,
or a Claudia server that is not hers, D1620), her server goes to the next free port of her range (after hers, then from
20000: the same order for every window of hers, so two that start at once meet on one port and D435 decides), for as long
as that lasts, written down in `desktop-server.json` as `{"instead": N}` so that her other apps find it there. A start
uses her server where it is; once it is gone and her own port is free, it starts there again and the file goes (the
owner's answer to the review of `private-place.feature`, question 1). A window whose server went away starts it again
on the port its page is on, if that is free. A file from before,
`{"port": N}`, is not read.

**Why.** The page keeps Mine, collections and server bookmarks per address: her own server needs one address that does not
change from one start to the next, whoever else is logged in (the grilling of 2026-11-25, Q15). From her account, two
accounts of one Mac or Linux computer never collide (their numbers are below 10000 apart); the range is below the ports
the systems hand out by themselves (macOS and Windows from 49152, Linux from 32768), and has no 8765 in it.

**Supersedes D504** for the desktop's own server, which D504 put on 8765 "so the address stays the same": it still does,
but per person. **Accepted (Q15):** what the page kept for `127.0.0.1:8765` (Mine, collections, server bookmarks) looks
empty once after the update; no migration, the suite being pre-release.

**Alternatives.** The service on another port and her own server on 8765: the second person logged in would still have to
move, and her address would depend on who logged in first. A port chosen once and stored: changes nothing but adds a file
that can be lost. Two accounts of one Windows PC may get the same port (rare): the second one is held like any taken port.

**Notes.** Code: `private-port.ts` / `private_port.py`, `private-server.ts` / `private_server.py`, `HostPlatform.account`.
Pinned by `clients/contract/private-port.vectors.json`.
