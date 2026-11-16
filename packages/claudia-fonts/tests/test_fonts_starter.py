"""The starter set: a pinned lock of open fonts, fetched and checked by SHA-256 (D93, D905)."""

import hashlib
import json
import sys

import pytest

from claudia_fonts import COLLECTION_FILE, Catalogue, FetchError, builtin_folder, collection_folders, fetch, read_lock
from claudia_fonts.__main__ import main
from claudia_fonts.starter import LockedCollection, LockedFile
from claudia_fonts.testing import make_font


def test_the_packaged_lock_pins_open_fonts_by_hash_at_a_fixed_commit():
    lock = read_lock()
    names = [c.name for c in lock]
    assert names == ["Inter", "Fraunces", "JetBrains Mono", "Carlito", "Caladea"]
    for collection in lock:
        assert collection.licence == "OFL-1.1" and collection.redistributable
        assert any(f.name == "OFL.txt" for f in collection.files)
        for f in collection.files:
            assert f.url.startswith("https://raw.githubusercontent.com/google/fonts/35e77c38")
            assert len(f.sha256) == 64


def test_the_package_ships_exactly_the_pinned_starter_set():
    """D500: every server has the starter set without the network. What ships is what the lock pins, byte for byte,
    with each collection's record, and nothing else."""
    root = builtin_folder()
    lock = read_lock()
    assert sorted(p.name for p in root.iterdir() if p.is_dir()) == sorted(c.folder for c in lock)
    for collection in lock:
        folder = root / collection.folder
        assert sorted(p.name for p in folder.iterdir()) == sorted(
            [f.name for f in collection.files] + [COLLECTION_FILE]
        )
        for f in collection.files:
            assert hashlib.sha256((folder / f.name).read_bytes()).hexdigest() == f.sha256, f.name
        record = json.loads((folder / COLLECTION_FILE).read_text())
        assert (record["name"], record["licence"], record["redistributable"]) == (collection.name, "OFL-1.1", True)


def test_the_shipped_starter_set_is_a_catalogue_with_the_fallback_family():
    catalogue = Catalogue.from_folders(collection_folders(builtin_folder()))
    assert catalogue.problems == ()
    assert {"Inter", "Fraunces", "JetBrains Mono", "Carlito", "Caladea"} <= set(catalogue.families())
    assert catalogue.resolve("Calibri").provided == "Carlito"


def lock_of(tmp_path, *, bad=False):
    font = make_font(tmp_path / "src.ttf").read_bytes()
    licence = b"SIL Open Font License"
    sha = hashlib.sha256(font).hexdigest()
    files = (
        LockedFile("Test-Regular.ttf", "https://example.org/t.ttf", "0" * 64 if bad else sha, len(font)),
        LockedFile("OFL.txt", "https://example.org/OFL.txt", hashlib.sha256(licence).hexdigest(), len(licence)),
    )
    store = {"https://example.org/t.ttf": font, "https://example.org/OFL.txt": licence}
    collection = LockedCollection("Test Sans", "testsans", "OFL-1.1", True, "https://example.org", "1", files)
    return [collection], store


def test_fetch_writes_each_collection_with_its_record_and_the_catalogue_reads_it(tmp_path):
    collections, store = lock_of(tmp_path)
    asked = []
    folders = fetch(tmp_path / "fonts", collections, download=lambda url: asked.append(url) or store[url])
    assert folders == [tmp_path / "fonts" / "testsans"]
    record = json.loads((folders[0] / COLLECTION_FILE).read_text())
    assert record["name"] == "Test Sans" and record["redistributable"] is True
    assert Catalogue.from_folders(collection_folders(tmp_path / "fonts")).families() == ("Test Sans",)
    # a second run fetches nothing: the files are there with the right bytes
    asked.clear()
    fetch(tmp_path / "fonts", collections, download=lambda url: asked.append(url) or store[url])
    assert asked == []


