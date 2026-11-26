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
* **The Bom is made from the payload's list** (`mkbom -i`), everything owned by root:wheel, as the payload says;
  pkgbuild's "recommended" ownership gives the apps root:admin, which nothing here needs.
* **Each person's logs and settings stay** on uninstalling; the service's log (`/Library/Logs/Claudia`) goes.
* **The pins were taken from CI's first download** (this sandbox cannot reach GitHub's release downloads or nodejs.org)
  and are checked against the publishers' lists at every run (`check-pins`).

## What CI taught (draft PR #48, 2026-11-26)

The first runs went red until the package was right; each finding is fixed with a test:

* **The pins**: the first run downloaded each file and printed its SHA-256; `build.py check-pins` checks the CPython and
  Node pins against the publishers' own lists at every run. bomutils publishes none.
* **bomutils 0.2 on today's compilers**: `lsbom.cpp` does not build as C++17 (its `data` clashes with `std::data`;
  built as C++14), and `mkbom` copied a link name with `strcpy` into room without its NUL when there is no link, a
  one-byte heap overflow that Ubuntu's fortified build stops: `bomutils-mkbom.patch` copies exactly the name's length.
* **The suite's own packages** are folders, which `--only-binary :all:` refuses on a fresh runner (a local uv cache had
  hidden it): `uv build` makes their wheels first; everything else is still a macOS wheel.
* **Universal wheels** (lxml, fontTools, brotli) carry an unsigned Intel slice: what counts is the signed arm64 slice.
* **mkbom leaves out names that start with a dot** when it reads a folder (python-docx's `.rels`, fastapi's `.agents`):
  CI compared each Bom with its payload (`lsbom` against `build.py list-payload`) and found it. The Bom is made from the
  payload's own list (`flatpkg.bom_listing`, `mkbom -i`), with POSIX `cksum` checksums as bomutils computes them.

The green run (45840979179): the pins are the publishers', 59 programs and libraries each with a signed arm64 slice,
4925 paths in the apps' part and 7 in the service's, the same in each Bom and payload; the package is 100 MB.

## What the code review changed (2026-11-26)

* **The Mac's own folders keep their owners and modes**: `/Applications` is root:admin 0775 on every Mac, and the payload
  said root:wheel 0755 with `overwrite-permissions="true"`, which could have taken from administrators the right to put
  apps there. `flatpkg.MAC_FOLDERS` lists them as the Mac has them, PackageInfo says `overwrite-permissions="false"`,
  and CI compares each Bom with its payload by path, mode and owner.
* **An update closes the open apps** (their windows, cores and servers, of every person) before it removes the old
  runtime, as the Windows installer closes them; the welcome page says so.
* **As root, nothing is followed that the service or a person made**: the service's postinstall gives only the folders
  it makes to `_claudia`, never recursively (a hard link to a file of the system would be given too); the uninstaller
  leaves files with more than one link alone and does not remove `Caches` through a link a person made.
* **The uninstaller says when a step failed** ("claudia could not be removed completely. These steps failed: …"), and
  leaves the shared documents readable for the administrators (the server wrote them for itself alone).
* **The uninstaller app speaks English or German**, as the Mac's first language is, and says its own last words.
* **An app that cannot start says so** in an alert with the last lines of its log, instead of a bouncing icon.
* **The signature check fails closed**: a universal binary with a 32-bit slice, one with 64-bit offsets, or one cut
  short, is refused rather than taken for "not Mach-O".
* **The runtime's Python comes with its bytecode** (`--compile-bytecode`): the runtime is read-only, and every server
  start would compile every module again.
* `windowBinary` has no flag argument: the launcher takes an installed app's binary as it is. Pillow is pinned in CI as
  uv.lock has it. `packaging/shared.py` loads the pins of both builds; every public function has its docstring.
* `test-install.sh` opens windows in her login session, quits one and checks that no process stays, updates with the
  default choices (the service restarted by the apps' part) and with an app open, and uninstalls with an app open.
* Not changed: the install scripts name the label and folders themselves rather than being generated (shellcheck and
  the tests read them as they are); the install-test job stays written and off until there is a macOS runner.

## Assumptions (say if they are wrong)

* macOS Installer takes a package whose payload and xar archive were written by `flatpkg.py` and whose Bom by `mkbom`
  (as packages built on Linux by others are); the first install on the owner's Mac says so or not.
* CPython from python-build-standalone, Node's macOS build, Neutralino's and the wheels' libraries carry a signature
  (`check-signatures` tells in CI; `rcodesign` would sign one that does not).
* Installer looks up the parts' titles and the refusal in `Localizable.strings` of `Resources/<language>.lproj`.

## What could not be run here

* Installing the package, opening an app, the Dock icon, the service under launchd, the ACL, uninstalling on a Mac: only
  a Mac (`test-install.sh`). The scripts ran under a temporary volume with stand-ins for `launchctl`, `dscl`, `pkill`,
  `pkgutil`, `chown`, `chmod +a`.
* The real downloads and `mkbom` (GitHub's release downloads and nodejs.org are closed to this sandbox): CI.
