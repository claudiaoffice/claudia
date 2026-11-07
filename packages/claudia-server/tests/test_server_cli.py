"""The command line: what it refuses, and what it prepares."""

import pytest

from claudia_core import Document, MemoryStore
from claudia_creates import SlideModel
from claudia_server.auth import Account
from claudia_server.cli import UsageError, load_model, make_plan
from claudia_server.protocol import Context, Limits


def plan(*args, tmp_path):
    return make_plan([*args, "--state-dir", str(tmp_path)])


def test_the_default_plan_is_encrypted_and_local(tmp_path):
    result = plan(tmp_path=tmp_path)
    options = result.uvicorn_options
    assert options["host"] == "127.0.0.1" and options["ssl_certfile"].endswith("cert.pem")
    assert any("fingerprint SHA256:" in line for line in result.banner)
    assert any("no web app" in line for line in result.banner)


def test_no_tls_says_so_loudly(tmp_path):
    result = plan("--no-tls", tmp_path=tmp_path)
    assert "ssl_certfile" not in result.uvicorn_options
    assert any(line.startswith("WARNING: no TLS") for line in result.banner)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--no-tls", "--tls-cert", "a.pem"], "contradict"),
        (["--no-tls", "--redirect-port", "8080"], "needs TLS"),
        (["--tls-cert", "a.pem"], "go together"),
        (["--port", "0"], "--port"),
        (["--model", "nonsense"], "module:Class"),
        (["--model", "no_such_module:Thing"], "cannot load the model"),
        (["--web", "/nonexistent"], "built web app"),
    ],
)
def test_impossible_options_are_refused_with_a_reason(tmp_path, args, message):
    with pytest.raises(UsageError, match=message):
        plan(*args, tmp_path=tmp_path)


def test_the_model_is_loaded_by_name():
    from claudia_core.testing import ListModel

    assert load_model("claudia_core.testing:ListModel") is ListModel


def test_a_folder_makes_the_store_persistent_and_sealed(tmp_path):
    result = plan("--no-tls", "--dir", str(tmp_path / "data"), tmp_path=tmp_path)
    assert any("encrypted" in line and "NOT" not in line for line in result.banner)
    assert (tmp_path / "data" / "docs").is_dir()


def test_the_old_plain_store_must_be_asked_for_by_name_and_says_what_it_is(tmp_path):
    result = plan("--no-tls", "--plain-dir", str(tmp_path / "data"), tmp_path=tmp_path)
    assert any("NOT encrypted" in line for line in result.banner)
    assert (tmp_path / "data" / "docs").is_dir()


def test_a_sealed_and_a_plain_folder_cannot_both_be_asked_for(tmp_path):
    with pytest.raises(UsageError, match="--dir"):
        plan("--no-tls", "--dir", str(tmp_path / "a"), "--plain-dir", str(tmp_path / "b"), tmp_path=tmp_path)


def test_the_server_really_seals_what_a_folder_receives(tmp_path):
    from starlette.testclient import TestClient

    folder = tmp_path / "data"
    client = TestClient(plan("--no-tls", "--dir", str(folder), tmp_path=tmp_path).app)
    with client.websocket_connect("/api/docs/plan/ws") as ws:
        ws.send_text(
            '{"id":1,"method":"hello","params":{"user":"Annabelle","password":"Correct-Horse-9","create":true}}'
        )
        assert ws.receive_json()["ok"]
    assert sorted(p.name for p in (folder / "docs").iterdir()) == ["plan.claudia", "plan.claudia.journal"]


def test_listing_can_be_switched_off_from_the_command_line(tmp_path):
    from starlette.testclient import TestClient

    on = TestClient(plan("--no-tls", tmp_path=tmp_path).app)
    off = TestClient(plan("--no-tls", "--no-list", tmp_path=tmp_path).app)
    assert on.get("/api/docs").status_code == 200 and off.get("/api/docs").status_code == 404


