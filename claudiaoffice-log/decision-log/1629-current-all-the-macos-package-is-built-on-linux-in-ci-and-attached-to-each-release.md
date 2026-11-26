---
id: D1629
title: "The macOS package is built on Linux in CI and attached to each release; installing it is tested on the owner's Mac"
status: current
applies-to: all
date: 2026-11-26
round: "E8.5 macOS installer, part 3: the package (branch `mac-installer`); designed 2026-11-25, built on Linux in CI by the owner's answers of 2026-11-26"
supersedes: []
superseded-by: []
---

# D1629 · The macOS package is built on Linux in CI and attached to each release; installing it is tested on the owner's Mac

GitHub's hosted macOS runners do not come for this repository, so **nothing of the build needs a Mac**:
`.github/workflows/macos.yml` builds the package on Ubuntu for every pull request that touches it, every push to
`main` and by hand, keeps it 30 days, and on a tag `vX.Y.Z` attaches `claudia-office-X.Y.Z-macos-arm64.pkg` to the
GitHub release, next to the Windows installer and the Debian package. What needed a Mac has a Linux way (the owner's
answers Q1-Q7, 2026-11-26): the server is CPython plus wheels instead of PyInstaller (D1625); the payload (cpio) and
the archive (xar) are written in Python (`packaging/macos/flatpkg.py`) and the Bom by bomutils' `mkbom`, built from a
pinned source; icons by Pillow; the uninstaller is a script app (D1628). No binary is changed, so none is signed: the
build refuses one without a code signature (`packaging/macos/macho.py`). CI reads the finished package back with
libarchive's `bsdtar` and checks its parts, title, Boms and payload.

**What CI cannot do is install it.** `packaging/macos/test-install.sh` is the install test, on the owner's Mac or a
macOS virtual machine; its job in `macos.yml` is written and switched off until there is a macOS runner. The first
install of each change to the package is the owner's. The `macos-latest` entry of ci.yml's Python job stays off.

**Downloads are pinned by SHA-256** (`packaging/macos/third-party.json`, D742): CPython, Node, bomutils. A new pin is
taken from CI's own download, compared with the publisher's checksum list.

**Changes** D742 (testing by installing) for the Mac: tested by installing on the owner's Mac, not in CI.
