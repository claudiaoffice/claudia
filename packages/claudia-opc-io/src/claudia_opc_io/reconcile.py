"""Reconcile two versions of the same OPC package: the original bytes an app wrote, and a "naive" rewrite a
format library just produced from it after one or more edits. ``reconcile`` keeps the naive rewrite's bytes for
parts the caller says claudia meant to touch (``owned``), and restores every other part's bytes from the
original -- because a library's ``save()`` is a whole-package operation (D217; see
claudiaoffice-log/decision-log/): nothing here can assume it leaves alone what it did not need to change, the
same way openpyxl's own save() silently dropped a pivot table it never touched.

This first version reconciles whole parts only. A part that is itself a shared, indexed table referenced from
both owned and unowned content (xlsx's ``sharedStrings.xml``/``styles.xml``, for instance) needs a real
per-entry merge, not a whole-part choice between "keep" and "restore" -- deliberately not built yet. composes'
docx story does not need it (``word/document.xml`` is the only part it owns); computes' xlsx story will."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .package import read_parts, write_parts

OwnedTest = Callable[[str], bool]


def owns(part_names: Iterable[str]) -> OwnedTest:
    """An ``owned`` test that matches exactly these part names."""
    names = frozenset(part_names)
    return names.__contains__


def reconcile(original_bytes: bytes, regenerated_bytes: bytes, owned: OwnedTest) -> bytes:
    """``regenerated_bytes`` with every part ``owned`` says claudia did not mean to touch restored to its
    ``original_bytes`` version. A part that exists only in ``regenerated_bytes`` (the library added something
    that was never in the original) is kept as is: there is nothing to restore it from, and dropping it would
    leave a broken package."""
    original = read_parts(original_bytes)
    regenerated = read_parts(regenerated_bytes)
    final: dict[str, bytes] = {}
    for name, data in original.items():
        final[name] = regenerated.get(name, data) if owned(name) else data
    for name, data in regenerated.items():
        if name not in final:
            final[name] = data
    return write_parts(final)
