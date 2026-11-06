"""Housekeeping the gate checks for directly, because each failure mode was found by accident once already.

A ``.rej`` or ``.orig`` file is a rejected patch or a backup left by a merge tool; it does not belong in history, and
a stray one can hide a change that never landed the way ``uv.lock.rej`` did (CODE-07).
"""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_no_rej_or_orig_files_are_tracked():
    result = subprocess.run(
        ["git", "ls-files", "*.rej", "*.orig"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    tracked = [line for line in result.stdout.splitlines() if line]
    assert not tracked, f"rejected-patch or backup files are tracked and must not be: {tracked}"
