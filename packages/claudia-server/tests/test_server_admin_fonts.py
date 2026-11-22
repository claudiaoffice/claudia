"""``/api/admin/fonts``: Server settings ▸ Fonts (E3.13 f, D1041). Administrators only; check first, then add."""

import json
from urllib.parse import quote

import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_fonts import COLLECTION_FILE
from claudia_fonts.testing import make_font
from claudia_server.admin import AdminDirectory
from claudia_server.admin_api import AdminContext, AiRuntime
from claudia_server.admin_fonts import HOLD_SECONDS, FontUploads
from claudia_server.admin_sessions import AdminSessions
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.fonts import FontService
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.server_settings import ServerSettings

PASSWORD = "correct horse battery"


def collection(folder, name, *, redistributable=True, fonts=(("Shipped Sans", "Regular"),), extra=None):
    folder.mkdir(parents=True)
    record = {"format": 1, "name": name, "licence": "OFL-1.1", "redistributable": redistributable, **(extra or {})}
    (folder / COLLECTION_FILE).write_text(json.dumps(record))
    for family, style in fonts:
        make_font(folder / f"{family.replace(' ', '')}-{style.replace(' ', '')}.ttf", family, style)
    return folder


@pytest.fixture
def admins():
    directory = AdminDirectory(cost=2**4)
    directory.add("anna", PASSWORD, added="2026-11-01T00:00:00Z")
    return directory


@pytest.fixture
def server(tmp_path, admins):
    shipped = tmp_path / "shipped"
    collection(shipped / "inter", "Inter", fonts=(("Inter", "Regular"), ("Inter", "Bold")))
    collection(shipped / "arimo", "Arimo", fonts=(("Arimo", "Regular"),))
    operator = collection(
        tmp_path / "operator" / "house", "House", redistributable=False, fonts=(("House", "Regular"),)
    )
    make_font(operator / "House-Locked.ttf", "House", "Locked", fs_type=2)
    added = tmp_path / "state" / "fonts"
    fonts = FontService.from_folders([operator.parent], tmp_path / "webfonts", shipped=[shipped], added_root=added)
    admin = AdminContext(
        admins=admins,
        sessions=AdminSessions(),
        settings=ServerSettings(max_documents=20),
        state_dir=tmp_path / "state",
        ai=AiRuntime(models=(ListModel,), enabled=False),
        exposed=True,
        fonts=fonts,
    )
    client = TestClient(create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(), admin=admin, fonts=fonts))
    token = client.post("/api/admin/login", json={"name": "anna", "password": PASSWORD}).json()["token"]
    client.headers["authorization"] = f"Bearer {token}"
    return client, fonts, tmp_path


def upload(client, path):
    answer = client.post(
        "/api/admin/fonts/files", content=path.read_bytes(), headers={"x-claudia-name": quote(path.name)}
    )
    assert answer.status_code == 200, answer.text
    return answer.json()["token"]


def made(tmp_path, name, family="City Sans", style="Regular", **kwargs):
    (tmp_path / "made").mkdir(exist_ok=True)
    return make_font(tmp_path / "made" / name, family, style, **kwargs)


def test_only_an_administrator_sees_the_fonts_page(server):
    client, _, _ = server
    assert client.get("/api/admin/fonts", headers={"authorization": "Bearer nope"}).status_code == 401


