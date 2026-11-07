# E0 — cross-OS spike results and the web-surface decision

Two notes merged: the E0.1 and E0.2 spike results (2026-11-01, updated 2026-11-02) and the web-surface reasoning
behind D41–D44 (2026-11-02). Moved here 2026-11-05.

> **Update from the E0.3 work.** The frontend is one web page in two thin shells: GTK 4/libadwaita with WebKitGTK 6.0
> on Linux, Neutralino on Windows and macOS. GTK and libadwaita are therefore needed on Linux only. The Windows GTK
> bundle, the MSYS2 quick check and the macOS GTK quick check are no longer required and are kept as history and as
> fallback evidence.

## Where we stand

| Story | Linux | Windows | macOS |
|---|---|---|---|
| E0.1 libadwaita window | automatic probes pass (headless); looks right in a screenshot | a quick check with the MSYS2 toolchain run by hand on Windows 11: all 8 checklist rows "pass". Bundle: first attempt failed silently, script rewritten, not re-run | postponed, no Mac available; a quick-check script written, never run; no bundle script |
| E0.2 server and workers in the bundle | all scenarios pass, also from a relocated copy | not run | postponed |

Neither story is finished: the acceptance criteria name Windows 10/11 and macOS, and the bundle part of E0.1 has not
been passed on any OS.

## E0.1 — libadwaita window

**Setup.** Ubuntu 24.04 in a headless VM under Xvfb, Cairo renderer, GTK 4.14.5, libadwaita 1.5.0, run once with the
system Python 3.12 and once with CPython 3.14.6 and PyGObject 3.58.1 built from source.

**Results.** All 7 automatic probes pass on both interpreters: the window and four menu buttons, each menu opening as
a popover, `Adw.AboutDialog` opening and closing, a Unicode clipboard round trip (`Größe – 日本語 – 😀`), forcing dark
and light through `Adw.StyleManager`, monitor and scale information, and Unicode in the entry field. Drop-down
verdicts, the file chooser, shortcuts and input methods are hands-on checks that nobody has done. The window renders
like a GNOME application. Start-up with the launcher on 3.14: 0.40 s until imports are done, first frame at 0.70 s —
but this is Xvfb with the software renderer in a VM, so it says nothing about real machines. The layout is a
GtkBuilder file loaded through `Gtk.Template`, including the menus and actions, which works without layout code in
Python as D27 requires.

**Findings.**

1. `Adw.AboutDialog` needs libadwaita 1.5 or newer, which matches D28. Ubuntu 24.04 has exactly 1.5.0.
2. In a `.ui` menu, a `target` attribute with `type="s"` is parsed as GVariant text, so `values` fails with "unknown
   keyword". A plain `<attribute name="target">values</attribute>` is a string and needs no type.
3. **If building the window throws during `activate`, the application neither shows a window nor exits; it just
   hangs.** The spike has a 60 s watchdog and exits with a code. The real shell needs the same.
4. PyGObject 3.58.1 compiles on CPython 3.14.6 once `libgirepository-2.0-dev` and the cairo headers are installed.
5. Accelerators use `<Primary>`, which GTK maps to Cmd on macOS. Whether that behaves is a hands-on check.

**Not shown.** A real GNOME session, Wayland, fractional scaling, the file chooser portal, input methods, dark mode
following the system (headless reports no colour-scheme support), and anything on Windows or macOS. For Linux the
"bundled Python and GTK" criterion is probably the wrong question, because GTK is part of a GNOME system and Flatpak
would be the natural form; Flatpak was not tested.

### Windows 11 quick check (MSYS2 toolchain)

Windows 11 build 26200, MSYS2 UCRT64: Python 3.14.7, GTK 4.24.0, libadwaita 1.10.0, GLib 2.90.0, PyGObject 3.58.0,
German locale, display scaling 200 %. This is the MSYS2 toolchain on a machine that has it installed, not a bundle.

The tester set all 8 rows to "pass" after looking at the window — menus, file chooser, shortcuts, clipboard, dark
mode, HiDPI and text input included — and described the window as looking good. The report shows the system colour
scheme is detected, the input-method context is the Windows one, and the scale factor is 2. The notes field was left
empty, so nothing is recorded about fonts, the title bar or IME behaviour.

**Correction to "all tests passed".** One automatic probe is red in the report: the About dialog was still mapped
200 ms after `force_close()`. The tester judged the dialog fine by eye, so this was a too-short fixed wait rather than
a defect. The probe now polls for up to 3 s and records how long it took (0.16 s on Linux); the Windows number is
still to be seen.

**Start-up** took 10.2 s to imports and 17.9 s to the first frame — but this was the first start after installation,
with nothing warm, so it is not a verdict on GTK on Windows.

### The failed Windows bundle, and what was wrong with the script

