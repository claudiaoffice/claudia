"""Loading a catalogue entry's ``spec.py`` (D218).

Every entry's spec file is named ``spec.py`` -- that is the point of the catalogue (the directory layout is for
people browsing the library, not for Python's import system) -- so a plain ``import spec`` would have every
entry silently reuse whichever one loaded first via :data:`sys.modules`'s cache. Loading each by its own path
with a name derived from the catalogue id avoids that; nothing here needs the module to be reachable by that
name again afterwards, registering it in ``sys.modules`` is only the usual courtesy for code a loaded module
might expect (a dataclass's own introspection, for instance).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .case import Case


def load_case(spec_path: Path, entry_id: str) -> Case:
    """The ``CASE`` a catalogue entry's ``spec.py`` defines; ``ImportError`` if the file is missing or defines no
    ``CASE``, so a broken spec is reported as a loud error rather than a silently-skipped case."""
    if not spec_path.is_file():
        raise ImportError(f"no spec file at {spec_path}")
    module_name = f"claudia_test_documents._specs.{entry_id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, spec_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load a spec module from {spec_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    case = getattr(module, "CASE", None)
    if not isinstance(case, Case):
        raise ImportError(f"{spec_path} must define a module-level CASE = Case(...)")
    return case
