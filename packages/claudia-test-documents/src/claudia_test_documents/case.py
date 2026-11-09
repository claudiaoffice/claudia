"""What one catalogue entry's ``spec.py`` declares about its test case (D178).

A ``spec.py`` is loaded dynamically (:mod:`claudia_test_documents.loader`) and must define a module-level
``CASE = Case(...)``. Every field is optional because a case tests only what it is for: a "beyond claudia"
preservation case (a table, an image) has no ``import_checks`` at all -- claudia has nothing to assert about
content it does not model -- while a plain style-mapping case needs no ``preserve_parts``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

#: A case's checks run against whatever model object the format's adapter produces (a ``TextModel`` today; a
#: ``WorkbookModel``/``SlideModel`` once computes/creates get their own adapters) -- typed loosely here on
#: purpose, since this module knows nothing about any one format's model class.
Model = Any


@dataclass
class Case:
    """One test case's checks, loaded from its ``spec.py``.

    ``import_checks``: assertions about the model right after import (Tier 1). ``modify``: returns an edited copy
    of the imported model for the round-trip leg; omitted means "no edit" (the loop still runs, as a check that
    an untouched import survives re-export unchanged). ``after_checks``: assertions about the model after
    export-and-reimport; defaults to ``import_checks`` when omitted, since for most cases "what was true on
    import is still true after a no-op or unrelated edit" is exactly the right check. ``preserve_parts``: zip
    part names that must be byte-identical between the original file and the re-exported one (Tier 2, for
    content living in its own package part -- an image, a style sheet). ``preserve_elements``: a callable
    comparing the original and re-exported bytes directly, for content that is not its own part (a table sitting
    inside the same part claudia's own export rewrites) -- raises ``AssertionError`` on a mismatch, same as any
    other check here. ``export_checks``: a callable asserting something about the re-exported bytes themselves
    (part of the same round-trip stage as ``after_checks``, not ``preserve`` -- it is checking what the edit
    itself produced, not what should have been left alone) -- for a feature the model layer cannot see back out
    again, such as a tracked change: ``docx_to_text`` never reimports one (python-docx's own ``paragraph.text``
    already skips it), so the only way to confirm a suggestion was written as a real ``w:ins``/``w:del`` pair is
    to look at the exported XML directly, not at the reimported model. ``visual``: opts into the Tier 3
    rendered-appearance check when the runner is asked to run it (``--visual``); left ``False`` for every case
    so far, since none of them has a property that is only checkable by looking at it (see the implementation
    note).
    """

    import_checks: Callable[[Model], None] | None = None
    modify: Callable[[Model], Model] | None = None
    after_checks: Callable[[Model], None] | None = None
    export_checks: Callable[[bytes], None] | None = None
    preserve_parts: list[str] = field(default_factory=list)
    preserve_elements: Callable[[bytes, bytes], None] | None = None
    visual: bool = False
