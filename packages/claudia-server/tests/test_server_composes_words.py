"""The text by what it says (E7.10, D681): paragraphs by id and words by quoting them, so a language model can read
and write a text without counting characters."""

import pytest

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_server.apps import MODEL_METHODS, SUGGEST_METHODS
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.composes_words import MAX_READ, locate
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
VERA = Account("vera", "viewer")
AI = Account.assistant(MODEL_METHODS["composes"])


@pytest.fixture
def paper():
    return Document(TextModel(), store=MemoryStore())


def call(doc, name, params=None, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return composes_methods.dispatch(ctx, name, params or {})


def write(doc, *paragraphs):
    """The text with these paragraphs, typed by ann."""
    call(doc, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "\n".join(paragraphs)})


def texts(doc):
    return [block.text for block in doc.model.blocks]


def acting(role="editor", mode_writes=None):
    """The assistant's account for one question (D261): narrowed to the asker's role and her mode's writes."""
    return AI.acting_for(role, mode_writes)


# -- finding words
def test_words_are_found_by_quoting_them_and_an_occurrence_picks_one():
    assert locate("a cat and a cat", "cat", 1, "b1") == (2, 5)
    assert locate("a cat and a cat", "cat", 2, "b1") == (12, 15)
    assert locate("whole", "", 1, "b1") == (0, 5), "nothing quoted is the whole paragraph"


def test_words_that_are_not_there_say_so_and_ask_to_read_again():
    with pytest.raises(RequestError) as missing:
        locate("a cat", "dog", 1, "b1")
    assert "not in paragraph b1" in missing.value.message and "read it again" in missing.value.message
    with pytest.raises(RequestError) as too_far:
        locate("a cat", "cat", 2, "b1")
    assert "1 times" in too_far.value.message


# -- reading
def test_paragraphs_are_read_in_windows_with_their_ids_styles_and_what_follows(paper):
    write(paper, *[f"Line {n}" for n in range(1, 8)])
    first = call(paper, "paragraphs", {"count": 3})
    assert first["total"] == 7 and [p["text"] for p in first["paragraphs"]] == ["Line 1", "Line 2", "Line 3"]
    assert first["paragraphs"][0] == {"id": "b1", "index": 0, "style": "body", "text": "Line 1"}
    after = call(paper, "paragraphs", {"first": first["more"], "count": 10})
    assert [p["index"] for p in after["paragraphs"]] == [3, 4, 5, 6] and after["more"] is None


def test_paragraphs_containing_some_words_ignore_case(paper):
    write(paper, "The budget", "Other things", "budget again")
    found = call(paper, "paragraphs", {"containing": "BUDGET"})["paragraphs"]
    assert [p["text"] for p in found] == ["The budget", "budget again"]


def test_a_read_window_is_bounded(paper):
    with pytest.raises(RequestError):
        call(paper, "paragraphs", {"count": MAX_READ + 1})
    with pytest.raises(RequestError):
        call(paper, "paragraphs", {"first": "b99"})


def test_the_outline_is_the_headings(paper):
    write(paper, "Intro", "Some text.", "Method")
    blocks = paper.model.blocks
    call(paper, "set_style", {"block": blocks[0].id, "style": "heading-1"})
    call(paper, "set_style", {"block": blocks[2].id, "style": "heading-2"})
    outline = call(paper, "outline")
    assert [(h["text"], h["style"]) for h in outline["headings"]] == [("Intro", "heading-1"), ("Method", "heading-2")]


# -- writing
def test_replace_words_changes_the_quoted_words_only(paper):
    write(paper, "We met in order to plan, in order to act.")
    result = call(paper, "replace_words", {"block": "b1", "find": "in order to", "text": "to", "occurrence": 2})
    assert texts(paper) == ["We met in order to plan, to act."]
    assert result["block"] == "b1" and result["offset"] == len("We met in order to plan, to")


def test_replace_words_with_nothing_quoted_rewrites_the_paragraph_and_a_line_break_makes_two(paper):
    write(paper, "Old words.")
    call(paper, "replace_words", {"block": "b1", "find": "", "text": "First.\nSecond."})
    assert texts(paper) == ["First.", "Second."]


def test_replace_words_is_one_step_to_undo(paper):
    write(paper, "One two three.")
    call(paper, "replace_words", {"block": "b1", "find": "two", "text": "2\nand more"})
    call(paper, "undo")
    assert texts(paper) == ["One two three."]


def test_add_paragraphs_after_one_take_the_style_that_follows_or_the_one_given(paper):
    write(paper, "Title", "End.")
    call(paper, "set_style", {"block": "b1", "style": "heading-1"})
    added = call(paper, "add_paragraphs", {"after": "b1", "text": "New one.\nAnd another."})["paragraphs"]
    assert texts(paper) == ["Title", "New one.", "And another.", "End."]
    assert [paper.model.block(b).style for b in added] == ["body", "body"]
    quoted = call(paper, "add_paragraphs", {"after": added[-1], "text": "Said by someone.", "style": "quote"})
    assert paper.model.block(quoted["paragraphs"][0]).style == "quote"


