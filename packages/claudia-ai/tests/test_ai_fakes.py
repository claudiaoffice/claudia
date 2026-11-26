"""The fakes tests use instead of a model and of Anthropic: held work fails a test that forgets it, never hangs it."""

import asyncio
import contextlib
import json
import threading
import urllib.request

import pytest

from claudia_ai import testing
from claudia_ai.testing import FakeAnthropic, FakeModel, Hold


def test_work_that_is_never_let_go_fails_the_test(monkeypatch):
    monkeypatch.setattr(testing, "HOLD_PATIENCE", 0.05)
    work = Hold()
    work.hold()
    with pytest.raises(AssertionError, match="never let go"):
        work.wait_until_free()


def test_waiting_for_work_that_never_begins_fails_the_test(monkeypatch):
    monkeypatch.setattr(testing, "HOLD_PATIENCE", 0.05)
    with pytest.raises(AssertionError, match="never began"):
        asyncio.run(Hold().begun())


def test_a_slow_model_gives_up_when_told_to_stop():
    model = FakeModel(delay=30)
    assert model.generate([], max_new_tokens=1, stop=lambda: True) == "partial"
    assert model.stopped_early


def test_a_held_anthropic_that_closes_answers_nobody():
    with FakeAnthropic() as fake:
        fake.hold()
        body = json.dumps({"model": "m", "messages": [], "max_tokens": 1}).encode()
        request = urllib.request.Request(fake.url, body, {"x-api-key": "sk-ant-test-key", "content-type": "x"})
        asking = threading.Thread(target=_ask, args=(request,), daemon=True)
        asking.start()
        assert fake.started.wait(5), "the request reached the fake"
    asking.join(5)  # the fake closed: the held request gave up instead of answering
    assert not asking.is_alive()


def _ask(request):
    with contextlib.suppress(OSError):  # the connection is closed without an answer
        urllib.request.urlopen(request, timeout=5).read()  # noqa: S310 - the fake on this computer
