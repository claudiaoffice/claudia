# Windows client (E5.11), first slice: Claudia Composes

> **Superseded in architecture (2026-11-11):** the D159 injection design described below was replaced by D251; see `e5-11-windows-client-complete.md`. This file stays as history, including the four real runs of 2026-11-09.

Written 2026-11-08. What was built for the native Windows client of **composes**, how it was checked, what it
carries over unchanged from the macOS slice (`e5-11-macos-client.md`) versus what is genuinely different on this
OS, and where it stands on D159 — the same transport question the macOS slice closed for its own platform.
Built on the branch `win-client`, handed over as a patch (no push access to GitHub from this session; the owner
creates the branch and applies it, her usual workflow for feature branches).

Scope and depth for this slice were the owner's own explicit choices, asked up front rather than assumed: bring
`macos-client`'s decision-log/backlog content forward into this branch's own (stale) copy of both rather than only
appending to them; match the macOS slice's depth ("full E5.11 parity") rather than a minimal skeleton; and, for the
one genuinely open platform question below (D161), match macOS's own precedent of flagging a gap rather than
building a fix nobody has asked for yet.

Code: `clients/windows/` (package `claudia-shell-windows`) and `clients/contract/` (the shell contract, unchanged).
Human documentation: `clients/windows/README.md`, also meant for the Sphinx docs once this package has any (it is
plain TypeScript/Node, no Sphinx target set up yet — see "Open points").

## What exists