The first `bundle_windows.sh` stopped silently after the `pacman` download, every time, with no log. Testing it on
Linux against a fake MSYS2 tree found three defects:

1. **A silent exit path.** The DLL scan was a pipeline under `set -euo pipefail` with `ntldd`'s error output sent to
   `/dev/null`. If one seed file does not exist — an unmatched wildcard stays literal — `ntldd` fails, the pipeline
   fails, and the script ends with exit code 1 and no message. Consistent with the symptom, though not proven to be
   what happened on Windows.
2. **Libraries loaded by name were never copied.** The scan copied only the *dependencies* of its seed files. Nothing
   links `libadwaita-1-0.dll`; GObject Introspection loads it by name from the typelib, so the old script would have
   produced a bundle without it. The same applies to anything only a typelib names.
3. **A stall when the console cannot print the probe output.** With a stdout that cannot encode `😀`, the clipboard
   probe raised `UnicodeEncodeError` inside a GLib callback and the selftest hung until the watchdog. It matters
   because the bundle's smoke test pipes the output.

The rewritten script writes a log, names the failing step and command, treats the optional parts as optional and lists
what it skipped, copies the typelib-named libraries, checks the result with a minimal PATH, generates a launcher that
works without pixbuf loaders, adds a software-rendering fallback, and ends with the bundle's own self-test. It has
been run only against the fake tree, never on Windows.

## E0.2 — embedded server and worker pool

**Setup.** `build_bundle.py` fetches python-build-standalone 3.14.6 with uv, installs fastapi, uvicorn, websockets and
psutil into it, and adds the spike package. The bundle is about 115 MB (101 MB interpreter, hard-linked files counted
once). The driver runs with that interpreter only (`-I`, empty working directory), starts a stand-in "desktop shell"
which starts the server over a lifeline pipe, and checks 10 scenarios per start method.

**Results.** 20 of 20 scenarios pass in the built bundle, and 20 of 20 again after copying it to a temporary folder.

| Criterion | Evidence (Linux, 2 workers) |
|---|---|
| Server starts, client connects | ready in 0.27 s (forkserver) to 0.48 s (spawn); connect 3 ms; ping 0.1 ms |
| Pickled function runs | `add` round trip 0.2–0.3 ms; a lambda is refused with a clear error and the worker stays healthy; pool warm-up 0.24 s (forkserver), 0.42 s (spawn) |
| Not blocking other users | while both workers are busy for 2 s, ping stays under 1 ms and a third task waits 1.6 s in the queue |
| Kill on timeout | a 1 s timeout answers after 1.0 s, the worker is replaced, and a child process of the worker dies with it |
| Worker crash | reported as `worker_died`, the pool refills, the next task runs |
| Clean shutdown | by protocol and by closing the window: everything gone after 0.3–0.4 s |
| No orphans after a crash | shell killed with SIGKILL while workers idle or busy: everything gone after 0.3 s. Server killed with SIGKILL: workers gone after 0.05–0.1 s |

**Findings.**

1. **Busy workers need a parent watchdog.** A worker in the middle of a task never reads its pipe, so closing the pipe
   does not reach it. Each worker has a thread waiting on `multiprocessing.parent_process().sentinel`. A negative
   control with that thread disabled left 3 and 4 processes behind after killing the server with busy workers, for
   both start methods — the scenario fails when it should.
2. **Python 3.14 aborts at exit if a daemon thread is blocked in `sys.stdin.buffer.read()`**
   ("`_enter_buffered_busy: could not acquire lock`"). The lifeline thread did exactly that. Fixed by reading the
   descriptor with `os.read`.
3. **Shutdown cost.** Waiting for each worker in turn made closing with busy workers take 4.3 s. Busy workers are now
   killed immediately and idle ones share one 2 s deadline: 0.3 s.
4. **Closing the parent's copy of the child's pipe end** is what turns a dead worker into an EOF instead of a hang.
   Easy to forget.
5. **Process-tree kill** (psutil) is what made the worker's child die on timeout. What happens without it was not
   tested, so this is "works with", not "needed".

**Not shown.** Everything on Windows and macOS. Things to watch there: console windows flashing, Windows Job Objects
(the watchdog covers the workers, not processes a worker function starts itself), spawn start-up cost,
Defender/SmartScreen/Gatekeeper reactions to a bundled `python.exe`, and notarization. Frozen apps were deliberately
not tested: the bundle is an unfrozen interpreter, so the frozen-multiprocessing risk does not arise unless we decide
to freeze.

## The web surface: why system web views

Plotly is wanted, and replicating it natively would be enormous work (D33). Plotly needs a real browser engine: DOM
and SVG, text measuring, Canvas 2D, WebGL for `scattergl` and 3D, and DOM events.

