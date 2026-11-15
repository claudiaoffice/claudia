"""A document file goes from one server to another, end to end: two real servers, the file copied from one's folder and
brought to the other through the import (D440, D442), with its uid (D533–D535) and its description and tags (D530).

Moving documents between places by dragging them is not built (E5.18, "to be decided"); what a person can do today is
take the file and bring it to the other place. That path crosses a process boundary that the in-process tests of
``test_server_uid.py`` and ``test_server_details_import.py`` do not: the folder layout of a real server started from
the command line, and two servers that share nothing but the file.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from collections.abc import Iterator

import pytest
from live import PASSWORD, Live, server

APPS = ("computes", "composes", "creates")


@pytest.fixture(scope="module")
def two(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Live, Live]]:
    """Two servers: the one a document is made on, and the one it is brought to."""
    with server(tmp_path_factory.mktemp("home")) as home, server(tmp_path_factory.mktemp("away")) as away:
        yield home, away


def make(live: Live, app: str, name: str, description: str = "", tags: tuple[str, ...] = ()) -> str:
    """Make a document as its owner, say what it is about, and return its uid (from the welcome)."""
    with live.socket(app, name) as session:
        welcome = session.hello(create=True)
        if description or tags:
            kept = session.ok("set_details", password=PASSWORD, description=description, tags=list(tags))
            assert kept == {"description": description, "tags": list(tags)}
    return welcome["uid"]


def upload(live: Live, data: bytes, name: str) -> tuple[int, dict]:
    return live.post("/api/uploads", data, {"x-claudia-name": name})


def place(live: Live, token: str) -> tuple[int, dict]:
    return live.post(f"/api/uploads/{token}/place", b"{}", {"content-type": "application/json"})


def lookup(live: Live, uid: str) -> tuple[int, dict]:
    return live.post("/api/docs/lookup", json.dumps({"uid": uid}).encode(), {"content-type": "application/json"})


def row(live: Live, app: str, name: str) -> dict | None:
    status, listing = live.get("/api/docs")
    assert status == 200
    return next((r for r in listing["documents"] if r["app"] == app and r["id"] == name), None)


def with_manifest(data: bytes, **changes: object) -> bytes:
    """The file with fields of its plain manifest changed, as anybody holding the file could."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            content = source.read(info)
            if info.filename == "manifest.json":
                content = json.dumps({**json.loads(content), **changes}).encode()
            target.writestr(info, content)
    return out.getvalue()


@pytest.mark.parametrize("app", APPS)
def test_a_file_brought_to_another_server_is_the_same_document_there(two: tuple[Live, Live], app: str) -> None:
    home, away = two
    name = f"plan-{app}"
    uid = make(home, app, name, "The **plan** for spring", ("garden", "2027"))
    assert str(uuid.UUID(uid)) == uid

    # The list says what the owner said, and never the uid (D530, D533).
    listed = row(home, app, name)
    assert listed is not None and (listed["description"], listed["tags"]) == (
        "The **plan** for spring",
        ["garden", "2027"],
    )
    assert uid not in json.dumps(home.get("/api/docs")[1])
    assert lookup(home, uid) == (200, {"app": app, "id": name, "modified": listed["modified"]})
    assert lookup(away, uid)[0] == 404

    # Brought to the other server: the upload offers what the file says, and nothing is there yet.
    status, offered = upload(away, home.file_of(app, name), f"{name}.claudia")
    assert status == 200, offered
    assert (offered["app"], offered["id"], offered["description"], offered["tags"]) == (
        app,
        name,
        "The **plan** for spring",
        ["garden", "2027"],
    )
    assert offered["same_document"] is None and not offered["exists"]
    assert "uid" not in offered and uid not in json.dumps(offered)
    assert place(away, offered["upload"]) == (200, {"app": app, "id": name})

    # There it is the same document: same uid, same description, and its owner opens it with her password.
    assert lookup(away, uid)[1]["id"] == name
    moved = row(away, app, name)
    assert moved is not None and moved["tags"] == ["garden", "2027"]
    with away.socket(app, name) as session:
        assert session.hello()["uid"] == uid


@pytest.mark.parametrize("app", APPS)
def test_the_same_document_is_never_twice_on_a_server(two: tuple[Live, Live], app: str) -> None:
    home, _ = two
    name = f"once-{app}"
    make(home, app, name)
    data = home.file_of(app, name)

    status, offered = upload(home, data, f"{name}.claudia")
    assert status == 200 and offered["same_document"] == name and offered["exists"]
    status, refused = place(home, offered["upload"])
    assert status == 409 and f"“{name}”" in refused["detail"]


def test_a_renamed_file_is_still_the_same_document_and_cannot_be_opened_under_the_new_name(
    two: tuple[Live, Live],
) -> None:
    home, away = two
    make(home, "computes", "budget")
    forged = with_manifest(home.file_of("computes", "budget"), name="budget-copy")

    # On the server that has it, the uid gives it away whatever the file is called now (D535).
    status, offered = upload(home, forged, "budget-copy.claudia")
    assert status == 200 and offered["same_document"] == "budget"
    assert place(home, offered["upload"])[0] == 409

    # Elsewhere it can be placed, but the sealed parts are bound to name and uid (D533): it opens for nobody.
    status, offered = upload(away, forged, "budget-copy.claudia")
    assert status == 200 and offered["same_document"] is None
    assert place(away, offered["upload"])[0] == 200
    with away.socket("computes", "budget-copy") as session:
        refused = session.call("hello", user="ann", password=PASSWORD)
    assert not refused["ok"]


def test_a_document_keeps_its_app_wherever_it_goes(two: tuple[Live, Live]) -> None:
    """A text brought to a server goes to that server's composes, and is found there by its uid from any app."""
    home, away = two
    uid = make(home, "composes", "letter")
    status, offered = upload(away, home.file_of("composes", "letter"), "letter.claudia")
    assert status == 200 and offered["app"] == "composes"
    assert place(away, offered["upload"])[0] == 200
    assert lookup(away, uid)[1]["app"] == "composes"
    assert row(away, "computes", "letter") is None
