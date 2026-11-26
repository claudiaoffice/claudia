# The macOS package

`claudia-office-<version>-macos-arm64.pkg`: claudia composes, computes and creates for every person of a Mac with
Apple Silicon and macOS 14 or newer, "uninstall claudia", and, chosen under "Customize", the claudia service, a place
for the people of the Mac to share documents ("Shared on this computer"). Unsigned. Decisions D1625–D1629; the design
is `claudiaoffice-log/notes/e8-5-architecture.md`, part 3.

## Built on Linux

GitHub's macOS runners do not come for this repository, so nothing of the build needs a Mac. `.github/workflows/macos.yml`
builds the package on Ubuntu for pull requests, `main` and by hand (a workflow artifact, 30 days), and attaches it to the
GitHub release of a tag `vX.Y.Z`. To build it yourself on Linux (or a Mac), with Node 22, uv and `make`:

```sh
(cd web && npm ci && npm run build)
(cd clients/neutralino && npm ci && npm run build:macos && for a in composes computes creates; do (cd apps/$a && npx @neutralinojs/neu update); done)
B=packaging/macos/build.py
mkdir -p build/python build/node build/bomutils
uv run --no-project python $B fetch python build/python.tar.gz && tar -xzf build/python.tar.gz -C build/python --strip-components=1
uv run --no-project python $B fetch node build/node.tar.gz && tar -xzf build/node.tar.gz -C build/node --strip-components=1
uv run --no-project python $B fetch bomutils build/bomutils.tar.gz && tar -xzf build/bomutils.tar.gz -C build/bomutils --strip-components=1
make -C build/bomutils
uv run --no-project python $B server --python build/python
uv run --no-project --with pillow python $B stage --python build/python --node build/node --version 0.5.0 --out build/macos
uv run --no-project python $B check-signatures build/macos
uv run --no-project python $B package --stage build/macos --mkbom build/bomutils/build/bin/mkbom --version 0.5.0 --out dist
```

| file | what |
| --- | --- |
| `build.py` | the version, the pinned downloads, the server into the runtime's Python, the stage, the signature check, the package |
| `flatpkg.py` | the formats of a flat package: payload and scripts (cpio, gzipped), PackageInfo, the xar archive |
| `macho.py` | which files are Mach-O, and whether each carries a code signature |
| `third-party.json` | CPython and Node for macOS on Apple Silicon, bomutils: pinned by SHA-256 |
| `scripts/apps/`, `scripts/service/` | the parts' preinstall and postinstall |
| `uninstall.sh`, `uninstall-app.sh` | the uninstaller, and the program of "uninstall claudia.app" |
| `resources/` | the installer's welcome page and words, English and German (the licence page is made from `LICENSE`) |
| `test-install.sh` | the install test, on a Mac |

The tests that need no Mac: `tests/test_macos_packaging.py`, `test_macos_flatpkg.py`, `test_macos_macho.py`,
`test_macos_scripts.py`.

## Pins

A download is refused unless its SHA-256 is the one in `third-party.json`, and the refusal says which it found. Before
it downloads, CI checks each pin against its publisher's own list (`checksums`: python-build-standalone's `SHA256SUMS`,
Node's `SHASUMS256.txt`; `build.py check-pins`). To move to a newer CPython or Node: change `version`, `url` and
`checksums`, let CI download it once, and put the SHA-256 it prints in; the next run checks it against the list.
bomutils publishes no list (its file is GitHub's archive of the tag): its pin is the first download's.

## Signatures

Apple Silicon runs no code without a signature; an ad-hoc one is enough, and CPython, Node, Neutralino and the wheels'
libraries carry one, since they were built on a Mac. The build changes none of them and signs none: `check-signatures`
refuses a stage with a Mach-O file that has none. Should a download ever lack one, sign it ad-hoc with
[`rcodesign`](https://github.com/indygreg/apple-platform-rs) (`rcodesign sign FILE`), which runs on Linux.

## Installing it, and the install test

A downloaded unsigned package is opened with "Open Anyway" in System Settings ▸ Privacy & Security. CI cannot install
it. On a Mac, from a checkout:

```sh
sudo packaging/macos/test-install.sh ~/Downloads/claudia-office-0.5.0-macos-arm64.pkg
```

It installs without and with the service, updates over itself and uninstalls, and checks each step (it ends with
`PASS` and leaves claudia removed). Then open claudia composes from Applications once: its window, one Dock icon.

## On the Mac

| where | what |
| --- | --- |
| `/Applications/claudia <app>.app` | the app: a launcher script and the Neutralino window (D1626) |
| `/Applications/Utilities/uninstall claudia.app` | asks for an administrator, removes claudia, leaves documents and settings (D1628) |
| `/Library/Application Support/Claudia/runtime` | Node, Python with the server, the client, the web frontend |
| `/Library/Application Support/Claudia/shared`, `/Library/LaunchDaemons/de.claudia-office.server.plist`, `…/Claudia/service.json` | the service, only when chosen (D1627) |
| `~/Library/Application Support/Claudia` | each person's documents and settings ("Private on this computer") |
| `~/Library/Caches/Claudia/run/<app>`, `~/Library/Logs/Claudia/<app>.log` | where her window runs from, what its start printed |
