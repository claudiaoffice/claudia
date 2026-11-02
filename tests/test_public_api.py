"""The public API is a promise (docs/versioning.md): it changes on purpose, with a version and a CHANGELOG entry.

If this test fails you changed the public API of a package: names in ``__all__``, or signatures of what they expose.
Decide whether that was intended; if so

1. raise ``__version__`` in the package's ``_version.py`` (patch: no API change; minor: additions; breaking: see
   docs/versioning.md),
2. describe the change in the package's CHANGELOG.md,
3. run ``uv run python scripts/api_surface.py --write`` and commit the new snapshots with the change.
"""

import importlib
import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHANGELOGS = {
    "claudia_core": ROOT / "CHANGELOG.md",
    "claudia_server": ROOT / "packages" / "claudia-server" / "CHANGELOG.md",
    "claudia_client": ROOT / "packages" / "claudia-client" / "CHANGELOG.md",
    "claudia_container": ROOT / "packages" / "claudia-container" / "CHANGELOG.md",
}


def load_script():
    spec = importlib.util.spec_from_file_location("api_surface", ROOT / "scripts" / "api_surface.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = load_script()
packages = pytest.mark.parametrize("name", SCRIPT.PACKAGES)


@packages
def test_the_api_matches_the_snapshot(name):
    now = SCRIPT.surface(importlib.import_module(name))
    then = json.loads(SCRIPT.snapshot_path(name).read_text())
    assert now == then, "the public API changed: see the docstring of this module for what to do"


@packages
def test_the_version_is_in_the_changelog(name):
    version = importlib.import_module(name).__version__
    assert f"## [{version}]" in CHANGELOGS[name].read_text(), f"describe this version in {CHANGELOGS[name].name}"


@packages
def test_the_version_looks_like_one(name):
    assert re.fullmatch(r"\d+\.\d+\.\d+", importlib.import_module(name).__version__)


@packages
def test_all_lists_only_things_that_exist_and_nothing_twice(name):
    module = importlib.import_module(name)
    assert len(set(module.__all__)) == len(module.__all__)
    for item in module.__all__:
        assert hasattr(module, item), item


def public_objects():
    for package in SCRIPT.PACKAGES:
        module = importlib.import_module(package)
        for item in module.__all__:
            obj = getattr(module, item)
            if inspect.isclass(obj) or inspect.isfunction(obj):
                yield f"{package}.{item}", obj


@pytest.mark.parametrize(("name", "obj"), list(public_objects()), ids=lambda v: v if isinstance(v, str) else "")
def test_every_public_class_and_function_is_documented(name, obj):
    assert (obj.__doc__ or "").strip(), f"{name} has no docstring (the API documentation is generated from it)"


def public_methods():
    for name, obj in public_objects():
        if not inspect.isclass(obj) or issubclass(obj, BaseException):
            continue
        for member, value in vars(obj).items():
            member_kinds = property | classmethod | staticmethod
            if member.startswith("_") or not (callable(value) or isinstance(value, member_kinds)):
                continue
            yield f"{name}.{member}", getattr(obj, member)


def test_public_methods_are_documented():
    """A method that overrides a documented one inherits its description (Sphinx does the same)."""
    missing = sorted(key for key, member in public_methods() if not inspect.getdoc(member))
    assert not missing, f"no docstring (the API reference is generated from them): {missing}"
