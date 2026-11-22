"""What several repository tests share."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture(scope="session")
def run_e2e() -> ModuleType:
    """``scripts/run_e2e.py``, the runner of the end-to-end tests, loaded as a module (it is a script)."""
    spec = importlib.util.spec_from_file_location("run_e2e", Path(__file__).parent.parent / "scripts" / "run_e2e.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look themselves up there
    spec.loader.exec_module(module)
    return module
