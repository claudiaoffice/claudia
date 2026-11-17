# PyInstaller recipe of claudia-server.exe, the server with its Python and its libraries inside (D740):
#
#   uv run --no-dev --with pyinstaller==6.21.0 pyinstaller --noconfirm --distpath dist --workpath build packaging/windows/claudia-server.spec
#
# One folder (dist/claudia-server/), not one file: a one-file program unpacks itself into a temporary folder at every
# start, which takes seconds, and a virus scanner reads all of it every time. The folder is what the installer copies.
#
# What PyInstaller cannot see by itself is taken in whole: every package of the workspace (packages/*/src/*) with its
# modules and its data (help topics, fonts, catalogs, shapes), because the apps and their converters are found by name
# when the server starts, not by an import it could follow. The libraries that load their parts the same way are
# named below. If a start of the built program says "No module named ...", the name belongs in LOADED_BY_NAME.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parents[1]  # noqa: F821  (SPECPATH is set by PyInstaller)

#: Libraries that import their own parts by name (servers, protocols, loops), so the import graph does not show them.
LOADED_BY_NAME = ["uvicorn", "websockets", "fastapi", "starlette", "cryptography"]

workspace = sorted(p.name for src in root.glob("packages/*/src/*") if (p := src).is_dir() and not p.name.startswith("_"))

datas, binaries, hiddenimports = [], [], []
for name in [*workspace, *LOADED_BY_NAME]:
    package_datas, package_binaries, package_hidden = collect_all(name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

analysis = Analysis(  # noqa: F821
    [str(root / "packaging" / "windows" / "server_entry.py")],
    pathex=[str(src) for src in root.glob("packages/*/src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "sphinx", "playwright", "mypy"],  # nothing of the server's work; tkinter is the Tk the server has no use for
    noarchive=False,
)
pyz = PYZ(analysis.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="claudia-server",
    console=True,  # a console program: its output goes to the log file of whoever starts it, and no window opens for it
    icon=None,
)
coll = COLLECT(exe, analysis.binaries, analysis.datas, name="claudia-server")  # noqa: F821
