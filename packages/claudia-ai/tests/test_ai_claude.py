"""Claude as a language model (E7.11): the Messages API through a stand-in for Anthropic that runs on this computer."""

import threading
import time

import pytest

from claudia_ai import ClaudeModel, FailureReason, ModelError, ProviderError
from claudia_ai.testing import FakeAnthropic

KEY = "sk-ant-test-a7Q2"


@pytest.fixture
def anthropic():
    with FakeAnthropic(key=KEY, answer=lambda messages: "B7 divides by C7, which is empty.") as fake:
        yield fake


def claude(fake, **options):
    return ClaudeModel(KEY, "claude-sonnet-5-5", base_url=fake.url, **options)


def ask(model, messages=None, stop=lambda: False):
    return model.generate(messages or [{"role": "user", "content": "why?"}], max_new_tokens=300, stop=stop)


def test_claude_answers_and_says_it_sends_content_out(anthropic):
    model = claude(anthropic)
    assert ask(model) == "B7 divides by C7, which is empty."
    assert model.remote is True
    assert model.name == "Claude · claude-sonnet-5-5"


def test_the_request_carries_the_key_the_model_and_the_conversation(anthropic):
    messages = [
        {"role": "system", "content": "You are ai."},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
    ask(claude(anthropic), messages)
    (sent,) = anthropic.requests
    assert sent.key == KEY
    assert sent.model == "claude-sonnet-5-5"
    assert sent.max_tokens == 300
    assert sent.system == "You are ai."
    assert sent.messages == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]


def test_messages_of_one_role_in_a_row_are_joined_because_the_api_wants_them_to_alternate(anthropic):
    messages = [{"role": "user", "content": "one"}, {"role": "user", "content": "two"}]
    ask(claude(anthropic), messages)
    assert anthropic.requests[0].messages == [{"role": "user", "content": "one\n\ntwo"}]


@pytest.mark.parametrize(
    ("fails", "reason"),
    [
        ("key_refused", FailureReason.KEY_REFUSED),
        ("credit_used_up", FailureReason.CREDIT_USED_UP),
        ("rate_limited", FailureReason.RATE_LIMITED),
        ("overloaded", FailureReason.OVERLOADED),
        ("unknown_model", FailureReason.UNKNOWN_MODEL),
    ],
)
def test_every_failure_of_anthropic_has_its_reason(anthropic, fails, reason):
    anthropic.fail(fails)
    with pytest.raises(ProviderError) as caught:
        ask(claude(anthropic))
    assert caught.value.reason is reason
    assert isinstance(caught.value, ModelError)


def test_a_failure_in_the_middle_of_the_stream_is_read_as_well(anthropic):
    anthropic.fail("overloaded", after_text="B7 divi")
    with pytest.raises(ProviderError) as caught:
        ask(claude(anthropic))
    assert caught.value.reason is FailureReason.OVERLOADED


def test_a_server_that_cannot_be_reached_is_unreachable():
    with FakeAnthropic(key=KEY) as fake:
        url = fake.url
    with pytest.raises(ProviderError) as caught:
        ask(ClaudeModel(KEY, "claude-sonnet-5-5", base_url=url))
    assert caught.value.reason is FailureReason.UNREACHABLE


def test_a_server_that_goes_quiet_is_a_timeout(anthropic):
    anthropic.go_quiet()
    started = time.monotonic()
    with pytest.raises(ProviderError) as caught:
        ask(claude(anthropic, read_timeout=0.2))
    assert caught.value.reason is FailureReason.TIMED_OUT
    assert time.monotonic() - started < 5


def test_the_person_is_told_in_one_sentence_and_the_key_is_never_in_it(anthropic):
    anthropic.fail("key_refused")
    with pytest.raises(ProviderError) as caught:
        ask(claude(anthropic))
    assert str(caught.value) == "Claude is not available at the moment. The administrator can see why."
    assert KEY not in str(caught.value) + caught.value.detail + repr(caught.value)


def test_stop_ends_a_running_answer_soon_with_what_there_is(anthropic):
    anthropic.answer = lambda messages: "word " * 200
    anthropic.pause_between_chunks = 0.05
    stopping = threading.Event()
    threading.Timer(0.2, stopping.set).start()
    started = time.monotonic()
    text = ask(claude(anthropic), stop=stopping.is_set)
    assert time.monotonic() - started < 3
    assert text.startswith("word")
    assert len(text) < len("word " * 200)


@pytest.mark.parametrize(
    ("reason", "sentence"),
    [
        (FailureReason.KEY_REFUSED, "Anthropic refused the key."),
        (FailureReason.CREDIT_USED_UP, "The credit balance at Anthropic is used up."),
        (FailureReason.RATE_LIMITED, "Anthropic's rate limit was reached."),
        (FailureReason.OVERLOADED, "Anthropic is overloaded at the moment."),
        (FailureReason.UNREACHABLE, "Anthropic cannot be reached from this server."),
        (FailureReason.UNKNOWN_MODEL, "Anthropic does not know the model “claude-x”."),
        (FailureReason.TIMED_OUT, "Anthropic did not answer within 60 seconds."),
    ],
)
def test_the_administrator_reads_each_reason_in_one_sentence(reason, sentence):
    assert reason.admin_sentence(model="claude-x", seconds=60) == sentence
