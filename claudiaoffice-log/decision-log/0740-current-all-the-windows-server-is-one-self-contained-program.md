---
id: D740
title: "On Windows the server is one self-contained program"
status: current
applies-to: all
date: 2026-11-17
round: "The Windows installer (E8.1; branch `win-installer`)"
supersedes: []
superseded-by: []
---

# D740 · On Windows the server is one self-contained program

**The installer ships the server as `claudia-server.exe` with its Python 3.14 and its libraries inside**, built by
PyInstaller from `packaging/windows/claudia-server.spec` as a folder (`onedir`: a one-file program unpacks itself at
every start, and a virus scanner reads all of it every time). Nobody installs Python (D16: the interpreter is always
bundled). The spec takes every package of the workspace by name and with its data (help topics, fonts, catalogs, shapes)
because the apps and their converters are found by name, not by an import PyInstaller could follow.

`claudia-server.exe` takes the options of `python -m claudia_server` unchanged. Its start (`packaging/windows/server_entry.py`)
first answers the workers of the server's own process pool (`multiprocessing.freeze_support`), which on Windows are the
same program started again.

The desktop client starts it when `CLAUDIA_SERVER_EXE` is set (`findServerProgram`; it wins over `CLAUDIA_SERVER_PYTHON`);
the packaged client sets it itself (D741).

**Notes.** What was shown: the same spec built on Linux (127 MB) starts, answers `/api/health` and opens a document in each
app with the help topics found (`packaging/smoke_server.py`). What was not: the Windows build itself; CI builds and tests it
(D742). Nuitka was not tried; PyInstaller 6.21 supports Python 3.14. A new package of the workspace needs nothing in the spec;
a library that loads its own parts by name goes into `LOADED_BY_NAME`. No AI runtime (OpenVINO, models) is in the program
(the owner, 2026-11-17: AI is out for now); the `openvino` extra is not collected.
