"""What a browser is told a page of this server may do (SEC-13, ``claudia_server.security_headers``).

Before, an answer carried only ``Cache-Control``: any site could frame a document or the server settings, and nothing
limited where a script could come from or connect to.
"""

import base64
import hashlib

import pytest
from starlette.testclient import TestClient

from claudia_core.testing import ListModel
from claudia_server.app import create_app
from claudia_server.auth import ScryptDirectory
from claudia_server.hub import Hub, MemoryProvider
from claudia_server.security_headers import FRAME_ANCESTORS, content_security_policy, inline_script_hashes

CONFIG = 'window.__NUXT__={};window.__NUXT__.config={public:{},app:{baseURL:"/"}}'
IMPORT_MAP = '{"imports":{"#entry":"/_nuxt/entry.js"}}'
START_PAGE = (
    "<!DOCTYPE html><html><head>"
    f'<script type="importmap">{IMPORT_MAP}</script>'
    '<script type="module" src="/_nuxt/entry.js" crossorigin></script></head>'
    f'<body><div id="__nuxt"></div><script>{CONFIG}</script>'
    '<script type="application/json" id="__NUXT_DATA__">[{"serverRendered":1},false]</script></body></html>'
)


def sha(text: str) -> str:
    return f"'sha256-{base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()}'"


def directives(response) -> dict[str, str]:
    policy = response.headers["content-security-policy"]
    return {part.split(" ", 1)[0]: part.split(" ", 1)[1] for part in policy.split("; ")}


@pytest.fixture
def client(tmp_path):
    (tmp_path / "index.html").write_text(START_PAGE)
    (tmp_path / "_nuxt").mkdir()
    (tmp_path / "_nuxt" / "entry.js").write_text("console.log(1)")
    app = create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(cost=2**4), web_dir=tmp_path)
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", ["/", "/admin", "/budget", "/_nuxt/entry.js", "/api/health", "/api/protocol"])
def test_every_answer_carries_the_headers(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in response.headers["permissions-policy"]
    rules = directives(response)
    assert rules["frame-ancestors"] == FRAME_ANCESTORS
    assert rules["object-src"] == "'none'" and rules["base-uri"] == "'none'"


def test_only_the_start_pages_own_inline_scripts_may_run(client):
    rules = directives(client.get("/"))
    assert rules["script-src"].split() == ["'self'", *sorted((sha(CONFIG), sha(IMPORT_MAP)))]
    assert "'unsafe-inline'" not in rules["script-src"] and "'unsafe-eval'" not in rules["script-src"]


def test_connections_go_to_this_server_and_its_websocket_only(client):
    rules = directives(client.get("/", headers={"host": "127.0.0.1:8765"}))
    assert rules["connect-src"] == "'self' ws://127.0.0.1:8765 wss://127.0.0.1:8765"


def test_a_desktop_shell_on_this_computer_may_frame_the_app_and_nobody_else():
    """The Windows and macOS clients show the web app in a frame of their own local page (D251)."""
    assert FRAME_ANCESTORS.split() == ["'self'", "http://127.0.0.1:*", "http://localhost:*"]


def test_a_host_header_cannot_add_a_directive():
    policy = content_security_policy("evil; script-src *")
    names = [part.split(" ", 1)[0] for part in policy.split("; ")]
    assert names.count("script-src") == 1, "no second directive"
    assert "*" not in policy.replace("127.0.0.1:*", "").replace("localhost:*", "")


def test_data_blocks_and_scripts_with_a_source_are_not_hashed():
    page = '<script src="/a.js"></script><script type="application/json">{"a":1}</script><script>go()</script>'
    assert inline_script_hashes([page]) == (sha("go()"),)
    assert inline_script_hashes([page, page]) == (sha("go()"),), "one entry per script, however many pages"


def test_without_a_web_app_the_landing_page_is_covered_too():
    app = create_app(Hub(MemoryProvider(ListModel)), ScryptDirectory(cost=2**4))
    with TestClient(app) as c:
        rules = directives(c.get("/"))
    assert rules["script-src"] == "'self'"
    assert rules["frame-ancestors"] == FRAME_ANCESTORS


def test_the_api_description_keeps_only_the_framing_rule_for_now(client):
    """FastAPI's page loads its script from a CDN (SEC-14): a script rule would leave it blank."""
    response = client.get("/api/swagger")
    assert response.headers["content-security-policy"] == f"frame-ancestors {FRAME_ANCESTORS}"
    assert response.headers["x-content-type-options"] == "nosniff"
