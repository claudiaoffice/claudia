# E8.5, part 3: the macOS package (2026-11-26)

Branch `mac-installer`. Decisions D1625–D1629. The design is `notes/e8-5-architecture.md`, part 3, changed on
2026-11-26 by the owner's answers Q1–Q7: GitHub's macOS runners do not come, so the package is **built on Linux in CI**
and attached to each release like the Windows installer and the Debian package. The scenarios are
`specs/desktop/macos-installer.feature`; their tags name the tests.

## What was built

| Where | What |
|---|---|
| `clients/neutralino/src/launch.ts`, `cli.ts` | `--prepare`: stage the app into its run folder, link node, set the core's command, write `window.sh` (`windowScript`, `environmentChanges`, `shellQuote`), start nothing |
| `clients/neutralino/src/platform/{host,macos,windows}.ts` | `runFolder` (macOS `~/Library/Caches/Claudia/run/<app>`), `runFolderWithSpace`, `linkNodeIntoRun`, `windowBinary(…, packaged)` |
| `packaging/shared.py` | versions, pins, downloads, `require`: moved out of `packaging/windows/build.py`, which imports them |
| `packaging/macos/build.py` | `version`, `fetch`, `server` (the server's wheels for macOS into the runtime's Python), `stage`, `check-signatures`, `package` |
| `packaging/macos/flatpkg.py` | payload and scripts (odc cpio, gzipped, owned by root), PackageInfo, the xar archive |
| `packaging/macos/macho.py` | Mach-O files and whether each carries `LC_CODE_SIGNATURE` (thin and universal) |
| `packaging/macos/scripts/`, `uninstall.sh`, `uninstall-app.sh` | update (stop the service, remove the old runtime and apps, start it again), the service (account `_claudia`, shared folders, ACL for the administrators, start), uninstalling |
| `packaging/macos/resources/` | welcome page and the installer's words, English and German; the licence page is made from `LICENSE` |
| `packaging/macos/test-install.sh` | the install test on a Mac |
| `.github/workflows/macos.yml` | build on Ubuntu, read back with `bsdtar`, artifact 30 days, release on a tag; the Mac's install test switched off |
| `tests/test_macos_{packaging,flatpkg,macho,scripts}.py` | 100+ tests on any system |

## Deviations from the architecture note, and why

* **The server's state on a Mac** is `…/Claudia/shared/state`, as the note says; the service file names it.
* **`hostArchitectures="arm64,x86_64"`**, not only `arm64`: with `arm64` alone an Intel Mac gets the installer's own
  refusal, not ours ("claudia needs a Mac with Apple Silicon and macOS 14 or newer."). arm64 in the list keeps the
  installer from asking for Rosetta; our check refuses Intel and macOS before 14.
* **`--no-tls` is the last argument** of the LaunchDaemon, after the pairs (the order does not matter to the server).
* **The Bom is made from the folder** (`mkbom -u 0 -g 0 FOLDER`), all owned by root:wheel, as the payload says; pkgbuild's
  "recommended" ownership gives the apps root:admin, which nothing here needs.
* **Each person's logs and settings stay** on uninstalling; the service's log (`/Library/Logs/Claudia`) goes.
* **The pins are empty until CI's first download** (this sandbox cannot reach GitHub's release downloads or nodejs.org):
  `fetch` refuses the file and says its SHA-256; that number, compared with the publisher's list, becomes the pin.

## Assumptions (say if they are wrong)

* macOS Installer takes a package whose payload and xar archive were written by `flatpkg.py` and whose Bom by `mkbom`
  (as packages built on Linux by others are); the first install on the owner's Mac says so or not.
* CPython from python-build-standalone, Node's macOS build, Neutralino's and the wheels' libraries carry a signature
  (`check-signatures` tells in CI; `rcodesign` would sign one that does not).
* Installer looks up the parts' titles and the refusal in `Localizable.strings` of `Resources/<language>.lproj`.
* An update does not close open apps: their files are replaced under them (Windows closes them; the scenarios ask
  nothing).

## What could not be run here

* Installing the package, opening an app, the Dock icon, the service under launchd, the ACL, uninstalling on a Mac: only
  a Mac (`test-install.sh`). The scripts ran under a temporary volume with stand-ins for `launchctl`, `dscl`, `pkill`,
  `pkgutil`, `chown`, `chmod +a`.
* The real downloads and `mkbom` (GitHub's release downloads and nodejs.org are closed to this sandbox): CI.