- `claudia-composes`: a thin Neutralino 6.8.0 shell, application id `de.claudiaoffice.composes`, with a native
  Windows menu built from the shared GTK manifest (`manifest.py`'s `describe()`) rather than a second hand-written
  one — composes rather than creates, the inverse of macOS's own first-app choice, matching this branch's own
  name.
- A **local server started by the Node launcher itself**, not by Neutralino: `launch.ts`'s `prepareServer()`
  mirrors `launch.py`'s and the macOS client's own `prepareServer()` almost line for line (same two `SetupProblem`
  messages — missing Python 3.14, missing built frontend — same folder-creation-before-start behaviour), adapted
  for `%LOCALAPPDATA%\Claudia` instead of `~/Library/Application Support` or XDG.
- **D159, carried over rather than re-decided**: the owner's own framing when scoping this slice was that the
  transport question was "how does a Neutralino shell reach the frontend", not "how does a *macOS* Neutralino
  shell reach it" — nothing in the spike or the macOS build found a platform split in the answer, so it was not
  asked again. `launch.ts`'s `main()` starts the server first (its address has to exist before anything else), then
  starts the Neutralino binary with `--url=<that address>` and `--path=apps/composes`, identical flags to macOS.
  **Not yet confirmed on a real Windows machine**, unlike macOS's own confirmed run — see "Not verified".
- `page-bridge.ts`'s `installBridge()` is the whole adapter the web app needs, structurally identical to macOS's:
  it shims `window.webkit.messageHandlers.claudia.postMessage` to the exact shape
  `web/app/lib/shell-bridge.ts`'s `detectHandler()` already looks for. **`shell-bridge.ts` itself needed zero
  further changes** — D121's "the page speaks the contract directly" now covers a third shell with no change to
  the second shell's own adapter pattern.
- `manifest.py`'s `role` field (D158), added for macOS, was **missing from this branch's own starting point** and
  so is the one Linux-side change this patch carries, ported from `macos-client` rather than re-derived: the Cocoa
  editing selector a macOS Edit item needs. Windows's own `menu.ts` reads nothing from this field (see "Mapping to
  the shared manifest" below) — it exists in the shared manifest for macOS's sake alone, carried through
  `generate_menu.py`'s JSON output for every shell regardless of whether a given shell reads it.
- Checks: `tsc --strict`, vitest (57 tests: identity, paths, server including `freePort()`, menu, page-bridge,
  launch), pytest clean on the Python side (`generate_menu.py`, 10 tests), a drift guard (`npm run check-menu`)
  between the checked-in `src/generated/menu.*.json` and `manifest.py` itself. No further GTK-side changes beyond
  the carried-over `role` field.

Nothing in `web/` was changed. Nothing in `clients/linux/` or `clients/macos/` changed.

## Deviation from the plan

Same reading as macOS's own: D43 ("desktop clients bundle the frontend, never load it from a remote server"), on a
literal pass, looks like it rules out an external loopback URL at all. D115 already qualified this for Linux and
D159's own note observes that a loopback server run by the shell itself arguably still satisfies D43's intent. This
client follows the same reading macOS already established, rather than re-litigating it: the frontend is still the
one built into the checkout; the local server just serves it over loopback instead of the window loading it
directly from disk.

## Mapping to the shared manifest

Deliberately simpler than macOS's own `buildMainMenu()`. Windows keeps File, Edit, Format, View, Tools, Config,
Help as one ordinary window menu — there is no application-menu convention to relocate About and Quit into the way
D44 has macOS do, so `menu.ts` does not rebuild or relocate anything: the manifest's own menu order is the window
menu, unchanged.

| Native item | Carried out by | Notes |
|---|---|---|
| File ▸ Quit | shell | `Neutralino.app.exit()` directly, same special case as macOS's App-menu Quit — the one click `routeMenuClick()` does not forward to the page, because the shell ends the process either way. |
| Help ▸ About | page | `Kind.SHELL` in the manifest (GTK shows a native dialog), forwarded here anyway — Neutralino has no native About on any platform (D158 point 4); `AboutDialog.vue` already exists and needed no change for a third shell either. |
| Edit ▸ Undo/Redo/Cut/Copy/Paste | page dispatch **only** | Unlike macOS, there is no native Cocoa selector to also fire — every Edit item, standard ones included, is a plain contract `action` message, the same path Linux already uses for Undo/Redo. `role` is read from nowhere in this module. |
| Everything else (File/Format/View/Tools/Config) | page | Forwarded as a contract `action` message, same as every other shell. |

## First real run (owner, Windows VM + Git Bash, 2026-11-09)

The owner ran the start script from a Git Bash shell on a Windows VM. It did not reach the point of starting the
Neutralino binary — it failed one step earlier, during `npm run build:inject` (part of `npm run build`, which
`start-win-client.cmd` runs on every invocation):

```
node:internal/modules/esm/load:191
    throw new ERR_UNSUPPORTED_ESM_URL_SCHEME(parsed, schemes);
Error [ERR_UNSUPPORTED_ESM_URL_SCHEME]: Only URLs with a scheme in: file, data, and node are supported by the
default ESM loader. On Windows, absolute paths must be valid file:// URLs. Received protocol 'c:'
```

One real bug, caught and fixed before any further patch:

1. **`tools/build-inject.mjs` passed a bare filesystem path to a dynamic `import()`.** Line 20 builds
   `identityPath` with `node:path`'s `join()` — correct for `readFileSync`/`existsSync`, which take filesystem
   paths — but line 26 then handed that same string straight to `await import(identityPath)`. A dynamic import
   specifier has to resolve as a URL. `node:path`'s `join()` returns a bare path, which Node's ESM loader
   tolerates for an absolute **POSIX** path (`/home/...` has no `scheme:` prefix to misread) — exactly why this
   never surfaced in this sandbox's own Linux build-and-test cycle — but an absolute **Windows** path starts with
   a drive letter, and `C:\Users\...\dist\identity.js` parses as a URL whose scheme is `c:`, which is not on the
   loader's allow-list (`file:`, `data:`, `node:`). Fixed with Node's own documented answer for exactly this:
   `pathToFileURL(identityPath).href` instead of the bare path, which produces a valid `file:` URL on every OS
   (confirmed directly in this sandbox: `new URL('C:\\Users\\dev\\dist\\identity.js').protocol` is `'c:'`;
   `new URL(pathToFileURL('C:\\Users\\dev\\dist\\identity.js').href).protocol` is `'file:'`).

   New test: `tests/build-inject.test.ts` (3 cases), pinned to the scheme-parsing property itself rather than to
   `build-inject.mjs`'s own `main()` (which runs real esbuild/filesystem side effects the moment the module is
   imported, so it is not imported directly in a test — the same reasoning `page-bridge.ts`'s own tests already
   use for `installBridge()`). 60 vitest tests now, up from 57.

   **The identical bug exists, unexercised, in `clients/macos/tools/build-inject.mjs`** (same `join()`-then-
   `import()` pattern; never triggered because POSIX absolute paths are tolerated) — flagged for the owner to
   carry the same one-line fix over, not fixed here since this patch has no reach into the `macos-client` branch.