def test_the_page_lists_collections_families_and_problems(server):
    client, _, _ = server
    view = client.get("/api/admin/fonts").json()
    assert view["format"] == 1
    assert (view["counts"]["families"], view["counts"]["files"], view["counts"]["not_usable"]) == (3, 4, 1)
    shipped, house = view["collections"]
    assert (shipped["id"], shipped["name"], shipped["origin"], shipped["editable"]) == (
        "shipped",
        "Shipped with Claudia",
        "shipped",
        False,
    )
    assert shipped["families"] == ["Arimo", "Inter"] and shipped["may_go"] == "anywhere"
    assert (house["origin"], house["may_go"], house["editable"], house["problems"]) == (
        "operator",
        "this-server",
        False,
        1,
    )
    families = {f["family"]: f for f in view["families"]}
    assert families["Arimo"]["stands_in_for"][:2] == ["Arial", "Helvetica"]
    assert "sans-serif" in families["Inter"]["stands_in_for"]
    assert sorted(s["style"] for s in families["Inter"]["styles"]) == ["Bold", "Regular"]
    [problem] = families["House"]["problems"]
    assert (problem["code"], problem["detail"], problem["style"]) == ("forbids-embedding", "2", "Locked")


def test_checking_changes_nothing_and_says_what_each_file_becomes(server):
    client, fonts, tmp_path = server
    tokens = [
        upload(client, made(tmp_path, "City-Regular.ttf")),
        upload(client, made(tmp_path, "City-BoldItalic.ttf", style="Bold Italic", fs_type=2)),
        upload(client, made(tmp_path, "Inter-Regular.ttf", family="Inter", version="9.9")),
    ]
    before = fonts.catalogue.digest
    answer = client.post("/api/admin/fonts/check", json={"files": tokens}).json()
    assert [(f["name"], f["verdict"], f["code"]) for f in answer["files"]] == [
        ("City-Regular.ttf", "added", ""),
        ("City-BoldItalic.ttf", "left-out", "forbids-embedding"),
        ("Inter-Regular.ttf", "added", "replaces"),
    ]
    assert answer["files"][2]["detail"] == "Shipped with Claudia"
    assert answer["adds"] == 2 and answer["families"] == ["City Sans", "Inter"]
    assert fonts.catalogue.digest == before


def test_adding_makes_a_collection_the_page_and_the_clients_see_at_once(server):
    client, fonts, tmp_path = server
    token = upload(client, made(tmp_path, "City-Regular.ttf"))
    answer = client.post(
        "/api/admin/fonts/collections",
        json={"files": [token], "name": "City house fonts", "licence": "Contract 2024-117", "may_go": "this-server"},
    )
    assert answer.status_code == 201, answer.text
    view = answer.json()
    added = view["collections"][-1]
    assert (added["name"], added["origin"], added["editable"], added["added_by"]) == (
        "City house fonts",
        "added",
        True,
        "anna",
    )
    assert added["may_go"] == "this-server" and added["families"] == ["City Sans"]
    assert "City Sans" in fonts.catalogue
    assert (tmp_path / "state" / "fonts" / added["id"] / COLLECTION_FILE).is_file()
    # the staged file was used up
    again = client.post("/api/admin/fonts/check", json={"files": [token]})
    assert again.status_code == 400


@pytest.mark.parametrize(
    ("change", "status"),
    [({"may_go": "everyone"}, 400), ({"name": " "}, 400), ({"licence": ""}, 400), ({"files": ["nope"]}, 400)],
)
def test_a_collection_without_what_it_needs_is_refused(server, change, status):
    client, _, tmp_path = server
    token = upload(client, made(tmp_path, "City-Regular.ttf"))
    body = {"files": [token], "name": "City", "licence": "OFL-1.1", "may_go": "anywhere"} | change
    assert client.post("/api/admin/fonts/collections", json=body).status_code == status


def test_an_added_collection_can_be_renamed_and_removed_and_the_shipped_set_cannot(server):
    client, fonts, tmp_path = server
    token = upload(client, made(tmp_path, "City-Regular.ttf"))
    body = {"files": [token], "name": "City", "licence": "OFL-1.1", "may_go": "anywhere"}
    added = client.post("/api/admin/fonts/collections", json=body).json()["collections"][-1]
    renamed = client.patch(f"/api/admin/fonts/collections/{added['id']}", json={"name": "City fonts"}).json()
    assert renamed["collections"][-1]["name"] == "City fonts"
    assert client.delete("/api/admin/fonts/collections/shipped").status_code == 409
    house = renamed["collections"][1]["id"]
    assert client.delete(f"/api/admin/fonts/collections/{house}").status_code == 409
    assert client.patch(f"/api/admin/fonts/collections/{house}", json={"name": "x"}).status_code == 409
    assert client.delete("/api/admin/fonts/collections/nope").status_code == 404
    gone = client.delete(f"/api/admin/fonts/collections/{added['id']}").json()
    assert [c["name"] for c in gone["collections"]] == ["Shipped with Claudia", "House"]
    assert "City Sans" not in fonts.catalogue


