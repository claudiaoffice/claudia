---
id: D434
title: "A server started for the desktop apps stops when nobody has used it for a while"
status: current
applies-to: all
date: 2026-11-14
round: "One server, app modules (branch one-server)"
supersedes: []
superseded-by: []
---

# D434 · A server started for the desktop apps stops when nobody has used it for a while

**`--exit-when-idle SECONDS` makes the server stop by itself, gracefully (documents are packed), once nothing has
used it for that long: no open WebSocket — a document's connection or the start page's presence socket
`/api/presence` — and no HTTP request. The desktop apps start their shared local server with it; a server started by
hand or in a container never stops by itself (the option is off by default).**

**Notes.** Owner, 2026-11-14: the last desktop app closing is not enough, because a browser may be using the same
local server, and the server can see its clients itself. A page with a document open already holds a WebSocket (it
drives the connection-quality icon); the start page holds none, so it keeps the presence socket open while it is
shown. The socket carries nothing and needs no login; at most `max_waiting` of them are accepted, and the origin and
host rules of every other socket apply. Stopping goes through the server's normal shutdown (uvicorn's
`should_exit`), not a signal, so it works the same on Windows.
