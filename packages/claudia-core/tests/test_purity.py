"""The kernel does no I/O and contains no app code (E1.1 acceptance)."""

import ast
from pathlib import Path

import claudia_core

SRC = Path(claudia_core.__file__).parent
FORBIDDEN_IMPORTS = {
    "os",
    "sys",
    "socket",
    "pathlib",
    "shutil",
    "subprocess",
    "sqlite3",
    "asyncio",
    "threading",
    "multiprocessing",
    "urllib",
    "http",
    "ssl",
    "io",
    "tempfile",
    "logging",
    "zipfile",
    "pickle",
    "random",
    "secrets",
    "uuid",
}
CLOCK_ONLY = {"time", "datetime"}  # only clock.py may read a clock
APP_WORDS = ("sheet", "cell", "workbook", "slide", "paragraph", "formula")


def modules():
    return {p: ast.parse(p.read_text()) for p in sorted(SRC.glob("*.py"))}


def test_no_io_imports_and_no_open():
    for path, tree in modules().items():
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                assert name not in FORBIDDEN_IMPORTS, f"{path.name} imports {name}"
                if name in CLOCK_ONLY:
                    assert path.name in ("clock.py", "testing.py"), f"{path.name} reads a clock"
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("open", "print", "input"), f"{path.name} calls {node.func.id}"


def test_no_spreadsheet_text_or_slide_identifiers():
    for path, tree in modules().items():
        if path.name == "testing.py":
            continue
        for node in ast.walk(tree):
            ident = next((v for a in ("name", "id", "attr", "arg") if (v := getattr(node, a, None))), None)
            if isinstance(ident, str):
                assert not any(w in ident.lower() for w in APP_WORDS), f"{path.name}: {ident}"


def test_kernel_has_no_third_party_imports():
    stdlib = {
        "__future__",
        "abc",
        "collections",
        "contextlib",
        "dataclasses",
        "datetime",
        "enum",
        "re",
        "time",
        "typing",
    }
    for path, tree in modules().items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                assert node.module.split(".")[0] in stdlib, f"{path.name}: {node.module}"
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in stdlib, f"{path.name}: {a.name}"
