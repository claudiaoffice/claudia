"""Open OpenDocument output in LibreOffice, the reference implementation, and check what it reads (D409).

``uv run python scripts/odf_libreoffice_check.py``

What the unit tests prove is that the files follow the rules this code knows. This asks a program that is not this
code. For every enabled odt entry of the test-document library it makes the edit the entry's ``spec.py`` makes,
and for a model with every style and a suggestion it makes a new file; then it has ``soffice --headless`` convert the
source, the edited file and the new file to plain text, and checks that

* ``soffice`` accepts the file (exit code 0, a text file comes out), and
* every word of every block of the edited model is in the text LibreOffice read, in order. (Words, not the exact
  text: LibreOffice prints a footnote's number inside the sentence and a tracked deletion and its insertion run
  together, and writes a tab or a break as it likes.)

It exits 0 where there is no ``soffice`` (saying so: a skip is never reported as a pass) and 1 if any check failed. The
CI job that runs it is allowed to fail at first (D409); a run on a laptop with LibreOffice installed is the check.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "test-documents"
TIMEOUT = 180


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def as_text(program: str, data: bytes, work: Path) -> str:
    """What LibreOffice reads of the odt ``data``, as plain text."""
    source = work / "in.odt"
    source.write_bytes(data)
    out = work / "out"
    out.mkdir(exist_ok=True)
    profile = work / "profile"  # a profile of its own, so no run waits for another's lock
    command = [
        program,
        f"-env:UserInstallation=file://{profile}",
        "--headless",
        "--convert-to",
        "txt:Text",
        "--outdir",
        str(out),
        str(source),
    ]
    done = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT, check=False)
    produced = out / "in.txt"
    if done.returncode != 0 or not produced.exists():
        raise RuntimeError(f"soffice could not read the file (exit {done.returncode}): {done.stderr.strip()[:300]}")
    return produced.read_text(encoding="utf-8-sig")


def shows(read: str, expected: str) -> bool:
    """Whether every word of ``expected`` is in ``read``, in order (see the module description)."""
    position = 0
    for word in re.findall(r"\w+", expected):
        found = read.find(word, position)
        if found < 0:
            return False
        position = found + len(word)
    return True


def library_cases() -> list[tuple[str, bytes, bytes, list[str]]]:
    """``(name, source, edited, texts the edited file must show)`` for each enabled odt entry."""
    from claudia_test_documents import load_catalogue
    from claudia_test_documents.adapters import ADAPTERS
    from claudia_test_documents.loader import load_case

    adapter = ADAPTERS["odt"]
    assert adapter.apply_edits_fn is not None
    found = []
    for entry in load_catalogue(LIBRARY / "catalogue.json"):
        if entry["format"] != "odt" or not entry.get("enabled", True):
            continue
        source = (LIBRARY / entry["source"]).read_bytes()
        case = load_case(LIBRARY / entry["spec"], entry["id"])
        baseline, working = adapter.import_fn(source), adapter.import_fn(source)
        current = case.modify(working) if case.modify is not None else working
        edited = adapter.apply_edits_fn(source, baseline, current)
        shown = [block.text for block in adapter.import_fn(edited).blocks if block.text.strip()]
        found.append((entry["id"], source, edited, shown))
    return found


def new_file() -> tuple[bytes, list[str]]:
    """A file made from a model: every style, white space, a suggestion."""
    from claudia_composes_io import odt_to_text, text_to_odt

    from claudia_composes import Block, Suggestion, TextModel, TextRange

    model = TextModel(
        [
            Block("b1", "title", "Annual report"),
            Block("b2", "heading-1", "Summary"),
            Block("b3", "heading-2", "Details"),
            Block("b4", "body", "The committee rejected the proposal.  Two  spaces\tand a tab\nand a break."),
            Block("b5", "quote", "Words of someone else"),
        ]
    )
    model.suggestions["s1"] = Suggestion("s1", "Claudia AI", TextRange("b4", 14, 22), "rejected", "approved", "tone")
    data = text_to_odt(model)
    return data, [block.text for block in odt_to_text(data).blocks]


def main() -> int:
    program = soffice()
    if program is None:
        print("skipped: soffice (LibreOffice) is not installed; nothing was checked")
        return 0
    library = library_cases()
    cases = [(name, edited, shown) for name, _, edited, shown in library]
    cases += [(f"{name} (source)", source, []) for name, source, _, _ in library]
    data, shown = new_file()
    cases.append(("new file from a model", data, shown))
    failed = 0
    with tempfile.TemporaryDirectory() as directory:
        for name, data, texts in cases:
            work = Path(directory) / re.sub(r"\W+", "-", name)
            work.mkdir()
            try:
                text = as_text(program, data, work)
                missing = [t for t in texts if not shows(text, t)]
                if missing:
                    raise RuntimeError(f"LibreOffice does not show: {missing}")
            except (RuntimeError, subprocess.TimeoutExpired) as problem:
                failed += 1
                print(f"FAIL  {name}: {problem}")
            else:
                print(f"ok    {name}")
    print(f"{len(cases) - failed} of {len(cases)} read by LibreOffice" + ("" if not failed else f", {failed} did not"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
