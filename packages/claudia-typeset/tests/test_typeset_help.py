"""The help topic that every "LaTeX was not found" message points to (D76, E13.1, D90)."""

from importlib import resources

import pytest

from claudia_typeset import HELP_TOPIC, SETTINGS

MAX_CHARACTERS = 9_000  # a small local model must be able to read a topic whole (E13.4)


def read_topic():
    return (resources.files("claudia_typeset") / "help" / "configure-latex.md").read_text(encoding="utf-8")


def split(text):
    """Front matter (simple ``key: value`` lines between two ``---`` lines) and body."""
    assert text.startswith("---\n"), "a topic starts with its metadata"
    head, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body


@pytest.fixture(scope="module")
def topic():
    return split(read_topic())


def test_the_topic_has_the_id_that_the_error_messages_name(topic):
    meta, _ = topic
    assert meta["id"] == HELP_TOPIC


def test_the_title_is_a_task_phrased_as_a_question(topic):
    meta, _ = topic
    assert meta["title"].startswith("How do I")
    assert meta["title"].endswith("?")


@pytest.mark.parametrize("field", ["apps", "language", "tags", "explains"])
def test_the_metadata_is_complete(topic, field):
    meta, _ = topic
    assert meta.get(field), f"{field} is missing"


def test_it_explains_each_setting(topic):
    meta, body = topic
    for setting in SETTINGS:
        assert setting in meta["explains"]
        assert f"`{setting}`" in body


def test_it_has_a_worked_example(topic):
    _, body = topic
    assert "## Example" in body


def test_it_covers_every_system_and_the_pitfalls(topic):
    _, body = topic
    for word in ("Windows", "macOS", "Linux", "pdftocairo", "MiKTeX", "tlmgr"):
        assert word in body, word


def test_it_tells_miktex_users_to_switch_off_installing_on_the_fly(topic):
    """The typesetter has no network and no time for a download in the middle of a job."""
    _, body = topic
    assert "on the fly" in body


def test_it_is_short_enough_to_be_read_whole():
    assert len(read_topic()) <= MAX_CHARACTERS


def test_its_steps_are_numbered(topic):
    _, body = topic
    assert "\n1. " in body
    assert "\n2. " in body
