# Spike E8.5: an installed macOS app whose launcher becomes its window

**Throwaway.** It answers one question before part 3 of `claudiaoffice-log/notes/e8-5-architecture.md` is built: when an
app installed from a `.pkg` starts with a shell script that `exec`s the Neutralino binary inside the same app, does macOS
show **one** Dock icon with the app's name and icon, and does it open at all, unsigned (ad-hoc signed only)?

## What it builds

`claudia-composes-spike.pkg`, which installs exactly the layout of the design, for composes only:

```
/Applications/claudia composes.app/Contents/
    Info.plist, MacOS/claudia-composes (launcher.sh), MacOS/neutralino, Resources/composes.icns
/Library/Application Support/Claudia/runtime/
    node/ (Node 22, darwin-arm64), client/ (dist, apps/composes), web/, spike/prepare.mjs
```

What differs from the real package: the server is your checkout's (`.venv/bin/python`, named in `runtime/spike/settings.sh`),
there is no service and no uninstaller app, and `prepare.mjs` stands in for the launcher's future `--prepare` mode.

The start: `claudia-composes` runs `prepare.mjs` (copies the app's folder to `~/Library/Caches/Claudia/run/composes`, links
`node` in there, writes the core's command and `window.sh`), then `exec`s `window.sh`, which `exec`s
`claudia composes.app/Contents/MacOS/neutralino`. Both `exec`s keep the process macOS launched.

## What was checked here (Linux, 2026-11-25)

With a stand-in for Neutralino that prints what it gets, in a layout with the same space in its path: the stand-in runs
with the **pid the launcher was started with**, two starts in a row; the core's command names `…/run/composes/node`, which
links to the bundled node; `ext/core.mjs` is in the run folder; the window's environment has `CLAUDIA_WEB_DIR`,
`CLAUDIA_SERVER_PYTHON` and node's folder first in `PATH`; `window.sh` quotes values with quotes, `$`, backticks and line
breaks correctly. **Not checked: anything of macOS** (Dock, LaunchServices, Gatekeeper, `pkgbuild`, `codesign`, WKWebView).

## What you do, on the Mac

From the checkout, on branch `mac-installer`:

1. `sh spikes/e8-5-mac-launcher/build-spike-pkg.sh`, which builds `build/spike-mac-launcher/claudia-composes-spike.pkg`
   (a few minutes: it builds the web app and the client and downloads Node).
2. **Close every claudia window** (also those of `start-mac-client.sh`), then open the `.pkg` from Finder by
   double-click, so it is treated like a download would be. If macOS refuses it, use System Settings ▸ Privacy & Security
   ▸ "Open Anyway". Install it.
3. Open **claudia composes** from Applications (Finder or Launchpad), and leave it open.
4. `sh spikes/e8-5-mac-launcher/check-spike.sh open`
5. Quit it with Cmd+Q, wait half a minute, then `sh spikes/e8-5-mac-launcher/check-spike.sh quit`
6. `sh spikes/e8-5-mac-launcher/uninstall-spike.sh` (asks for your password).

Paste both outputs of `check-spike.sh` into the chat, with your answers:

| # | Look at | Hoped for |
|---|---|---|
| 1 | Did the `.pkg` need "Open Anyway"? Did the app then open without any warning? | the package yes, the app no |
| 2 | How many Dock icons while it starts and once the window shows? | one, from the first moment |
| 3 | The name in the menu bar next to the Apple logo, in Cmd+Tab, and in the Dock's tooltip | "claudia composes" |
| 4 | The icon in the Dock and in Cmd+Tab | composes' glyph, not a generic one |
| 5 | Does the window show the start page and open a document? | yes |
| 6 | After Cmd+Q: does the Dock icon go away at once? | yes, and `check-spike.sh quit` lists no process of the window or core |

## Result (2026-11-25, the owner's Mac: Apple Silicon, macOS 27.2.1): **yes**

* **One app:** macOS registered one "claudia composes" (`de.claudiaoffice.composes`) whose executable is
  `Contents/MacOS/neutralino`, with `originalExecutablePath` the launcher script and `originalPid` its own pid (25414):
  both `exec`s kept the launched process. One Dock icon from the first moment, composes' glyph, "claudia composes" in the
  menu bar and in Cmd+Tab (seen by the owner). WebKit's helpers ("claudia composes Networking" and two more) are listed
  too, as for any app with a web view; they have no Dock icon.
* **Unsigned works:** no quarantine attribute on the installed files; the ad-hoc signatures are valid and the bundle
  satisfies its designated requirement; the app opened without any warning.
* **The chain runs:** window → core (through the `node` link in `~/Library/Caches/Claudia/run/composes`) → server; the
  page started, showed its servers, and opened a document (seen by the owner). Neutralino's log stayed empty (no errors).
* **Quitting:** Cmd+Q ended the window and the core at once and the Dock icon went away; only the server was left, which
  stops by itself ten minutes after its last window (D445), as `macos-installer.feature` expects.
* **Not shown:** the package did not need "Open Anyway", but it was built on the same Mac and so had no quarantine
  attribute; a package downloaded from a release will have one. To check in the install test with a downloaded copy.

So part 3 of `notes/e8-5-architecture.md` stays as designed; the fallbacks below were not needed.

## If the answer is no

The fallback I would try next, in this order: (a) the bundle's executable is a tiny compiled program instead of a shell
script (the Windows launcher is one already, D750); (b) Neutralino is the bundle's executable and the preparation moves
into a separate step the launcher cannot skip. Each changes only part 3 of the design.
