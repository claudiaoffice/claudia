"""How the server hands out the built web app: pages are revalidated on every load, hashed assets may be kept.

A desktop client (WebKit) keeps its HTTP cache between runs. Without ``Cache-Control`` it may reuse a page for a
while by its own guess, so after a server update a client could keep showing the previous web app (seen on the
demo server: the old frontend, with the old menus and no way to talk to the desktop shell).
"""

import pytest
from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider


@pytest.fixture
def web(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>start</title>")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    assets = tmp_path / "_nuxt"
    assets.mkdir()
    (assets / "entry.Dk3x9.js").write_text("console.log(1)")
    return tmp_path


@pytest.fixture
def client(web):
    app = create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(cost=2**4), web_dir=web)
    with TestClient(app) as c:
        yield c


def test_the_start_page_is_revalidated_on_every_load(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_an_address_of_the_app_gets_the_start_page_and_the_same_rule(client):
    response = client.get("/budget")
    assert response.status_code == 200
    assert "<title>start</title>" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_a_file_that_is_not_named_by_its_content_is_revalidated_too(client):
    assert client.get("/favicon.svg").headers["cache-control"] == "no-cache"


def test_assets_named_by_their_content_may_be_kept_for_good(client):
    response = client.get("/_nuxt/entry.Dk3x9.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_revalidating_costs_no_body_when_nothing_changed(client):
    first = client.get("/")
    again = client.get("/", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
    assert again.headers["cache-control"] == "no-cache"


def test_a_missing_file_is_still_a_404(client):
    assert client.get("/_nuxt/gone.js").status_code == 404