def test_add_paragraphs_at_the_start(paper):
    write(paper, "Body.")
    added = call(paper, "add_paragraphs", {"text": "A title", "style": "title"})["paragraphs"]
    assert texts(paper) == ["A title", "Body."]
    assert [paper.model.block(b).style for b in added] == ["title"]
    assert paper.model.blocks[1].style == "body", "what was there keeps its style"


def test_add_paragraphs_refuses_a_style_a_paragraph_cannot_have(paper):
    with pytest.raises(RequestError):
        call(paper, "add_paragraphs", {"after": "b1", "text": "x", "style": "no-such-style"})
    assert texts(paper) == [""]


# -- the assistant (D262, D640, D681)
def test_the_assistant_writes_words_for_a_person_who_chose_act(paper):
    write(paper, "We utilize it.")
    call(paper, "replace_words", {"block": "b1", "find": "utilize", "text": "use"}, acting())
    call(paper, "set_style", {"block": "b1", "style": "quote"}, acting())
    call(paper, "add_paragraphs", {"after": "b1", "text": "More."}, acting())
    assert texts(paper) == ["We use it.", "More."] and paper.model.block("b1").style == "quote"
    runs = paper.model.block("b1").to_data()["runs"]
    assert any(run[1] == "ai" for run in runs), "what the AI wrote is the AI's"


def test_for_a_person_who_chose_suggest_the_assistant_can_only_propose(paper):
    write(paper, "We utilize it.")
    proposing = acting(mode_writes=SUGGEST_METHODS["composes"])
    for name, params in (
        ("replace_words", {"block": "b1", "find": "utilize", "text": "use"}),
        ("set_style", {"block": "b1", "style": "quote"}),
        ("add_paragraphs", {"after": "b1", "text": "x"}),
    ):
        with pytest.raises(RequestError) as refused:
            call(paper, name, params, proposing)
        assert refused.value.code == "forbidden"
    made = call(
        paper, "suggest_words", {"block": "b1", "find": "utilize", "replacement": "use", "reason": "plainer"}, proposing
    )
    (open_one,) = call(paper, "suggestions")
    assert open_one["id"] == made["suggestion"] and (open_one["start"], open_one["end"]) == (3, 10)
    assert texts(paper) == ["We utilize it."], "a suggestion changes no text"


def test_the_assistant_never_writes_more_than_the_asker_may(paper):
    write(paper, "Text.")
    with pytest.raises(RequestError) as refused:
        call(paper, "replace_words", {"block": "b1", "find": "", "text": "x"}, acting(role="viewer"))
    assert refused.value.code == "forbidden"


def test_offsets_are_never_written_for_a_person_who_chose_suggest(paper):
    with pytest.raises(RequestError):
        call(
            paper,
            "replace_text",
            {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "x"},
            acting(mode_writes=SUGGEST_METHODS["composes"]),
        )


def test_only_the_assistant_suggests_and_a_suggestion_stays_in_its_paragraph(paper):
    write(paper, "One.")
    with pytest.raises(RequestError):
        call(paper, "suggest_words", {"block": "b1", "find": "One", "replacement": "Two", "reason": "r"})
    with pytest.raises(RequestError) as across:
        call(paper, "suggest_words", {"block": "b1", "find": "One", "replacement": "A\nB", "reason": "r"}, acting())
    assert "inside its paragraph" in across.value.message


def test_a_viewer_reads_but_writes_nothing(paper):
    write(paper, "Text.")
    assert call(paper, "paragraphs", {}, VERA)["paragraphs"][0]["text"] == "Text."
    with pytest.raises(RequestError):
        call(paper, "replace_words", {"block": "b1", "find": "", "text": "x"}, VERA)


def test_mistakes_in_a_request_are_named(paper):
    write(paper, "Text.")
    for name, params in (
        ("replace_words", {"block": "b9", "find": "", "text": "x"}),
        ("replace_words", {"block": "b1", "find": "Text", "text": "x", "occurrence": 0}),
        ("add_paragraphs", {"after": "b1", "text": ""}),
        ("paragraphs", {"count": 0}),
    ):
        with pytest.raises(RequestError):
            call(paper, name, params)


def test_replacing_nothing_by_nothing_writes_nothing(paper):
    result = call(paper, "replace_words", {"block": "b1", "find": "", "text": ""})
    assert texts(paper) == [""] and (result["block"], result["offset"]) == ("b1", 0)
    assert not call(paper, "history")["can_undo"], "no step in the history"


def test_the_words_methods_are_for_texts_only():
    from claudia_computes import WorkbookModel

    sheet = Document(WorkbookModel(), store=MemoryStore())
    ctx = Context(sheet, ANN, Limits(), users=lambda: ["ann"], lock_seconds=30.0)
    with pytest.raises(RequestError):
        composes_methods.dispatch(ctx, "outline", {})