def test_a_workbook_server_offers_the_spreadsheet_methods_and_others_do_not(tmp_path):
    from starlette.testclient import TestClient

    def methods(*extra):
        client = TestClient(plan("--no-tls", *extra, tmp_path=tmp_path).app)
        return set(client.get("/api/protocol").json()["methods"])

    assert {"cells", "set_cells", "sheets"} <= methods()
    assert "cells" not in methods("--model", "claudia_core.testing:ListModel")


def test_a_text_server_offers_the_text_methods_and_the_text_assistant(tmp_path):
    import asyncio

    from starlette.testclient import TestClient

    served = plan("--no-tls", "--model", "claudia_composes:TextModel", tmp_path=tmp_path)
    methods = set(TestClient(served.app).get("/api/protocol").json()["methods"])
    assert {"blocks", "replace_text", "suggest"} <= methods and "cells" not in methods

    async def users():
        return (await served.app.state.hub.open("x", create=True)).users()

    assert asyncio.run(users()) == ["ai"]


def test_workbooks_get_the_stand_in_assistant_unless_switched_off(tmp_path):
    import asyncio

    async def users(*extra):
        hosted = await plan("--no-tls", *extra, tmp_path=tmp_path).app.state.hub.open("x", create=True)
        return hosted.users()

    assert asyncio.run(users()) == ["ai"]
    assert asyncio.run(users("--no-assistant")) == []


# ---------------------------------------------------------------- the AI assistant with a language model (E7.1)
@pytest.fixture
def model_folder(tmp_path):
    folder = tmp_path / "qwen-ov"
    folder.mkdir()
    (folder / "openvino_model.xml").write_text("<net/>")
    return folder


@pytest.fixture
def fake_model(monkeypatch):
    """Stands in for OpenVinoModel: remembers how it was made, answers by echoing the question."""
    from claudia_ai.testing import FakeModel

    made = []

    def make(path, device, **options):
        model = FakeModel(lambda messages: "I heard: " + messages[-1]["content"])
        model.name = f"{path} on {device}"
        made.append((str(path), device))
        return model

    monkeypatch.setattr("claudia_server.cli.OpenVinoModel", make)
    return made


def test_a_model_is_loaded_at_start_up_and_named_in_the_banner(tmp_path, model_folder, fake_model):
    result = plan("--no-tls", "--ai", str(model_folder), "--ai-device", "NPU", tmp_path=tmp_path)
    assert fake_model == [(str(model_folder), "NPU")]
    assert any('user "ai"' in line and "NPU" in line for line in result.banner)
    result.close()


def test_the_gpu_is_the_default_device(tmp_path, model_folder, fake_model):
    plan("--no-tls", "--ai", str(model_folder), tmp_path=tmp_path).close()
    assert fake_model[0][1] == "GPU"


def test_a_model_that_cannot_be_loaded_stops_the_server_with_the_reason(tmp_path):
    with pytest.raises(UsageError, match=r"--ai: .* is not a folder"):
        plan("--no-tls", "--ai", str(tmp_path / "missing"), tmp_path=tmp_path)


@pytest.mark.parametrize("option", ["--ai-max-tokens", "--ai-timeout"])
def test_the_limits_must_be_positive(tmp_path, model_folder, fake_model, option):
    with pytest.raises(UsageError, match="must be positive"):
        plan("--no-tls", "--ai", str(model_folder), option, "0", tmp_path=tmp_path)


def test_a_model_and_no_assistant_contradict_each_other(tmp_path, model_folder, fake_model):
    with pytest.raises(UsageError, match="contradict"):
        plan("--no-tls", "--ai", str(model_folder), "--no-assistant", tmp_path=tmp_path)


def test_a_model_for_documents_the_assistant_does_not_know_is_refused(tmp_path, model_folder, fake_model):
    with pytest.raises(UsageError, match="does not know documents of this kind"):
        plan("--no-tls", "--ai", str(model_folder), "--model", "claudia_core.testing:ListModel", tmp_path=tmp_path)