def test_fetch_refuses_bytes_that_are_not_the_pinned_ones(tmp_path):
    collections, store = lock_of(tmp_path, bad=True)
    with pytest.raises(FetchError, match="SHA-256"):
        fetch(tmp_path / "fonts", collections, download=store.__getitem__)
    assert not (tmp_path / "fonts" / "testsans" / "Test-Regular.ttf").exists()


def test_a_download_that_fails_is_named(tmp_path):
    collections, _ = lock_of(tmp_path)

    def broken(url):
        raise OSError("no route")

    with pytest.raises(FetchError, match="example.org/t.ttf"):
        fetch(tmp_path / "fonts", collections, download=broken)


@pytest.mark.parametrize(
    "change",
    [{"folder": "../up"}, {"folder": ".hidden"}],
)
def test_a_lock_cannot_write_outside_its_folder(change):
    data = {
        "format": 1,
        "collections": [{"name": "X", "folder": "x", "licence": "OFL-1.1", "redistributable": True, "files": []}],
    }
    data["collections"][0] |= change
    with pytest.raises(ValueError, match="folder"):
        read_lock(json.dumps(data))


def test_a_lock_of_another_format_or_with_a_bad_file_name_is_refused():
    with pytest.raises(ValueError, match="format"):
        read_lock(json.dumps({"format": 99, "collections": []}))
    data = {
        "format": 1,
        "collections": [
            {
                "name": "X",
                "folder": "x",
                "licence": "L",
                "redistributable": True,
                "files": [{"name": "../a.ttf", "url": "https://example.org/a.ttf", "sha256": "0" * 64, "size": 1}],
            }
        ],
    }
    with pytest.raises(ValueError, match="file name"):
        read_lock(json.dumps(data))


def test_a_lock_fetches_over_https_only():
    data = {
        "format": 1,
        "collections": [
            {
                "name": "X",
                "folder": "x",
                "licence": "L",
                "redistributable": True,
                "files": [{"name": "a.ttf", "url": "http://example.org/a.ttf", "sha256": "0" * 64, "size": 1}],
            }
        ],
    }
    with pytest.raises(ValueError, match="https"):
        read_lock(json.dumps(data))


def test_collection_folders_finds_one_collection_or_several(tmp_path):
    assert collection_folders(tmp_path / "nothing") == []
    one = tmp_path / "one"
    one.mkdir()
    (one / COLLECTION_FILE).write_text("{}")
    assert collection_folders(one) == [one]
    many = tmp_path / "many"
    for name in ("b", "a", "c"):
        (many / name).mkdir(parents=True)
    for name in ("a", "b"):
        (many / name / COLLECTION_FILE).write_text("{}")
    assert collection_folders(many) == [many / "a", many / "b"]


def test_the_command_line_fetches_and_reports(tmp_path, monkeypatch, capsys):
    collections, store = lock_of(tmp_path)
    monkeypatch.setattr("claudia_fonts.starter.read_lock", lambda text=None: tuple(collections))
    monkeypatch.setattr("claudia_fonts.starter._download", store.__getitem__)
    assert main(["fetch", str(tmp_path / "fonts")]) == 0
    assert "1 collections" in capsys.readouterr().out
    monkeypatch.setattr("claudia_fonts.starter._download", lambda url: b"other")
    (tmp_path / "fonts" / "testsans" / "OFL.txt").unlink()
    assert main(["fetch", str(tmp_path / "fonts")]) == 1
    assert "SHA-256" in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
def test_a_fetched_collection_can_be_read_by_other_users(tmp_path):
    """The Docker image fetches as root and the server runs as another user: the files must not be 0600."""
    collections, store = lock_of(tmp_path)
    for folder in fetch(tmp_path / "fonts", collections, download=store.__getitem__):
        for path in folder.iterdir():
            assert path.stat().st_mode & 0o777 == 0o644, path.name
