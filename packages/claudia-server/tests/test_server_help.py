"""The help library: loading topics from their front matter, and searching them (E13.1, E13.3)."""

from __future__ import annotations

import pytest

from claudia_server.help import HelpContentError, HelpLibrary, Topic, default_library, parse_topic

TOPIC_TEXT = """---
id: computes.example-topic
title: How do I do the thing?
apps: computes
language: en
tags: thing, example
explains: THING()
---
Do the thing. For example `=THING()` gives 1.
"""


def test_parse_topic_reads_every_field():
    topic = parse_topic(TOPIC_TEXT)
    assert topic == Topic(
        id="computes.example-topic",
        title="How do I do the thing?",
        apps=("computes",),
        language="en",
        tags=("thing", "example"),
        explains=("THING()",),
        body="Do the thing. For example `=THING()` gives 1.",
    )


def test_parse_topic_defaults_language_to_en_and_allows_no_tags_or_explains():
    topic = parse_topic("---\nid: a.b\ntitle: How?\n---\nbody text")
    assert topic.language == "en"
    assert topic.apps == ()
    assert topic.tags == ()
    assert topic.explains == ()


@pytest.mark.parametrize(
    "text,words",
    [
        ("no front matter at all", ["starts with"]),
        ("---\nid: a.b\ntitle: How?\nbody with no closing marker", ["closing"]),
        ("---\nnot a key value line\n---\nbody", ["key: value"]),
        ("---\ntitle: How?\n---\nbody", ["id"]),
        ("---\nid: a.b\n---\nbody", ["title"]),
    ],
)
def test_parse_topic_refuses_what_is_not_well_formed(text, words):
    with pytest.raises(HelpContentError) as excinfo:
        parse_topic(text, source="t.md")
    assert "t.md" in str(excinfo.value)
    for word in words:
        assert word in str(excinfo.value)


def topic(id_, title="How?", **kw):
    return Topic(
        id=id_,
        title=title,
        apps=kw.get("apps", ()),
        language="en",
        tags=kw.get("tags", ()),
        explains=kw.get("explains", ()),
        body="",
    )


def test_a_library_refuses_two_topics_with_the_same_id():
    library = HelpLibrary([topic("a.b")])
    with pytest.raises(HelpContentError, match="a.b"):
        library.add(topic("a.b"))


def test_get_finds_a_topic_by_id_and_gives_none_for_an_unknown_one():
    library = HelpLibrary([topic("a.b")])
    assert library.get("a.b").id == "a.b"
    assert library.get("a.c") is None


def test_search_with_no_query_gives_every_topic_sorted_by_title():
    library = HelpLibrary([topic("a.b", title="Zebra"), topic("a.c", title="Antelope")])
    assert [t.title for t in library.search("")] == ["Antelope", "Zebra"]


def test_search_matches_the_title_tags_or_explains_case_insensitively():
    library = HelpLibrary(
        [
            topic("a.b", title="Looking things up", tags=("lookup",)),
            topic("a.c", title="Summing", explains=("SUMIF",)),
            topic("a.d", title="Unrelated"),
        ]
    )
    assert [t.id for t in library.search("lookup")] == ["a.b"]
    assert [t.id for t in library.search("sumif")] == ["a.c"]
    assert library.search("nothing matches this") == []


def test_load_folder_does_nothing_for_a_folder_that_does_not_exist(tmp_path):
    library = HelpLibrary()
    library.load_folder(tmp_path / "no-such-folder")
    assert len(library) == 0


def test_load_folder_reads_every_markdown_file_and_skips_other_files(tmp_path):
    (tmp_path / "one.md").write_text(TOPIC_TEXT, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a topic", encoding="utf-8")
    library = HelpLibrary()
    library.load_folder(tmp_path)
    assert len(library) == 1
    assert library.get("computes.example-topic") is not None


def test_default_library_loads_the_real_computes_and_typeset_topics():
    library = default_library()
    assert library.get("typeset.configure-latex") is not None  # D99's long-standing draft file
    assert any(t.id.startswith("computes.") for t in library.search(""))  # this iteration's new topics
