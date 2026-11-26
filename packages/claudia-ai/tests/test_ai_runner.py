"""One model for the whole server: one question at a time, off the event loop, with a time limit."""

import asyncio
import threading

import pytest

from claudia_ai import ModelError, ModelRunner, ModelTimeout, Request
from claudia_ai.testing import FakeModel, FakeTime


def ask(runner, text="hi"):
    return runner.answer(Request("ann", text))


def run(coro):
    return asyncio.run(coro)


def test_the_answer_is_read_into_a_turn():
    runner = ModelRunner(FakeModel(lambda m: "Hello, " + m[-1]["content"]))
    assert run(ask(runner, "Ann")).say == "Hello, Ann"
    runner.close()


def test_generating_does_not_block_the_event_loop():
    model = FakeModel()
    model.hold()
    runner = ModelRunner(model)

    async def main():
        task = asyncio.create_task(ask(runner))
        await model.begun()
        working = not task.done()  # the loop runs this while the model is held: it was not blocked
        model.let_go()
        await task
        return working

    assert run(main()), "the loop kept running while the model worked"
    assert model.threads and threading.current_thread() not in model.threads, "the model works on its own thread"
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
    clock = FakeTime()
    model = FakeModel(delay=5, clock=clock)
    runner = ModelRunner(model, timeout=0.1, clock=clock)
    with pytest.raises(ModelError, match="took longer than 0.1 seconds"):
        run(ask(runner))
    assert model.stopped_early and clock.now < 0.2, "stopped at the limit, not when the model was done"
    runner.close()


def test_the_time_limit_counts_from_when_the_model_starts_not_from_when_it_was_asked():
    clock = FakeTime()
    model = FakeModel(delay=0.15, clock=clock)
    model.hold()  # all three are asked before the first is answered
    runner = ModelRunner(model, timeout=0.4, clock=clock)

    async def main():
        answers = asyncio.gather(ask(runner), ask(runner), ask(runner))
        await model.begun()
        model.let_go()
        return await answers

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
    model = FakeModel()
    model.hold()
    runner = ModelRunner(model)

    async def main():
        task = asyncio.create_task(ask(runner))
        await model.begun()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(main())
    runner.close()
    assert model.stopped_early


def test_closing_stops_a_running_generation_and_refuses_new_questions():
    model = FakeModel()
    model.hold()
    runner = ModelRunner(model)

    async def main():
        task = asyncio.create_task(ask(runner))
        await model.begun()
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


def test_the_runner_says_which_model_it_holds():
    model = FakeModel()
    runner = ModelRunner(model)
    assert runner.name == model.name
    runner.close()


def test_a_question_after_close_is_refused_in_words():
    runner = ModelRunner(FakeModel())
    runner.close()
    with pytest.raises(ModelError, match="shutting down"):
        run(ask(runner))


def test_a_question_that_waited_when_the_worker_ended_is_refused_in_words():
    runner = ModelRunner(FakeModel())
    runner._executor.shutdown()  # the worker ends while the server still takes questions: the executor says so
    with pytest.raises(ModelError, match="shutting down"):
        run(ask(runner))


def test_a_question_whose_time_ran_out_before_it_began_is_not_asked():
    model = FakeModel()
    runner = ModelRunner(model, timeout=1e-9)
    with pytest.raises(ModelTimeout):
        run(ask(runner))
    assert model.calls == []
    runner.close()
