"""The documentation names the protocol version the code has (found 2026-11-19: the page said 1, the code 2)."""

import re
from pathlib import Path

from claudia_server.protocol import PROTOCOL_VERSION

VERSIONING = Path(__file__).resolve().parent.parent / "docs" / "versioning.md"


def test_the_versioning_page_names_the_current_protocol_version():
    named = re.findall(r"`PROTOCOL_VERSION` \(now (\d+)\)", VERSIONING.read_text(encoding="utf-8"))
    assert named == [str(PROTOCOL_VERSION)]