def test_the_first_replies_of_the_model_arrive_in_the_chat_over_a_real_socket(tmp_path, model_folder, fake_model):
    from starlette.testclient import TestClient
    from test_server_app import Peer

    result = plan("--no-tls", "--ai", str(model_folder), tmp_path=tmp_path)
    with TestClient(result.app) as client:
        peer = Peer(client, create=True)
        assert peer.request("chat", {"text": "@ai hello"})["ok"]
        while not any(f.get("event") == "chat" and f["data"]["author"] == "ai" for f in peer.pushed):
            frame = peer.socket.receive_json()
            peer.pushed.append(frame)
        reply = next(f["data"] for f in peer.pushed if f.get("event") == "chat" and f["data"]["author"] == "ai")
        assert (reply["to"], reply["text"]) == ("ann", "I heard: hello")
        peer.close()
    result.close()


CREATES = ["--model", "claudia_creates:SlideModel"]


def test_a_presentation_server_offers_the_slide_methods(tmp_path):
    from starlette.testclient import TestClient

    client = TestClient(plan("--no-tls", *CREATES, tmp_path=tmp_path).app)
    assert {"slides", "slide", "add_object", "shapes"} <= set(client.get("/api/protocol").json()["methods"])
    assert client.get("/api/docs").json()["app"] == "creates"


def test_shape_folders_extend_the_library(tmp_path):
    shapes = tmp_path / "my-shapes"
    shapes.mkdir()
    (shapes / "bar.json").write_text(
        '{"format": 1, "id": "bar", "name": "Bar", "path": "M0 0 L100 0 L100 100 L0 100 Z"}'
    )
    (shapes / "broken.json").write_text("{ not json")
    result = plan("--no-tls", *CREATES, "--shapes", str(shapes), tmp_path=tmp_path)
    assert any("shapes:" in line and "bar" in line for line in result.banner)
    assert any("broken.json" in line for line in result.banner), "a file that cannot be read is named, not ignored"
    methods = result.app.state.hub.methods
    context = Context(Document(SlideModel.empty(), store=MemoryStore()), Account("ann", "owner"), Limits())
    assert "bar" in [shape["id"] for shape in methods.dispatch(context, "shapes", None)["library"]]


def test_the_shape_folder_must_exist_and_belongs_to_presentations(tmp_path):
    with pytest.raises(UsageError, match="not a folder"):
        plan(*CREATES, "--shapes", str(tmp_path / "missing"), tmp_path=tmp_path)
    with pytest.raises(UsageError, match="presentations"):
        plan("--shapes", str(tmp_path), tmp_path=tmp_path)


# ------------------------------------------------------------------------ SEC-01: the names a server answers to
def status(app, base_url, path="/api/health"):
    from starlette.testclient import TestClient

    return TestClient(app, base_url=base_url).get(path).status_code


def test_the_server_answers_only_to_this_computer_by_default(tmp_path):
    app = plan("--no-tls", tmp_path=tmp_path).app
    assert status(app, "http://localhost:8765") == 200
    assert status(app, "http://127.0.0.1:8765") == 200
    assert status(app, "http://evil.example:8765") == 403


@pytest.mark.parametrize("extra", [["--allow-host", "claudia.example.org"], ["--tls-name", "claudia.example.org"]])
def test_names_given_on_the_command_line_are_answered(tmp_path, extra):
    app = plan(*extra, tmp_path=tmp_path).app
    assert status(app, "http://claudia.example.org") == 200
    assert status(app, "http://other.example.org") == 403


def test_the_name_the_server_binds_to_is_answered(tmp_path):
    app = plan("--host", "claudia.example.org", tmp_path=tmp_path).app
    assert status(app, "http://claudia.example.org") == 200


def test_the_name_this_computer_goes_by_is_answered_and_asking_for_it_needs_no_dns(tmp_path, monkeypatch):
    def no_dns():
        raise AssertionError("finding the fully qualified name can wait for a DNS server for seconds")

    monkeypatch.setattr("socket.gethostname", lambda: "nas")
    monkeypatch.setattr("socket.getfqdn", no_dns)
    app = plan("--no-tls", tmp_path=tmp_path).app
    assert status(app, "http://nas:8765") == 200
    assert status(app, "http://nas.home.example:8765") == 403, "a longer name is added with --allow-host"