This is a build-time-only bug: it would have hit any Windows VM in the same way, Git Bash or not, regardless of
PATH, `uv`, or Neutralino. Nothing about D159 was tested by this run — the failure happened one step before the
server or the Neutralino binary were ever started. The next real run, once this fix is applied, should get as far
as `findNeutralinoBinary()`'s own "fetch it with npx @neutralinojs/neu update" message, or further.

## Second real run (owner, same Windows VM, 2026-11-09): past the build, stopped at `uv sync`

Applying the first fix got one step further into `start-win-client.cmd`, to its very first line: `uv sync`.
It failed trying to compile `pyyaml` from source:

```
error: Failed to build `pyyaml==6.0.3`
  cause: Call to `_pyyaml_pep517.build_wheel` failed (exit code: 1)
  ...
  error: Microsoft Visual C++ 14.0 or greater is required. Get it with "Microsoft C++ Build Tools": ...
hint: `pyyaml` (v6.0.3) was included because `claudia-monorepo:dev` (v0.0.0) depends on `myst-parser` (v5.1.0)
      which depends on `pyyaml`
```

The `hint:` line names the actual problem precisely: `pyyaml` is pulled in by `myst-parser`, which is pulled in by
the root `[dependency-groups] dev` group (Sphinx docs tooling, `pytest`/`mypy`/`ruff`/`vulture` alongside it) —
`uv sync` installs that group by default, even though nothing in it is a runtime dependency of `claudia_server`,
`claudia_client`, or any of this client's own code (checked directly: no `packages/*/pyproject.toml` depends on
`pyyaml` or `myst-parser`). `pyyaml` tries to compile an optional Cython-accelerated extension unless told not to,
and that compile needs a C toolchain — present on neither this VM nor, as far as this patch knows, assumed by
anything else this client needs. The owner's Python here is **3.15**, released recently enough that `pyyaml`
6.0.3 has no prebuilt Windows wheel for it yet on PyPI, forcing the source build that then hit the missing
compiler. An older or more established Python/OS combination might well have found a prebuilt wheel and never
noticed this at all — this is a supply-chain timing problem as much as a Windows one.

Fixed by not installing the `dev` group in the first place: `uv sync --quiet` → `uv sync --quiet --no-dev` in
`start-win-client.cmd`. Confirmed directly in this sandbox (Linux, not Windows, but `uv`'s dependency-group
resolution is platform-independent): `uv tree --no-dev` lists no `pyyaml`, `myst-parser`, or `sphinx` anywhere;
the default `uv tree` lists all three, each tagged `(group: dev)`. This is also simply the more correct
invocation for what this script is for — starting a client to test it, not developing the repository's own
Python code or building its docs — so it is not a workaround so much as a latent wrong default being corrected.

**`start-client.sh` (Linux) and `start-mac-client.sh` (macOS) both call plain `uv sync --quiet` too**, with the
same latent exposure to this — unhit so far only because neither of those OSes' own Python/compiler situation has
triggered a source build of something in `dev` yet. Flagged for the owner to carry the same `--no-dev` flag to
both, same as the `build-inject.mjs` flag from the first real run.

## Third real run (owner, same Windows VM, 2026-11-09): build and `uv sync` both succeed, then... nothing

With both fixes applied, `start-win-client.cmd` got all the way through building the web app and the Windows
client and fetching the Neutralino binary (`npx @neutralinojs/neu update` ran once, as expected) — and then
`node clients\windows\dist\launch.js composes` produced **no output at all and exited immediately**, no window,
no error, no console line of any kind.

The owner's own first guess was a missing Microsoft Edge WebView2 Runtime on this particular Windows 11 VM image.
That turned out not to be the actual cause here, for a specific reason: if the Neutralino binary itself had
actually been spawned and then failed to show a window because WebView2 was missing, that failure would show up
as *some* output, because `main()` spawns the shell with `stdio: 'inherit'` — whatever the binary itself prints
on its way to failing reaches this console directly. Total silence, with literally nothing printed, pointed
instead at `main()` never being called in the first place.

