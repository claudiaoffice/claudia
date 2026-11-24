---
id: D2003
title: "The server's refusals over HTTP are said in the language the page asks for"
status: current
applies-to: all
date: 2026-11-24
round: "Bug eater, batch 1 follow-up (branch batch-1): CODE-92"
supersedes: []
superseded-by: []
---

# D2003 · The server's refusals over HTTP are said in the language the page asks for

**Decided 2026-11-24** (the owner: "please fix the bugs you found directly"; CODE-92).

A document's refusals reach its connection in the connection's language (D31, D322). The HTTP routes, the server
settings' pages above all, had no language: every refusal was English. Now:

- The web pages send their App Language as `Accept-Language` with every call to `/api/admin` (`createAdminApi`). The
  language stays the client's own setting (D31): the server keeps nothing about it.
- A refusal whose detail is a message of the server (`msg(...)`) is said in the first language of `Accept-Language`
  (`claudia_server/http_refusal.py`, installed for every route). A language without a catalog, or no header, is English.
- A refusal that carries more than its sentence is a `Refused`: the seconds to wait (`retry_after`) and the reason of an
  AI failure (`reason`) stay fields beside `detail`, as before.
- An error of the server's own raised with a message (`ValueError(msg(...))`) keeps it on its way to the answer
  (`message_of`).

**What stays English:** a refusal that comes from another package (claudia-fonts, claudia-typeset, claudia-document-file,
Anthropic's answer): those packages carry no catalogs, as for the document protocol (E5.17). Where a page already turns a
refusal into its own words by status or reason (the setup code, AI failures), it keeps doing so.