def test_a_bad_allow_host_is_refused_with_a_reason(tmp_path):
    with pytest.raises(UsageError, match="--allow-host"):
        plan("--no-tls", "--allow-host", "evil.example/path", tmp_path=tmp_path)


def test_the_banner_says_what_the_server_answers_to(tmp_path):
    result = plan("--no-tls", "--allow-host", "claudia.example.org", tmp_path=tmp_path)
    line = next(line for line in result.banner if line.startswith("answers to"))
    assert "claudia.example.org" in line and "localhost" in line and "--allow-host" in line


# --------------------------------------------------------------- SEC-07: no clear text where others can listen
@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.20", "claudia.example.org"])
def test_plain_text_is_refused_on_an_address_others_can_reach(tmp_path, host):
    with pytest.raises(UsageError, match="--behind-proxy"):
        plan("--no-tls", "--host", host, tmp_path=tmp_path)


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "localhost"])
def test_plain_text_is_fine_on_this_computer(tmp_path, host):
    assert plan("--no-tls", "--host", host, tmp_path=tmp_path).uvicorn_options["host"] == host


def test_behind_a_proxy_plain_text_is_allowed_on_any_address_and_the_banner_warns(tmp_path):
    result = plan("--no-tls", "--host", "0.0.0.0", "--behind-proxy", tmp_path=tmp_path)
    assert result.uvicorn_options["host"] == "0.0.0.0"
    assert any(line.startswith("WARNING: no TLS") and "proxy" in line for line in result.banner)


def test_behind_proxy_means_nothing_when_the_server_encrypts(tmp_path):
    with pytest.raises(UsageError, match="--behind-proxy"):
        plan("--behind-proxy", tmp_path=tmp_path)


def test_encryption_is_still_the_default_on_every_address(tmp_path):
    result = plan("--host", "0.0.0.0", tmp_path=tmp_path)
    assert result.uvicorn_options["ssl_certfile"].endswith("cert.pem")


# ------------------------------------------------------------------------------- SEC-02: limits and the secret
def test_the_caps_are_set_from_the_command_line(tmp_path):
    hub = plan("--no-tls", "--max-documents", "3", tmp_path=tmp_path).app.state.hub
    assert hub.max_documents == 3


@pytest.mark.parametrize("option", ["--max-documents", "--max-waiting", "--max-waiting-per-address"])
def test_a_cap_must_be_a_positive_number(tmp_path, option):
    with pytest.raises(UsageError, match=option):
        plan("--no-tls", option, "0", tmp_path=tmp_path)


SECRET = "a-long-secret-nobody-guesses-1234"


def listing(app, **headers):
    from starlette.testclient import TestClient

    return TestClient(app).get("/api/docs", headers=headers).status_code


def test_an_access_secret_can_come_from_a_file(tmp_path):
    secret_file = tmp_path / "secret"
    secret_file.write_text(SECRET + "\n")
    result = plan("--no-tls", "--access-secret-file", str(secret_file), tmp_path=tmp_path)
    assert listing(result.app) == 401 and listing(result.app, Authorization=f"Bearer {SECRET}") == 200
    assert any("access secret" in line for line in result.banner)
    assert not any(SECRET in line for line in result.banner), "the secret is never printed"


def test_an_access_secret_can_come_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDIA_ACCESS_SECRET", SECRET)
    app = plan("--no-tls", tmp_path=tmp_path).app
    assert listing(app) == 401 and listing(app, Authorization=f"Bearer {SECRET}") == 200


def test_the_file_wins_over_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDIA_ACCESS_SECRET", "x" * 32)
    secret_file = tmp_path / "secret"
    secret_file.write_text(SECRET)
    app = plan("--no-tls", "--access-secret-file", str(secret_file), tmp_path=tmp_path).app
    assert listing(app, Authorization=f"Bearer {SECRET}") == 200