That is exactly what was happening. The bottom of `launch.ts` has always had an entry-point guard meant to make
`node dist\launch.js composes` (run directly) call `main()`, the same idiom `launch.py` uses with
`if __name__ == "__main__"` and the macOS client's own `launch.ts` uses with the same `import.meta.url` check:

```ts
if (import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).then((code) => {
    process.exitCode = code
  })
}
```

`import.meta.url` is a well-formed URL Node computes correctly on every OS. The right-hand side is not: it is a
bare string template built from `process.argv[1]`, a raw filesystem path with no attempt to turn it into a
proper URL. On POSIX this happens to work anyway, because an absolute path already starts with `/`, so
`"file://" + "/home/.../launch.js"` is already the valid `"file:///home/.../launch.js"`. On Windows,
`process.argv[1]` is backslashed and drive-lettered (`C:\Users\...\dist\launch.js`); prepending `"file://"` to
that produces a string that is not a valid URL at all, and can never equal `import.meta.url`'s real,
forward-slashed, percent-correct form (`file:///C:/Users/.../dist/launch.js`). The comparison was always false on
Windows. `main()` was never called. The whole script, from the point of view of `node dist\launch.js composes`,
was a silent no-op — which is exactly the symptom reported.

Fixed the same way as the first two bugs this run cycle found: `pathToFileURL(process.argv[1] ?? '').href`
instead of the bare template, Node's own documented way to turn a filesystem path into a correct `file:` URL on
every OS. Verified directly in this sandbox: running the fixed `dist/launch.js` now reaches `main()` and prints
its own expected `SetupProblem` message (missing Python 3.14 in this sandbox, exit code 1) instead of exiting
silently with nothing printed and code 0. Two new regression tests in `tests/launch.test.ts` pin down the
comparison's own correctness in isolation — `main()` itself is not re-run in a test, since it has real side
effects (spawning a server, and if found, a real Neutralino binary).

This is the third bug in a row this real-run cycle found that has the identical shape: a Windows absolute path
(backslashes, a drive letter) breaking an assumption a POSIX absolute path happens to satisfy by coincidence.
**The identical line exists, unexercised, in `clients/macos/src/launch.ts`** — worth the same one-line fix there,
and at this point probably worth a dedicated pass over `clients/macos/` for this exact pattern rather than
rediscovering it a fourth time.

The owner's WebView2 hypothesis is not dismissed by this, only provisionally ruled out as the *current* blocker.
Once this fix lets `main()` actually run and the Neutralino binary actually gets spawned, a missing WebView2
Runtime becomes the natural next thing to check if the window still doesn't appear — see the README's "Not
verified" item 5.

## Fourth real run (owner, same Windows VM, 2026-11-09): the server starts, but a new console window and a timeout

With the third fix applied, `main()` is finally called and the local server gets spawned for real. Two new
things showed up:

**A new, separate console window for the Python server.** `defaultSpawn()` (`server.ts`) passes `detached: true`
to `node:child_process.spawn`, and Node's own docs are explicit about what that does on Windows beyond what its
POSIX meaning might suggest: a detached child gets its own, new console window, independent of whatever `stdio`
options are also given. Here `stdio` already redirects both the server's stdout and stderr to `logPath` (never
to any console at all), so the window that popped up was never going to show anything — exactly what the owner
reported: a separate console, with nothing printed to it. Node documents `windowsHide` as the flag for
suppressing that window specifically (a no-op on every other OS, per the same docs), so it is added alongside
`detached: true`, not instead of it — `detached` is kept for the one thing Windows still honours about it (this
module's own top comment: the child survives this process exiting unexpectedly). Confirmed as the right fix by
reading Node's own `child_process` documentation directly rather than guessing from the symptom alone. New
regression test in `tests/server.test.ts` spies on `node:child_process`'s `spawn` (`vi.mock` + `vi.hoisted`,
wrapping the real implementation so the file's other, already-existing `defaultSpawn` test still gets a genuine
child process) to check the actual options object passed — `windowsHide`, unlike `detached`, leaves no trace on
the resulting `ChildProcess` object afterwards for a test to read back any other way.

