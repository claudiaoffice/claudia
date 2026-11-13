"""The server's fonts for clients: the catalogue as data and the files by hash (E3.3, D905)."""

import hashlib
import json

import pytest
from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_fonts import COLLECTION_FILE
from claudia_fonts.testing import make_font
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.cli import UsageError, make_plan
from claudia_server.fonts import FontService
from claudia_server.hub import Hub, MemoryProvider


def collection(folder, name="Test", *, redistributable=True, fonts=(("Test Sans", "Regular", 400),)):
    folder.mkdir(parents=True)
    record = {"format": 1, "name": name, "licence": "OFL-1.1", "redistributable": redistributable}
    (folder / COLLECTION_FILE).write_text(json.dumps(record))
    for family, style, weight in fonts:
        make_font(folder / f"{family.replace(' ', '')}-{style}.ttf", family, style, weight=weight)
    return folder


def client(tmp_path, *folders):
    service = FontService.from_folders(folders, tmp_path / "webfonts")
    app = create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(), fonts=service)
    return TestClient(app), service


def test_the_listing_names_every_font_by_hash_with_its_file(tmp_path):
    root = tmp_path / "fonts"
    collection(root / "test", fonts=(("Test Sans", "Regular", 400), ("Test Sans", "Bold", 700)))
    c, service = client(tmp_path, root)
    answer = c.get("/api/fonts")
    assert answer.status_code == 200
    data = answer.json()
    assert data["format"] == 1 and data["digest"] == service.catalogue.digest
    assert [(f["family"], f["weight"]) for f in data["fonts"]] == [("Test Sans", 400), ("Test Sans", 700)]
    first = data["fonts"][0]
    assert first["file"] == f"/api/fonts/{first['sha256']}"
    assert first["axes"] == [] and first["outlines"] == "truetype"
    assert data["substitutions"]["Arial"] == "Liberation Sans"


def test_a_font_file_is_served_as_it_is_and_may_be_kept_for_good(tmp_path):
    root = collection(tmp_path / "fonts" / "test")
    c, service = client(tmp_path, root)
    font = service.servable()[0]
    answer = c.get(f"/api/fonts/{font.sha256}")
    assert answer.status_code == 200
    assert hashlib.sha256(answer.content).hexdigest() == font.sha256
    assert answer.headers["content-type"] == "font/ttf"
    assert "immutable" in answer.headers["cache-control"]
    woff2 = c.get(f"/api/fonts/{font.sha256}.woff2")
    assert woff2.status_code == 200 and woff2.content[:4] == b"wOF2"


def test_fonts_that_may_not_be_handed_out_are_neither_listed_nor_served(tmp_path):
    root = tmp_path / "fonts"
    collection(root / "closed", "Closed", redistributable=False, fonts=(("Closed Sans", "Regular", 400),))
    c, service = client(tmp_path, root)
    assert c.get("/api/fonts").json()["fonts"] == []
    closed = service.catalogue.fonts()[0]
    assert c.get(f"/api/fonts/{closed.sha256}").status_code == 404


@pytest.mark.parametrize("name", ["0" * 64, "nothex", "../../etc/passwd", "0" * 64 + ".ttf"])
def test_unknown_or_malformed_names_are_not_found(tmp_path, name):
    c, _ = client(tmp_path, collection(tmp_path / "fonts" / "t"))
    assert c.get(f"/api/fonts/{name}").status_code == 404


def test_a_file_changed_on_disk_is_refused_rather_than_served_under_its_old_hash(tmp_path):
    root = collection(tmp_path / "fonts" / "test")
    c, service = client(tmp_path, root)
    font = service.servable()[0]
    font.path.write_bytes(font.path.read_bytes() + b"\0")
    assert c.get(f"/api/fonts/{font.sha256}").status_code == 409


def test_without_a_font_service_there_are_no_font_routes(tmp_path):
    app = create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory())
    with TestClient(app) as c:
        assert c.get("/api/fonts").status_code == 404


def test_the_command_line_reads_fonts_folders_and_says_what_it_has(tmp_path):
    root = tmp_path / "fonts"
    collection(root / "a", "A", fonts=(("Alpha", "Regular", 400),))
    collection(root / "b", "B", fonts=(("Beta", "Regular", 400), ("Beta", "Bold", 700)))
    state = tmp_path / "state"
    plan = make_plan(["--no-tls", "--state-dir", str(state), "--fonts", str(root)])
    assert "fonts: 3 files in 2 families for clients (/api/fonts)" in plan.banner


def test_the_state_folder_s_fonts_are_used_when_none_are_given(tmp_path):
    state = tmp_path / "state"
    collection(state / "fonts" / "test")
    plan = make_plan(["--no-tls", "--state-dir", str(state)])
    assert any(line.startswith("fonts: 1 files") for line in plan.banner)
    bare = make_plan(["--no-tls", "--state-dir", str(tmp_path / "empty")])
    assert any(line.startswith("no fonts to hand out") for line in bare.banner)


def test_a_fonts_folder_that_does_not_exist_stops_the_server(tmp_path):
    with pytest.raises(UsageError, match="--fonts"):
        make_plan(["--no-tls", "--state-dir", str(tmp_path / "s"), "--fonts", str(tmp_path / "missing")])


def test_making_a_webfont_does_not_hold_up_the_rest_of_the_server(tmp_path, monkeypatch):
    """PERF-09: WOFF2 compression takes seconds for an ordinary font (2.4 s for DejaVu Sans, 37 s for a 10 MB one);
    it was done on the event loop, so every other request of every document waited for it."""
    import threading

    started, release = threading.Event(), threading.Event()

    def slow_woff2(data):
        started.set()
        release.wait(10)
        return b"wOF2" + data[:16]

    monkeypatch.setattr("claudia_fonts.webfonts._woff2", slow_woff2)
    root = collection(tmp_path / "fonts" / "test")
    c, service = client(tmp_path, root)
    font = service.servable()[0]
    with c:
        fetching = threading.Thread(target=lambda: c.get(f"/api/fonts/{font.sha256}.woff2"))
        fetching.start()
        try:
            assert started.wait(5)
            answered: list[int] = []
            asking = threading.Thread(target=lambda: answered.append(c.get("/api/health").status_code))
            asking.start()
            asking.join(3)
            assert answered == [200], "the health check waited for a webfont to be made"
        finally:
            release.set()
            fetching.join(10)
