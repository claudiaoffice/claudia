"""The command line: what it refuses, and what it prepares."""

import pytest

from claudia_server.cli import UsageError, load_model, make_plan


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


def test_a_folder_makes_the_store_persistent(tmp_path):
    result = plan("--no-tls", "--dir", str(tmp_path / "data"), tmp_path=tmp_path)
    assert any("not encrypted" in line for line in result.banner)
    assert (tmp_path / "data" / "docs").is_dir()


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