**The server itself did not answer within `LocalServer`'s 30-second startup timeout** (`checkReady()`'s own
`ServerStartError`, `server.ts`): `the server did not answer at http://127.0.0.1:50424 within 30000ms`. This is
not yet understood, and this round does not claim to fix it — guessing at a cause from the symptom alone, after
three straight bugs already found this way, is exactly the discipline this whole real-run cycle has tried not
to fall into.

What is known: the process did not exit (that would have produced a different error — "the server stopped at
start-up (exit code N)" — since `checkReady()` checks `process.exitCode` before the timeout check), so whatever
is happening, the Python process stayed alive the whole 30 seconds without the server answering `/api/health`.
`cli.py`'s own `main()` prints its start-up banner (host, port, TLS status, administrators, web app path) with
`flush=True` *before* calling into `uvicorn.run()` — so if the log this client writes to
(`%LOCALAPPDATA%\Claudia\composes\state\server.log`, computed by `prepareServer()` as
`join(stateDir(identity.name), 'server.log')`) contains that banner, the server itself started and is uvicorn
that is not answering (or answering somewhere the health check cannot reach); if the log is empty, something
upstream of the banner — argument parsing, loading the document model, loading server settings from
`--state-dir` — is itself the slow or stuck part. `ServerStartError`'s own message is supposed to append that
log's last 2000 characters automatically (`whatItSaid()`), so the console output already ought to show which of
these it is — the owner's report did not include that section, which is either because the log was genuinely
empty, or because the console output as pasted was trimmed before the tail. Either way, the next thing needed
to go further here is that log's actual content (or the untrimmed console output), not another guess.

A genuinely plausible explanation worth naming without committing to it: Windows Defender (or another real-time
antivirus) scanning a large, freshly-installed `.venv`'s DLLs and `.pyd` files on first access is a well-known
source of multi-second-to-multi-minute delays for a Python process's first import of packages like `uvicorn`'s
or `fastapi`'s dependencies, on a machine that has never run them before — `uv sync` just populated that `.venv`
fresh. If that is what is happening here, the fix is not a code change at all (raising the 30-second timeout
would only mask a one-time cold-start cost, and the *right* number to raise it to is not knowable from here) —
it is confirming the actual delay and, if AV scanning is it, either accepting the one-time cost or excluding the
`.venv` from real-time scanning. Not committed to as the cause without the log confirming it.

## Compatibility notes

1. **No real `SIGTERM` on Windows, not even for the ordinary stop path.** Node's own docs are explicit that
   `ChildProcess.kill()` ignores the `signal` argument on Windows and always terminates outright ("similar to
   SIGKILL"). Unlike macOS's SIGTERM-then-SIGKILL `stop()` (itself already missing Linux's PDEATHSIG belt), there
   is no softer first step to send at all here — one `kill()` call already is the hard stop, so the `graceMs`
   option on `stop()` is kept only for interface parity with the other two shells (a caller that does not care
   which OS it is on can still call `await server.stop()`) and is otherwise dead code. This is a real product gap
   written down deliberately, not matched silently: **a hard-killed `claudia_server` gets no graceful shutdown on
   Windows at all**, true even before considering what happens if the *shell* itself is killed outright (D161,
   same open issue macOS already flags, arriving one step earlier here).
2. **No process-group kill either.** `detached: true` on Windows, per Node's own docs, makes the child "not share
   its console with the parent" but does *not* give it a killable process group the way POSIX does. Unlike
   macOS/Linux reaching a negative pid to kill a whole group for free, there is nothing here to reach a
   `claudia_server` that has itself spawned children. Not solved here, flagged alongside point 1.
3. **A separate compiled binary, not an in-process shell**, same as macOS: Neutralino is a binary this launcher has
   to find (`findNeutralinoBinary()`) and spawn. Not checked into the repository (D157); `CLAUDIA_NEUTRALINO_BIN`
   or the conventional `apps/<app>/bin/neutralino-win_x64.exe` path (where `npx @neutralinojs/neu update` places
   it) is how a real install supplies it. **One genuine simplification versus macOS**: Neutralino 6.8.0 publishes
   exactly one Windows binary, so `neutralinoBinaryName()` takes no architecture parameter at all, unlike macOS's
   `arm64`/`x64` branch.
4. **`injectScript` runs before any `<script type=module>` tag does**, same as macOS — `inject-entry.ts` is bundled
   by esbuild into one dependency-free IIFE (`tools/build-inject.mjs`), not shipped as an ES module.
5. **`enableServer: true`** is Neutralino's own documented requirement for loading a remote/external URL, same as
   macOS — not re-verified separately for Windows, since this is Neutralino's own flag, not an OS-specific one.
6. **`nativeAllowList` trimmed to four exact method names** (`app.exit`, `window.setMainMenu`, `window.print`,
   `events.on`) — two fewer than macOS's six, because there is no `file-dialog.ts` here and so no
   `os.showOpenDialog`/`filesystem.readBinaryFile` call to allow (see point 7). `filesystemScopes` stays empty.
7. **No `file-dialog.ts` (D216) — a reasoned omission, not yet confirmed.** macOS needs this module because
   WKWebView shows no native Open panel for `<input type="file">` without a WKUIDelegate method Neutralino's
   generic binary does not implement. WebView2, the engine behind Neutralino's Windows binary, is Chromium, and
   Chromium has had its own native `<input type="file">` picker since long before Neutralino existed — so the
   expectation is that composes' Insert Image dialog already works with no shell-side help. This is a hypothesis
   built from how the two engines are documented to behave, not a result checked by clicking the button on a real
   machine; if it turns out wrong, the fix is structurally identical to macOS's own (`Neutralino.os.showOpenDialog`,
   `Neutralino.filesystem.readBinaryFile` are the same surfaces on both OSes).
8. **No `app-bundle.ts` equivalent, and none is needed.** macOS needs that module because the Dock, the
   application-menu heading and Activity Monitor all read a running process's bundle identity (`CFBundleName`),
   which a bare downloaded binary does not have. Windows has no equivalent identity source to fix — the taskbar
   and the window's own title bar both already read `neutralino.config.json`'s `modes.window.title` directly, the
   same way every shell always has, so `launch.ts` spawns the downloaded binary as-is.

## Not verified (needs a real Windows machine)

Four real runs have happened (see "First real run" through "Fourth real run" above), each fixing one bug and
getting one step further than the last — the build, then `uv sync`, then `main()` actually being called, then
the server itself actually spawning (minus its own stray console window) — but the fourth stopped at the
server's own 30-second startup timeout, for a reason not yet understood (see that run's own notes), so none has
yet reached the point where the Neutralino binary itself is spawned. Unlike the macOS slice, where a confirmed
run narrowed this list, everything below is still exactly as open as it was before the first of these runs:

