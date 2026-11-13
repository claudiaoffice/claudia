"""Hyphenation patterns for clients: the languages as data and the files by hash, and fetching them (D913)."""

import hashlib
import json

import pytest
from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_server import hyphenation
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.cli import UsageError, make_plan
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.hyphenation import FetchError, HyphenationService, Language, PatternFile, fetch, read_lock

PATTERNS = b"1ba 1be 1bi\n"
EXCEPTIONS = b"ta-ble\n"


def entry(name: str, data: bytes) -> dict:
    return {
        "name": name,
        "url": f"https://example.org/{name}",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def lock_text(**change) -> str:
    language = {
        "tag": "xx",
        "aliases": ["xx-YY"],
        "name": "Test",
        "licence": "MIT",
        "patterns": entry("hyph-xx.pat.txt", PATTERNS),
        "exceptions": entry("hyph-xx.hyp.txt", EXCEPTIONS),
    } | change
    return json.dumps({"format": 1, "languages": [language]})


def store() -> dict[str, bytes]:
    return {"https://example.org/hyph-xx.pat.txt": PATTERNS, "https://example.org/hyph-xx.hyp.txt": EXCEPTIONS}


def test_the_packaged_lock_pins_german_and_english_at_a_fixed_commit():
    languages = {language.tag: language for language in read_lock()}
    assert set(languages) == {"de", "en-GB", "en-US"}
    assert languages["en-US"].aliases == ("en",)
    for language in languages.values():
        for f in language.files():
            assert f.url.startswith("https://raw.githubusercontent.com/hyphenation/tex-hyphen/")
            assert len(f.sha256) == 64
    assert languages["de"].exceptions is None


def test_fetch_then_serve_the_listing_and_the_files(tmp_path):
    languages = read_lock(lock_text())
    fetch(tmp_path / "h", languages, download=store().__getitem__)
    service = HyphenationService.from_folder(tmp_path / "h", languages)
    assert service.summary() == "hyphenation: xx (/api/hyphenation)"
    c = TestClient(create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(), hyphenation=service))
    data = c.get("/api/hyphenation").json()
    assert data["format"] == 1
    assert data["languages"] == [
        {
            "tag": "xx",
            "aliases": ["xx-YY"],
            "name": "Test",
            "licence": "MIT",
            "patterns": {"sha256": hashlib.sha256(PATTERNS).hexdigest(), "size": len(PATTERNS)},
            "exceptions": {"sha256": hashlib.sha256(EXCEPTIONS).hexdigest(), "size": len(EXCEPTIONS)},
        }
    ]
    answer = c.get(f"/api/hyphenation/{hashlib.sha256(PATTERNS).hexdigest()}")
    assert answer.status_code == 200 and answer.content == PATTERNS
    assert answer.headers["content-type"].startswith("text/plain")
    assert "immutable" in answer.headers["cache-control"]
    assert c.get(f"/api/hyphenation/{'0' * 64}").status_code == 404
    assert c.get("/api/hyphenation/..%2Fsecret").status_code == 404


def test_a_language_whose_files_are_missing_or_changed_is_left_out(tmp_path):
    languages = read_lock(lock_text())
    service = HyphenationService.from_folder(tmp_path / "nothing", languages)
    assert service.languages == () and service.problems == ("xx: hyph-xx.pat.txt is missing",)
    assert service.summary().startswith("no hyphenation patterns")
    fetch(tmp_path / "h", languages, download=store().__getitem__)
    (tmp_path / "h" / "hyph-xx.hyp.txt").write_bytes(b"changed")
    changed = HyphenationService.from_folder(tmp_path / "h", languages)
    assert changed.languages == () and changed.problems == ("xx: hyph-xx.hyp.txt is not the pinned file",)


def test_fetch_keeps_good_files_and_refuses_other_bytes(tmp_path):
    languages = read_lock(lock_text())
    fetch(tmp_path / "h", languages, download=store().__getitem__)
    fetch(tmp_path / "h", languages, download=lambda url: pytest.fail("fetched again"))
    bad = store() | {"https://example.org/hyph-xx.pat.txt": b"other"}
    with pytest.raises(FetchError, match="SHA-256"):
        fetch(tmp_path / "other", languages, download=bad.__getitem__)

    def broken(url):
        raise OSError("no route")

    with pytest.raises(FetchError, match="example.org"):
        fetch(tmp_path / "third", languages, download=broken)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"patterns": {"name": "../x", "url": "https://e/x", "sha256": "0" * 64, "size": 1}}, "file name"),
        ({"patterns": {"name": "x", "url": "http://e/x", "sha256": "0" * 64, "size": 1}}, "https"),
        ({"patterns": {"name": "x", "url": "https://e/x", "sha256": "abc", "size": 1}}, "SHA-256"),
    ],
)
def test_a_lock_is_checked(change, message):
    with pytest.raises(ValueError, match=message):
        read_lock(lock_text(**change))
    with pytest.raises(ValueError, match="format"):
        read_lock(json.dumps({"format": 2, "languages": []}))


def test_a_language_without_exceptions_lists_none():
    language = Language("de", (), "German", "MIT", PatternFile("p", "https://e/p", "0" * 64, 1), None)
    assert language.to_data()["exceptions"] is None
    assert language.files() == [language.patterns]


def test_the_server_reads_the_state_folder_or_the_one_given(tmp_path):
    bare = make_plan(["--no-tls", "--state-dir", str(tmp_path / "s")])
    assert any(line.startswith("no hyphenation patterns") for line in bare.banner)
    with pytest.raises(UsageError, match="--hyphenation"):
        make_plan(["--no-tls", "--state-dir", str(tmp_path / "s"), "--hyphenation", str(tmp_path / "missing")])


def test_the_command_line_fetches_and_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(hyphenation, "read_lock", lambda text=None: read_lock(lock_text()))
    monkeypatch.setattr(hyphenation, "_download", store().__getitem__)
    assert hyphenation.main(["fetch", str(tmp_path / "h")]) == 0
    assert "2 pattern files" in capsys.readouterr().out
    monkeypatch.setattr(hyphenation, "_download", lambda url: b"wrong")
    assert hyphenation.main(["fetch", str(tmp_path / "other")]) == 1
    assert "SHA-256" in capsys.readouterr().err


class _Answer:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, limit):
        return self.data[:limit]


def test_the_default_download_reads_at_most_the_limit(monkeypatch):
    monkeypatch.setattr(hyphenation, "MAX_FILE_BYTES", 4)
    monkeypatch.setattr(hyphenation.urllib.request, "urlopen", lambda url, timeout: _Answer(b"abcd"))
    assert hyphenation._download("https://example.org/a") == b"abcd"
    monkeypatch.setattr(hyphenation.urllib.request, "urlopen", lambda url, timeout: _Answer(b"abcdefgh"))
    with pytest.raises(FetchError, match="larger"):
        hyphenation._download("https://example.org/a")


def test_a_write_that_fails_leaves_no_temporary_file(tmp_path, monkeypatch):
    def refuse(source, target):
        raise OSError("disk full")

    monkeypatch.setattr(hyphenation.os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        hyphenation._write(tmp_path / "a.txt", b"data")
    assert list(tmp_path.iterdir()) == []