def test_an_upload_of_another_kind_is_kept_and_checked_as_left_out(server):
    client, _, _ = server
    token = client.post("/api/admin/fonts/files", content=b"hello", headers={"x-claudia-name": "notes.txt"}).json()
    answer = client.post("/api/admin/fonts/check", json={"files": [token["token"]]}).json()
    assert [(f["verdict"], f["code"]) for f in answer["files"]] == [("left-out", "not-a-font-file")]


def test_the_page_says_whether_the_server_keeps_this_server_fonts_to_its_people(server):
    client, _, _ = server
    assert client.get("/api/admin/fonts").json()["access_secret_set"] is False


def sign_in(client, admins, name):
    """Another administrator's headers on the same server."""
    admins.add(name, PASSWORD, added="2026-11-17T00:00:00Z")
    token = client.post("/api/admin/login", json={"name": name, "password": PASSWORD}).json()["token"]
    return {"authorization": f"Bearer {token}"}


def test_the_page_says_how_much_may_wait_to_be_added(server):
    client, _, _ = server
    assert client.get("/api/admin/fonts").json()["limits"] == {"files": 64, "bytes": 128 * 1024 * 1024}


def test_files_let_go_of_free_the_room_for_others(server, monkeypatch):
    """CODE-49: files chosen and then given up (Cancel, Start again, a failed upload) are dropped by the dialog, and
    the room is free again at once."""
    client, _, tmp_path = server
    monkeypatch.setattr("claudia_server.admin_fonts.MAX_FILES", 2)
    font = made(tmp_path, "City-Regular.ttf")
    tokens = [upload(client, font), upload(client, font)]
    full = client.post("/api/admin/fonts/files", content=font.read_bytes(), headers={"x-claudia-name": "c.ttf"})
    assert full.status_code == 503 and "let go" in full.json()["detail"]
    dropped = client.request("DELETE", "/api/admin/fonts/files", json={"files": [*tokens, "unknown"]})
    assert dropped.json() == {"dropped": 2}
    assert client.post("/api/admin/fonts/check", json={"files": tokens}).status_code == 400
    upload(client, font)


def test_what_one_administrator_holds_neither_paragraphs_nor_serves_another(server, admins, monkeypatch):
    client, _, tmp_path = server
    monkeypatch.setattr("claudia_server.admin_fonts.MAX_FILES", 1)
    font = made(tmp_path, "City-Regular.ttf")
    anna = upload(client, font)
    bob = sign_in(client, admins, "bob")
    answer = client.post(
        "/api/admin/fonts/files", content=font.read_bytes(), headers={"x-claudia-name": "c.ttf", **bob}
    )
    assert answer.status_code == 200
    assert client.post("/api/admin/fonts/check", json={"files": [anna]}, headers=bob).status_code == 400
    assert client.request("DELETE", "/api/admin/fonts/files", json={"files": [anna]}, headers=bob).json() == {
        "dropped": 0
    }


def test_held_files_go_after_a_while():
    clock = [0.0]
    uploads = FontUploads(clock=lambda: clock[0])
    token = uploads.put("anna", "a.ttf", b"x")
    assert uploads.files("anna", [token]) == [("a.ttf", b"x")]
    clock[0] = HOLD_SECONDS + 1
    with pytest.raises(HTTPException):
        uploads.files("anna", [token])
