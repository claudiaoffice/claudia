"""The server's fonts for clients: the catalogue as data and the files by hash (E3.3, D905)."""

import hashlib
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_fonts import COLLECTION_FILE, DEFAULT_GENERICS, DEFAULT_SUBSTITUTIONS, read_lock
from claudia_fonts.testing import make_font
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.cli import UsageError, _fonts, build_parser, make_plan
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
    assert data["substitutions"] == dict(DEFAULT_SUBSTITUTIONS)
    assert data["generics"] == dict(DEFAULT_GENERICS)


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


def test_fonts_for_this_server_only_go_to_people_with_its_access_secret(tmp_path):
    """D1041: a collection whose fonts may go to this server's people only (``redistributable: false``) is listed and
    served to a request with the access secret, and to nobody else."""
    root = tmp_path / "fonts"
    collection(root / "closed", "Closed", redistributable=False, fonts=(("Closed Sans", "Regular", 400),))
    service = FontService.from_folders([root], tmp_path / "webfonts")
    secret = "s" * 24
    c = TestClient(create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(), fonts=service, access_secret=secret))
    closed = service.catalogue.fonts()[0]
    assert c.get("/api/fonts").json()["fonts"] == []
    assert c.get(f"/api/fonts/{closed.sha256}").status_code == 404
    assert c.get(f"/api/fonts/{closed.sha256}.woff2").status_code == 404
    with_secret = {"authorization": f"Bearer {secret}"}
    [listed] = c.get("/api/fonts", headers=with_secret).json()["fonts"]
    assert (listed["family"], listed["may_go"]) == ("Closed Sans", "this-server")
    assert c.get(f"/api/fonts/{closed.sha256}", headers=with_secret).status_code == 200
    assert c.get(f"/api/fonts/{closed.sha256}.woff2", headers=with_secret).status_code == 200


def test_on_a_server_without_an_access_secret_its_people_are_everyone_who_reaches_it(tmp_path):
    root = tmp_path / "fonts"
    collection(root / "closed", "Closed", redistributable=False, fonts=(("Closed Sans", "Regular", 400),))
    c, _ = client(tmp_path, root)
    assert [f["family"] for f in c.get("/api/fonts").json()["fonts"]] == ["Closed Sans"]


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
    # the 3 files of the folder, and the files of the families every server has (D500)
    files, families = _shipped()
    assert f"fonts: {files + 3} files in {families + 2} families for clients (/api/fonts)" in plan.banner


def test_the_state_folder_s_fonts_are_read_after_the_operator_s(tmp_path):
    """The collections added through the server settings (``STATE_DIR/fonts``, D1041) are read with ``--fonts`` too,
    after its folders."""
    state = tmp_path / "state"
    collection(state / "fonts" / "added", "Added", fonts=(("Gamma", "Regular", 400),))
    root = tmp_path / "fonts"
    collection(root / "a", "A", fonts=(("Alpha", "Regular", 400),))
    plan = make_plan(["--no-tls", "--state-dir", str(state), "--fonts", str(root)])
    files, families = _shipped()
    assert f"fonts: {files + 2} files in {families + 2} families for clients (/api/fonts)" in plan.banner


def test_the_state_folder_s_fonts_are_used_when_none_are_given(tmp_path):
    state = tmp_path / "state"
    collection(state / "fonts" / "test")
    plan = make_plan(["--no-tls", "--state-dir", str(state)])
    files, families = _shipped()
    assert f"fonts: {files + 1} files in {families + 1} families for clients (/api/fonts)" in plan.banner


def test_a_server_nobody_gave_fonts_has_the_starter_set_so_printing_always_works(tmp_path):
    """D500: the desktop apps' local server is started without fonts; before, printing there said "the server has no
    fonts to lay out with" and nothing else. The pinned starter set ships with claudia_fonts, so there is always the
    fallback family (Inter) and the metric-compatible stand-ins for Calibri and Cambria (Carlito, Caladea)."""
    bare = make_plan(["--no-tls", "--state-dir", str(tmp_path / "empty")])
    files, count = _shipped()
    assert f"fonts: {files} files in {count} families for clients (/api/fonts)" in bare.banner
    families = {f.family for f in _fonts(build_parser().parse_args([]), tmp_path / "empty").servable()}
    assert {"Inter", "Fraunces", "JetBrains Mono", "Carlito", "Caladea", "Arimo", "Tinos", "Cousine"} <= families


def _shipped() -> tuple[int, int]:
    """How many font files and families the shipped starter set has (D500)."""
    lock = read_lock()
    return sum(1 for c in lock for f in c.files if f.name.endswith(".ttf")), len(lock)


SAMPLE = Path(__file__).resolve().parents[3] / "test-documents" / "stand-in-fonts.json"


def test_a_server_nobody_gave_fonts_lists_every_stand_in_of_the_sample_and_the_table_that_names_it(tmp_path):
    """E3.13: what the shared sample's fonts are shown with is listed, so every client can lay them out."""
    service = _fonts(build_parser().parse_args([]), tmp_path / "empty")
    app = create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(), fonts=service)
    data = TestClient(app).get("/api/fonts").json()
    listed = {f["family"] for f in data["fonts"]}
    for entry in json.loads(SAMPLE.read_text(encoding="utf-8"))["fonts"]:
        if entry["closeness"] == "same-widths":
            assert data["substitutions"][entry["family"]] == entry["stand_in"]
        if entry["stand_in"]:
            assert entry["stand_in"] in listed, entry["family"]
    assert set(data["generics"].values()) <= listed


def test_a_font_the_operator_adds_replaces_the_shipped_one_of_the_same_family_and_style(tmp_path):
    state = tmp_path / "state"
    collection(state / "fonts" / "mine", "Mine", fonts=(("Inter", "Regular", 400),))
    fonts = _fonts(build_parser().parse_args([]), state)
    regular = [f for f in fonts.servable() if f.family == "Inter" and f.style == "Regular"]
    assert len(regular) == 1 and regular[0].path.is_relative_to(state)


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
