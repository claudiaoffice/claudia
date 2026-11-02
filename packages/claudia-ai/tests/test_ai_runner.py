"""One model for the whole server: one question at a time, off the event loop, with a time limit."""

import asyncio
import threading
import time

import pytest

from claudia_ai import ModelError, ModelRunner, Request
from claudia_ai.testing import FakeModel


def ask(runner, text="hi"):
    return runner.answer(Request("ann", text))


def run(coro):
    return asyncio.run(coro)


def test_the_answer_is_read_into_a_turn():
    runner = ModelRunner(FakeModel(lambda m: "Hello, " + m[-1]["content"]))
    assert run(ask(runner, "Ann")).say == "Hello, Ann"
    runner.close()


def test_generating_does_not_block_the_event_loop():
    model = FakeModel(delay=0.3)
    runner = ModelRunner(model)

    async def main():
        ticks = 0
        task = asyncio.create_task(ask(runner))
        while not task.done():
            await asyncio.sleep(0.01)
            ticks += 1
        return ticks, model.threads

    ticks, threads = run(main())
    assert ticks > 5, "the loop kept running while the model worked"
    assert threads and threading.current_thread() not in threads, "the model works on its own thread"
    runner.close()


def test_questions_are_answered_one_at_a_time_in_order():
    model = FakeModel(lambda m: m[-1]["content"], delay=0.05)
    runner = ModelRunner(model)

    async def main():
        return await asyncio.gather(*(ask(runner, str(n)) for n in range(4)))

    turns = run(main())
    assert [t.say for t in turns] == ["0", "1", "2", "3"] and model.most_at_once == 1
    assert [call[-1]["content"] for call in model.calls] == ["0", "1", "2", "3"]
    runner.close()


def test_an_answer_that_takes_too_long_is_stopped_and_reported():
    model = FakeModel(delay=5)
    runner = ModelRunner(model, timeout=0.1)
    started = time.monotonic()
    with pytest.raises(ModelError, match="took longer than 0.1 seconds"):
        run(ask(runner))
    assert time.monotonic() - started < 2 and model.stopped_early
    runner.close()


def test_the_time_limit_counts_from_when_the_model_starts_not_from_when_it_was_asked():
    runner = ModelRunner(FakeModel(delay=0.15), timeout=0.4)

    async def main():
        return await asyncio.gather(ask(runner), ask(runner), ask(runner))

    assert len(run(main())) == 3  # the third waited 0.3 s and still had its full 0.4 s
    runner.close()


def test_a_failing_model_is_a_model_error():
    runner = ModelRunner(FakeModel(lambda m: ModelError("the model failed: out of memory")))
    with pytest.raises(ModelError, match="out of memory"):
        run(ask(runner))
    runner.close()


def test_an_unexpected_failure_is_reported_in_words():
    runner = ModelRunner(FakeModel(lambda m: RuntimeError("boom")))
    with pytest.raises(ModelError, match="boom"):
        run(ask(runner))
    runner.close()


def test_cancelling_the_question_stops_the_generation():
    model = FakeModel(delay=5)
    runner = ModelRunner(model)

    async def main():
        task = asyncio.create_task(ask(runner))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(main())
    runner.close()
    assert model.stopped_early


def test_closing_stops_a_running_generation_and_refuses_new_questions():
    model = FakeModel(delay=5)
    runner = ModelRunner(model)

    async def main():
        task = asyncio.create_task(ask(runner))
        await asyncio.sleep(0.1)
        await asyncio.to_thread(runner.close)
        with pytest.raises(ModelError):
            await task
        with pytest.raises(ModelError, match="shutting down"):
            await ask(runner)

    run(main())
    assert model.stopped_early


def test_the_limits_are_passed_on_to_the_model():
    model = FakeModel()
    runner = ModelRunner(model, max_new_tokens=33)
    run(ask(runner))
    runner.close()
    assert model.max_new_tokens == [33]


def test_the_limits_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        ModelRunner(FakeModel(), timeout=0)
    with pytest.raises(ValueError, match="positive"):
        ModelRunner(FakeModel(), max_new_tokens=0)
