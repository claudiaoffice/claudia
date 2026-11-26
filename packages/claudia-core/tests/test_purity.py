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
TESTING_ONLY = {"gc", "sys"}  # the helpers for tests measure work: sys.monitoring counts it, gc is held off (PERF-14)
# "paragraph" was here until E10.17 (D181), when a paragraph stopped being a composes idea: a creates text box
# and the label inside a shape on a sheet carry the same entity, so the kernel is where it belongs. "slide" was here
# until E6.31 (D1470), when a slide stopped being only creates': computes has slides among its sheets, so the slide's
# frame, anchor and records are the kernel's. The rest stay — "sheet"/"cell"/"workbook" are computes', "formula" is
# computes' too, and the kernel knowing any of them would mean it had learned one app's shape.
APP_WORDS = ("sheet", "cell", "workbook", "formula")


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
                if name in TESTING_ONLY and path.name == "testing.py":
                    continue
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
        "base64",  # assets.py: an image's bytes, as plain text in the JSON state and wire protocol
        "collections",
        "contextlib",
        "dataclasses",
        "decimal",  # tables.py: a total of boxes of words is exact, not a float
        "datetime",
        "enum",
        "hashlib",  # assets.py: content-addressing an image by its sha256
        "json",  # shapes.py: a shape outline is one JSON object (parsing text, no I/O)
        "math",  # shapes.py: isfinite, refusing a shape coordinate that is nan or inf
        "re",
        "struct",  # assets.py: reading JPEG/BMP/GIF binary headers
        "time",
        "types",  # containers.py: an immutable view of a container's settings
        "typing",
        "unicodedata",  # pure tables, used to turn a style name into an id
        "zlib",  # raster.py: the empty PNG that stands in for an SVG nobody can draw
        "xml",  # assets.py: sanitizing an imported SVG with the standard library's own parser, no third party
    }
    for path, tree in modules().items():
        allowed = stdlib | TESTING_ONLY if path.name == "testing.py" else stdlib
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                assert node.module.split(".")[0] in allowed, f"{path.name}: {node.module}"
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in allowed, f"{path.name}: {a.name}"