1. **D159's core mechanic on Windows** — expected to carry over unchanged from macOS's confirmed result, not
   independently confirmed.
2. **D216's hypothesis**: whether `<input type="file">` truly needs no workaround on WebView2.
3. **The native-menu-plus-page-dispatch interaction** on composes' actual document editor, not just a generic text
   field.
4. **What happens to the server if the Neutralino window is killed outright** (D161) — untested, and, per
   compatibility notes 1–2, structurally has even less of a safety net than macOS's own untested case.
5. **A second machine, an older Windows version, a screen reader.** This client has only been built and tested in
   a Linux sandbox so far — no Windows machine of any kind yet.

## Open points for the owner

- **D159 needs the same real-machine test macOS already got.** Nothing here is blocked on that — it is simply the
  next piece of evidence this slice is missing.
- **Printing** (D158 point 2) is still not wired as a contract message, same gap as macOS — `Neutralino.window.print()`
  is typed in `NeutralinoLike` but nothing calls it yet, on either OS.
- **Packaging** (a real installer, `.ico` from the existing PNGs, codesigning, a Start Menu shortcut) is entirely
  open; this slice only produces a runnable `dist\launch.js` against a checkout.
- **Computes and creates** have `identity.ts` entries (`packaged: false`) and generated menu JSON but no
  `apps/<app>/` folder yet — the same "one more entry point" shape left open on every other shell for its own
  not-yet-built apps.
- **No CI job for this package yet**, matching macOS's own choice not to add one for its first slice (the Linux
  client has one Linux-only job in the main gate); nothing here runs the Windows suite automatically today.
- **The orphaned-process gap (D161)** is a known open issue, not a blocker for this patch — the owner's own
  explicit choice when scoping this slice, matching macOS's precedent rather than building a Windows Job Object now.
