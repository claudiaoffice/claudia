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


# ------------------------------------------------------------------------------------ translations (E13.8, D294)
ENGLISH_FILE = """---
id: a.how
title: How do I do it?
apps: computes
tags: do, it
explains: DOIT()
---
Do it like this.
"""


def german_file(source_hash: str, *, title="Wie mache ich es?") -> str:
    return (
        f"---\nid: a.how\ntitle: {title}\nlanguage: de\nsource-hash: {source_hash}\napps: computes\n"
        "tags: machen, es\n---\nSo wird es gemacht.\n"
    )


def library_with_german() -> HelpLibrary:
    english = parse_topic(ENGLISH_FILE)
    return HelpLibrary([english, parse_topic(german_file(english.fingerprint))])


def test_a_translation_shares_the_id_of_its_source_and_names_the_text_it_was_made_from():
    english = parse_topic(ENGLISH_FILE)
    german = parse_topic(german_file(english.fingerprint))
    assert (german.id, german.language, german.source_hash) == ("a.how", "de", english.fingerprint)
    assert english.source_hash == ""


def test_the_fingerprint_follows_the_text_of_the_file_not_its_line_endings():
    assert parse_topic(ENGLISH_FILE).fingerprint == parse_topic(ENGLISH_FILE.replace("\n", "\r\n")).fingerprint
    assert parse_topic(ENGLISH_FILE).fingerprint != parse_topic(ENGLISH_FILE + "More.\n").fingerprint


def test_a_library_holds_one_topic_per_id_and_language():
    english = parse_topic(ENGLISH_FILE)
    with pytest.raises(HelpContentError, match="a.how.*de"):
        HelpLibrary([english, parse_topic(german_file(english.fingerprint)), parse_topic(german_file("x"))])


def test_a_translation_needs_its_source():
    german = parse_topic(german_file("abc"))
    with pytest.raises(HelpContentError, match="a.how.*English"):
        HelpLibrary([german]).check()


def test_a_translation_says_which_text_it_was_made_from():
    with pytest.raises(HelpContentError, match="source-hash"):
        parse_topic("---\nid: a.how\ntitle: Wie?\nlanguage: de\n---\nText")


def test_get_gives_the_translation_where_there_is_one_and_english_where_there_is_not():
    library = library_with_german()
    assert library.get("a.how", "de").title == "Wie mache ich es?"
    assert library.get("a.how", "de-AT").language == "de"  # a region falls back to its language
    assert library.get("a.how", "en").title == "How do I do it?"
    assert library.get("a.how", "fr").title == "How do I do it?"
    assert library.get("a.how").title == "How do I do it?"


def test_search_shows_each_topic_once_in_the_language_asked_for():
    library = library_with_german()
    assert [t.title for t in library.search("", language="de")] == ["Wie mache ich es?"]
    assert [t.title for t in library.search("", language="fr")] == ["How do I do it?"]


def test_search_in_german_finds_the_german_words_and_the_english_ones():
    library = library_with_german()
    assert [t.id for t in library.search("machen", language="de")] == ["a.how"]
    assert [t.id for t in library.search("DOIT", language="de")] == ["a.how"]  # what it explains is not translated
    assert library.search("machen", language="en") == []


def test_a_translation_older_than_its_source_is_flagged():
    library = library_with_german()
    assert library.stale() == []
    changed = HelpLibrary([parse_topic(ENGLISH_FILE + "A new paragraph.\n"), library.get("a.how", "de")])
    assert changed.stale() == [("a.how", "de")]


def test_load_folder_reads_the_translations_next_to_their_sources(tmp_path):
    english = parse_topic(ENGLISH_FILE)
    (tmp_path / "how.md").write_text(ENGLISH_FILE, encoding="utf-8")
    (tmp_path / "how.de.md").write_text(german_file(english.fingerprint), encoding="utf-8")
    library = HelpLibrary()
    library.load_folder(tmp_path)
    assert library.get("a.how", "de").body == "So wird es gemacht."


def test_every_shipped_translation_is_as_new_as_its_source():
    """E13.8: a topic that changed makes its translations stale; this is the check that says so in CI. Fix by
    translating the change and setting ``source-hash`` to the English topic's fingerprint (it is in the message)."""
    library = default_library()
    library.check()
    stale = [(id_, language, library.get(id_).fingerprint) for id_, language in library.stale()]
    assert stale == [], f"translations older than their source (id, language, new source-hash): {stale}"


def test_the_shipped_topics_are_all_in_german():
    library = default_library()
    english = {topic.id for topic in library.search("")}
    assert english, "no topics shipped"
    assert {topic.id for topic in library.search("", language="de") if topic.language == "de"} == english
