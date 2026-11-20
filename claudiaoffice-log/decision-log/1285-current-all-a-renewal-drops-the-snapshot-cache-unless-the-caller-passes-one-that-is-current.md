---
id: D1285
title: "A renewal drops the snapshot cache unless the caller passes one that is current"
status: current
applies-to: all
date: 2026-11-19
round: "The document container and its security, second round, slice C (branch e2-document-sec)"
supersedes: []
superseded-by: []
---

# D1285 · A renewal drops the snapshot cache unless the caller passes one that is current

**Made while building slice C; the owner has not seen it yet (proposal, built).** `content/snapshot.bin` is a cache sealed
with the content key; after a renewal of that key an old one would not open. `change_role` and `remove_person` take a
`snapshot=` argument; the server passes the state it holds, and the container drops the entry when it is not given.
Nothing is lost: the next write makes the cache again.
