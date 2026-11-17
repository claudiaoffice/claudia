"""Files fetched by URL and checked against a lock (CODE-34, D701)."""

import hashlib
import sys

import pytest

from claudia_file_writer import FetchError, PinnedFile, download, fetch_pinned


def pinned(name, data, url=None):
    return PinnedFile(name, url or f"https://example.org/{name}", hashlib.sha256(data).hexdigest(), len(data))


def test_a_lock_entry_becomes_a_pinned_file():
    entry = {"name": "Inter[opsz,wght].ttf", "url": "https://example.org/a", "sha256": "AB" * 32, "size": "3"}
    assert PinnedFile.from_lock(entry) == PinnedFile("Inter[opsz,wght].ttf", "https://example.org/a", "ab" * 32, 3)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"name": "../a"}, "bad file name"),
        ({"name": "a/b"}, "bad file name"),
        ({"name": "a\\b"}, "bad file name"),
        ({"name": ".hidden"}, "bad file name"),
        ({"name": "c:a"}, "bad file name"),
        ({"name": ""}, "bad file name"),
        ({"url": "http://example.org/a"}, "https"),
        ({"sha256": "0" * 63}, "SHA-256"),
    ],
)
def test_a_lock_entry_that_could_leave_its_folder_or_be_fetched_unsafely_is_refused(change, message):
    entry = {"name": "a.txt", "url": "https://example.org/a", "sha256": "0" * 64, "size": 1} | change
    with pytest.raises(ValueError, match=message):
        PinnedFile.from_lock(entry)


def test_fetching_writes_what_is_missing_and_keeps_what_is_right(tmp_path):
    files = [pinned("a.txt", b"aaa"), pinned("b.txt", b"bbb")]
    store = {f.url: f.name[0].encode() * 3 for f in files}
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "a.txt").write_bytes(b"aaa")
    said = []
    paths = fetch_pinned(files, tmp_path / "f", download=store.__getitem__, report=said.append, label="test files")
    assert paths == [tmp_path / "f" / "a.txt", tmp_path / "f" / "b.txt"]
    assert (tmp_path / "f" / "b.txt").read_bytes() == b"bbb"
    assert said == ["fetching test files: b.txt"]


def test_a_file_with_other_bytes_than_the_lock_says_is_refused_and_not_written(tmp_path):
    files = [pinned("a.txt", b"aaa")]
    with pytest.raises(FetchError, match="a.txt: SHA-256"):
        fetch_pinned(files, tmp_path, download=lambda url: b"evil")
    assert not (tmp_path / "a.txt").exists()


def test_a_file_with_wrong_bytes_on_disk_is_fetched_again(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"old")
    fetch_pinned([pinned("a.txt", b"aaa")], tmp_path, download=lambda url: b"aaa")
    assert (tmp_path / "a.txt").read_bytes() == b"aaa"


def test_a_download_that_fails_is_named(tmp_path):
    def offline(url):
        raise OSError("no network")

    with pytest.raises(FetchError, match=r"https://example.org/a.txt: no network"):
        fetch_pinned([pinned("a.txt", b"aaa")], tmp_path, download=offline)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_a_fetched_file_can_be_read_by_other_users(tmp_path):
    """The Docker image fetches as root and the server runs as another user."""
    fetch_pinned([pinned("a.txt", b"aaa")], tmp_path, download=lambda url: b"aaa")
    assert (tmp_path / "a.txt").stat().st_mode & 0o777 == 0o644


class _Answer:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, limit):
        return self.data[:limit]


def test_the_download_reads_at_most_the_limit(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout: _Answer(b"abcd"))
    assert download("https://example.org/a", max_bytes=4) == b"abcd"
    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout: _Answer(b"abcdefgh"))
    with pytest.raises(FetchError, match="larger than 4 bytes"):
        download("https://example.org/a", max_bytes=4)


def test_the_download_refuses_anything_but_https():
    with pytest.raises(FetchError, match="https"):
        download("file:///etc/passwd", max_bytes=4)
