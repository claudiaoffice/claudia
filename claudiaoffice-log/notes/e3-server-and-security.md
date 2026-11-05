# Server security fixes — SEC-01, SEC-02, SEC-07

Written 2026-11-03 against `e7fc1ef`; moved here 2026-11-05. Package: claudia-server **0.6.0** (breaking changes, see
below). The server as originally built is described in `e1-kernel.md` under "Server (E3.1)".

All three fixes are in `main` at `54d1245` and were re-verified in the 2026-11-05 review.

## Why these three

From the tracker, the three most critical *still open at HEAD*: SEC-01 (P1, any web page could drive a local server),
SEC-02 and SEC-07 (P2, the only open items reachable over the network). SEC-03 and SEC-04 were listed as open but were
already fixed in the code; the tracker was stale. SEC-05 and SEC-06 are not reachable on the wire (see follow-ups).

## SEC-01 — DNS rebinding

The Origin check compared `Origin` with the page's own `Host`, so a page on a rebound name passed it. Measured against
the real server before the fix: 101 for the WebSocket, 200 for `GET /api/docs`.

Fix: `claudia_server/hosts.py`, `HostGuard`, an ASGI middleware that is the **outermost** layer — before CORS, so a
refused name gets no CORS headers. HTTP: 403 with a text naming `--allow-host`; WebSocket: close code **4403**. Exactly
one `Host` header is required.

Allowed: `localhost`; every IP literal, because an address cannot be rebound, except the unspecified `0.0.0.0` and
`::`; `--host` if it is a name; every `--tls-name`; `--allow-host` (repeatable); and the machine's
`socket.gethostname()`. The fully qualified domain name is deliberately **not** added automatically, because it can
stall on DNS; add it with `--allow-host`. Matching is ASCII-only — found by review, because Unicode case folding let
the Kelvin sign match `k`.

## SEC-02 — unlimited documents, unbounded pre-login connections

- `Hub(max_documents=1000)`, `--max-documents`. Refusal: `HubError("unavailable")`, close 1013. Counting uses an id
  set filled once from the store and extended on every open, **because the sealed store creates its file in `add_user`
  before `Hub.open`** — found only by testing on a real server.
- `--max-waiting` (256) and `--max-waiting-per-address` (64) for connections that have not logged in yet. The slot is
  taken before `accept`, so a client that was let on keeps its place; excess connections are accepted and closed
  with 1013.
- An optional access secret (at least 16 characters) from `--access-secret-file` or `CLAUDIA_ACCESS_SECRET`, needed in
  `hello.params.access` to **create** a document and as `Authorization: Bearer` to read the list. Compared with
  `hmac.compare_digest`. A refused creation is answered exactly like a missing document (D50). People of an existing
  document log in without it.
- A secret that is asked for but empty or too short stops the server, because an empty variable is what an unset value
  in a compose file looks like, and failing open would be silent.

## SEC-07 — plain text on the network

`--no-tls` with a non-loopback `--host` is a `UsageError` unless `--behind-proxy` is given; `--behind-proxy` without
`--no-tls` is refused. `scripts/start.py` requires `--tls` for hosts that are not this computer. The start banner
prints a warning in the proxy case.

## Breaking changes (CHANGELOG 0.6.0)

1. A client must now call the server by a name it answers to; behind a reverse proxy or a custom name, use
   `--allow-host`.
2. `--no-tls` on a non-loopback address needs `--behind-proxy`. Docker images that bound `0.0.0.0` plain must set it.
3. The public API snapshot was regenerated: `Gateway`, `create_app` and `Hub` got new keyword arguments, and `hosts`
   is an internal module not in `__all__`.

## Test-suite changes to know about

- `tests/conftest.py` has an autouse fixture that makes Starlette's `TestClient` call the app as `localhost`; its
  default `testserver` and hard-coded WebSocket Host would now be refused. Whitelisted in `vulture_whitelist.py` with
  a reason.
- New: `test_server_hosts.py`, `test_server_admission.py`; extended `test_server_cli.py` and `tests/test_start_script.py`.
- `test_a_missing_document_costs_as_much_time_as_a_wrong_password` (SEC-04) is a timing comparison and fails now and
  then on a loaded machine. Unrelated to these changes; worth making less sensitive.

## Measured

Real uvicorn, before and after: a rebound Host with a matching Origin went 101 → 4403; `/api/docs` went 200 → 403;
legitimate `localhost`, `127.0.0.1` and `[::1]` were unaffected; plain text on `0.0.0.0` is refused by both the CLI and
the launcher; the waiting and document caps hold. Before the fix, 120 sockets that connected and never logged in were
all held, and 120 wrong-password logins at once queued for 60 s without finishing.

## Follow-ups (not done, on purpose)

- **Per-address back-off on failed logins** (the rest of E2.7): the waiting caps bound the queue, but nothing slows a
  patient guesser. The next best step against brute force (SEC-11).
- **SEC-05** (redaction leaves content behind): not reachable on the wire, but it breaks a product promise; it needs
  the journal and block rewrite.
- **SEC-06** (the self-signed certificate is a CA): only matters when a person installs it as a system root; the safe
  fix is `ca=False` plus partial-chain verification in the client.
- The access secret travels in the first WebSocket frame, so it needs TLS like passwords — which SEC-07 now enforces
  off-loopback.
- `--allow-host` is a name list only, with no wildcards. Decide whether teams behind many proxy names need that.
- **The gate still prints "clean" when the web checks are skipped** (PROC-02), so the web client's tests and type check
  did not run against these changes.
- `ruff format --check .` already reported unformatted files at `main`, and the gate does not run it (CODE-08).
  Nothing unrelated was reformatted.
