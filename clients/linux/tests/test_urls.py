"""What the web view may navigate to, and what it may write to disk.

The page is the shell's own frontend served by the local server, but it renders text that other people wrote. It must
not be possible to leave it by a link, to open a window of another site, or to write a file outside the downloads
folder with a name that the document chose.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from claudia_shell_gtk import urls

ORIGIN = "http://127.0.0.1:41233"


@pytest.mark.parametrize(
    "uri",
    [
        "http://127.0.0.1:41233/",
        "http://127.0.0.1:41233/api/docs",
        "http://127.0.0.1:41233/?doc=notes",
        "about:blank",
        f"blob:{ORIGIN}/6d3c1f5e-8c0e-4d33-9b6a-6e3a5c1d2f10",
    ],
)
def test_the_page_may_stay_on_its_own_server(uri: str) -> None:
    assert urls.is_internal(uri, ORIGIN)


@pytest.mark.parametrize(
    "uri",
    [
        "http://127.0.0.1:9999/",  # another port is another server
        "http://localhost:41233/",  # another name is another origin
        "http://127.0.0.1:41233.evil.example/",
        "http://127.0.0.1:41233@evil.example/",
        "https://example.org/",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,<script>1</script>",
        "blob:https://evil.example/6d3c1f5e",
        "",
    ],
)
def test_everything_else_is_not_the_page_itself(uri: str) -> None:
    assert not urls.is_internal(uri, ORIGIN)


@pytest.mark.parametrize("uri", ["http://example.org/x", "https://example.org/x", "mailto:ann@example.org"])
def test_ordinary_links_are_handed_to_the_default_application(uri: str) -> None:
    assert urls.external_target(uri) == uri


@pytest.mark.parametrize(
    "uri", ["file:///etc/passwd", "javascript:alert(1)", "data:text/plain,x", "smb://host/share", ""]
)
def test_dangerous_schemes_are_never_opened(uri: str) -> None:
    assert urls.external_target(uri) is None


@pytest.mark.parametrize(
    ("suggested", "expected"),
    [
        ("notes.md", "notes.md"),
        ("../../etc/passwd", "passwd"),
        ("/etc/cron.d/evil", "evil"),
        (".bashrc", "bashrc"),
        ("a\x00b\nc.md", "abc.md"),
        ("", "download"),
        ("...", "download"),
        ("dir/", "download"),
        ("x" * 400 + ".md", "x" * 197 + ".md"),  # 200 characters in all, the extension survives
    ],
)
def test_a_download_name_chosen_by_the_page_is_made_safe(suggested: str, expected: str) -> None:
    assert urls.safe_download_name(suggested) == expected


def test_an_existing_file_is_not_overwritten(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("mine")
    (tmp_path / "notes (1).md").write_text("mine too")
    assert urls.unique_path(tmp_path, "notes.md") == tmp_path / "notes (2).md"
    assert urls.unique_path(tmp_path, "fresh.md") == tmp_path / "fresh.md"