| Option | Verdict | Why |
|---|---|---|
| WebKitGTK on Windows and macOS | not possible | WebKitGTK and WPE do not support Windows |
| Native chart drawing; server-rendered SVG with a hit map; a matplotlib GTK 4 backend; wxPython | dropped | Plotly is wanted; wxPython uses GTK 3 and cannot be embedded in a GTK 4 process |
| An own mini-engine or a native re-implementation of Plotly | dropped | the enormous work we want to avoid |
| Bundled Chromium (CEF or Electron) off-screen | dropped for size | works and would give frames as textures, but the install is well over 100 MB per OS |
| Servo, off-screen | dropped for now | software rendering, builds of 30+ minutes and several GB, Plotly compatibility untested |
| Our own Windows port of WebKit | dropped | the upstream Windows port builds and runs, and Playwright ships a patched build, but no releases or security advisories were found, a Skia backend landed in Nov 2024 with custom fonts and video broken, and it draws into a native window handle so it would not solve the overlay problem. We would become the engine vendor on one OS |
| **System web views (chosen)** | chosen | no engine in our installs; the OS or distro maintains and patches it; the approach Tauri uses |

Consequences: on macOS and Windows a native web view is an overlay, so nothing from GTK can be drawn over it. Hence
the docked panel (D40) rather than a floating one. Engine versions are outside our control, so a written minimum
feature baseline and a CI matrix are needed, and a Windows 10 machine without the WebView2 runtime needs the
bootstrapper or the offline installer.

### Then: two shells (D42–D44)

Later the same day the plan changed again. Embedding a system web view into a GTK window on Windows and macOS works
only as a native overlay and needs fragile glue, and it would have left two UIs to build. Instead there is **one Nuxt
frontend** and thin shells: GTK 4/libadwaita on Linux with WebKitGTK 6.0 as a real widget; Neutralino on Windows and
macOS with the OS title bar and native menu; and the browser as a third shell. A small shell contract covers menu
actions, file dialogs, About, theme, and starting and stopping the server bundle.

**What is verified about Neutralino** (its own site and docs, not our tests): it uses the OS web view and bundles no
engine; a claimed size of about 2 MB; a WebSocket-based native API for files, commands and dialogs; `setMainMenu`
creates a window menu on Linux and Windows and an application menu on macOS; the config has `nativeAllowList`,
`commandAllowList`, `filesystemScopes` and `tokenSecurity`; the macOS web view lacks `window.print()`.

**Not verified:** web view versions per OS, Wayland behaviour, input methods, accessibility, whether its file dialogs
use the desktop portals, release rhythm and maintainer base. An earlier chat message called it "one maintainer's
project"; that was a guess, not a finding. **Update 2026-11-07:** Neutralino 6.8.0 has since been run on macOS and Windows 11 (see
`e0-3-neutralino-windows-macos.md`); the web view versions, menus, dialogs, clipboard, printing and dead keys are now
observed there. Wayland, screen readers, a clean Windows 10, release rhythm and maintainer base are **still not
checked**, and the whole Windows and macOS story still rests on it. Fallbacks if it disappoints: Tauri (which uses the older GTK 3 WebKitGTK API on Linux) and
pywebview. The shell adapter stays thin so the switch is cheap.

## Proposals for decisions (never entered in the log)

- **A process lifetime protocol** for E3.5 and the desktop launcher: a lifeline pipe from shell to server, a
  parent-sentinel watchdog in every worker, tree kill on timeout, and kill-busy-first on shutdown. Tested on Linux
  only. *Partly realised for the Linux client as D119, which uses a process group and `PR_SET_PDEATHSIG`.*
- **Two interpreters on Windows?** MSYS2's Python and python-build-standalone are different interpreters. With D36 the
  client needs neither numpy nor pandas, so this may be acceptable. Moot on Windows since D42 dropped GTK there.
- **Linux distribution form.** GNOME/Linux probably means Flatpak, where the platform supplies GTK and its own Python;
  D16's "interpreter always bundled" then needs a decision for that case.
- **macOS bundle.** dylibbundler around Homebrew's GTK, or a relocatable conda-forge environment. Moot since D42.

## Sources

WebKit on Windows (https://webkit.org/webkit-on-windows/); WinCairo renamed to Win, July 2024; the Skia backend PR
(https://github.com/WebKit/WebKit/pull/36469); WebKitGTK 2.54.0 release note; WebView2 distribution and
windowed-versus-visual hosting (learn.microsoft.com); the WebView2 offscreen capture example; the GTK issue on
embedding the Edge WebView; `purego-cef2gtk`; `day-piece-webview`; `iced_servo`; plotly.js on `getBBox` and
`getBoundingClientRect` (https://github.com/plotly/plotly.js/pull/7497); Neutralinojs (https://neutralino.js.org/) and
its window API and configuration pages; Tauri 2 and webkit2gtk-4.1.