def test_a_missing_or_weak_secret_is_refused_with_a_reason(tmp_path):
    with pytest.raises(UsageError, match="--access-secret-file"):
        plan("--no-tls", "--access-secret-file", str(tmp_path / "nothing"), tmp_path=tmp_path)
    weak = tmp_path / "weak"
    weak.write_text("short\n")
    with pytest.raises(UsageError, match="at least"):
        plan("--no-tls", "--access-secret-file", str(weak), tmp_path=tmp_path)


def test_an_empty_secret_stops_the_server_instead_of_leaving_it_open(tmp_path, monkeypatch):
    """A variable that is set but empty (an unset value in a compose file), or an empty file, is not "no secret"."""
    empty = tmp_path / "empty"
    empty.write_text("\n")
    with pytest.raises(UsageError, match="at least"):
        plan("--no-tls", "--access-secret-file", str(empty), tmp_path=tmp_path)
    monkeypatch.setenv("CLAUDIA_ACCESS_SECRET", "")
    with pytest.raises(UsageError, match="at least"):
        plan("--no-tls", tmp_path=tmp_path)
    monkeypatch.setenv("CLAUDIA_ACCESS_SECRET", "short")
    with pytest.raises(UsageError, match="at least"):
        plan("--no-tls", tmp_path=tmp_path)


def test_no_secret_means_nothing_changes(tmp_path):
    assert listing(plan("--no-tls", tmp_path=tmp_path).app) == 200


# ------------------------------------------------------------------------------- the settings pages (admin.py)
def test_a_fresh_server_has_no_administrators_and_the_prompt_is_dormant_on_loopback(tmp_path):
    result = plan(tmp_path=tmp_path)
    assert not any("administrator" in line for line in result.banner)


def test_an_exposed_server_without_administrators_says_so_in_the_banner(tmp_path):
    result = plan("--no-tls", "--host", "0.0.0.0", "--behind-proxy", tmp_path=tmp_path)
    assert any("no administrator yet" in line for line in result.banner)


def test_max_documents_given_on_the_command_line_overrides_what_was_saved_but_does_not_replace_it(tmp_path):
    from claudia_server.server_settings import ServerSettings, save_settings

    save_settings(tmp_path, ServerSettings(max_documents=7))

    overridden = plan("--no-tls", "--max-documents", "3", tmp_path=tmp_path)
    assert overridden.app.state.hub.max_documents == 3

    not_overridden = plan("--no-tls", tmp_path=tmp_path)
    assert not_overridden.app.state.hub.max_documents == 7  # the override of the earlier run was never saved


def test_max_documents_without_any_saved_settings_falls_back_to_the_built_in_default(tmp_path):
    from claudia_server.hub import DEFAULT_MAX_DOCUMENTS

    result = plan("--no-tls", tmp_path=tmp_path)
    assert result.app.state.hub.max_documents == DEFAULT_MAX_DOCUMENTS


def test_an_access_secret_saved_through_the_settings_applies_without_any_option(tmp_path):
    from claudia_server.server_settings import ServerSettings, save_settings

    save_settings(tmp_path, ServerSettings(max_documents=5, access_secret=SECRET))
    app = plan("--no-tls", tmp_path=tmp_path).app
    assert listing(app) == 401
    assert listing(app, Authorization=f"Bearer {SECRET}") == 200


def test_an_operator_access_secret_overrides_the_saved_one_without_replacing_it(tmp_path):
    from claudia_server.server_settings import ServerSettings, load_settings, save_settings

    save_settings(tmp_path, ServerSettings(max_documents=5, access_secret=SECRET))
    other = "a-completely-different-secret-99"
    app = plan("--no-tls", "--access-secret-file", _write(tmp_path / "other-secret", other), tmp_path=tmp_path).app
    assert listing(app, Authorization=f"Bearer {other}") == 200
    assert listing(app, Authorization=f"Bearer {SECRET}") == 401
    assert load_settings(tmp_path, default_max_documents=1).access_secret == SECRET  # untouched on disk


def _write(path, text):
    path.write_text(text)
    return str(path)
