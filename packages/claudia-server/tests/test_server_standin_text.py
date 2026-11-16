"""The scripted stand-in for the text app: it suggests, or in act mode writes (D640), and says when it understands
nothing."""

import pytest

from claudia_composes import InsertText, SetStyle, TextModel, TextRange
from claudia_core import Document, MemoryStore
from claudia_server.ai_mode import ACT
from claudia_server.assistant import Call, Say, Task
from claudia_server.standin_text import LONG_SENTENCE_WORDS, MAX_SUGGESTIONS, TextEngine


@pytest.fixture
def paper():
    return Document(TextModel(), store=MemoryStore())


def write(doc, text, block="b1", at=0):
    doc.execute(InsertText(block, at, text), author="ann")


def plan(doc, text="review this", sender="ann", mode=None):
    task = Task(sender, text, doc) if mode is None else Task(sender, text, doc, mode=mode)
    return TextEngine().plan(task)


def suggestions(steps):
    return [s for s in steps if isinstance(s, Call)]


def test_in_suggest_mode_it_only_suggests(paper):
    write(paper, "We recieve teh mail.")
    steps = plan(paper)
    assert steps and {s.method for s in suggestions(steps)} == {"suggest"}, "the asker decides what is written (D262)"


def test_in_act_mode_it_writes_its_replacements_from_the_end_of_a_paragraph(paper):
    write(paper, "We recieve teh mail.")
    calls = suggestions(plan(paper, mode=ACT))
    assert [(c.method, c.params["start"], c.params["end"], c.params["text"]) for c in calls] == [
        ("replace_text", 11, 14, "the"),
        ("replace_text", 3, 10, "receive"),
    ], "the later place first, so the earlier offsets still hold"
    assert all(c.params["block"] == c.params["end_block"] == "b1" for c in calls)


def test_in_act_mode_a_remark_without_a_replacement_stays_a_remark(paper):
    write(paper, " ".join(["word"] * (LONG_SENTENCE_WORDS + 2)) + ".")
    calls = suggestions(plan(paper, mode=ACT))
    assert [c.method for c in calls] == ["suggest"] and "replacement" not in calls[0].params


def test_in_act_mode_it_says_what_it_changed_and_how_to_take_it_back(paper):
    write(paper, "We recieve teh mail.")
    said = [s.text for s in plan(paper, mode=ACT) if isinstance(s, Say)]
    assert said == ["I changed 2 places; undo takes a change back."]


def test_spelling_wordiness_and_intensifiers_become_replacements(paper):
    write(paper, "In order to recieve it we utilize a very good plan.")
    found = {(c.params["start"], c.params["end"]): c.params["replacement"] for c in suggestions(plan(paper))}
    assert found == {(0, 11): "To", (12, 19): "receive", (26, 33): "use", (36, 41): ""}


def test_a_capital_letter_stays_a_capital_letter(paper):
    write(paper, "Prior to that, teh end. Teh start.")
    by_text = {c.params["replacement"] for c in suggestions(plan(paper))}
    assert by_text == {"Before", "the", "The"}


def test_a_long_sentence_gets_a_remark_not_a_replacement(paper):
    sentence = " ".join(["word"] * (LONG_SENTENCE_WORDS + 1)) + "."
    write(paper, sentence)
    (call,) = suggestions(plan(paper))
    assert call.params.get("replacement") is None and str(LONG_SENTENCE_WORDS + 1) in call.params["reason"]
    assert (call.params["start"], call.params["end"]) == (0, len(sentence))


def test_every_suggestion_says_where_it_is_working(paper):
    write(paper, "teh end")
    (call,) = suggestions(plan(paper))
    assert call.focus == (TextRange("b1", 0, 3).to_data(),)


def test_it_looks_at_all_paragraphs_with_the_right_offsets(paper):
    write(paper, "fine")
    paper.execute(SetStyle("b1", "body"), author="ann")
    from claudia_composes import SplitBlock

    paper.execute(SplitBlock("b1", 4, "b2", "body"), author="ann")
    write(paper, "so teh end", block="b2")
    (call,) = suggestions(plan(paper))
    assert (call.params["block"], call.params["start"], call.params["end"]) == ("b2", 3, 6)


def test_this_paragraph_means_the_one_the_asker_is_in(paper):
    from claudia_composes import SplitBlock

    write(paper, "teh first")
    paper.execute(SplitBlock("b1", 9, "b2", "body"), author="ann")
    write(paper, "teh second", block="b2")
    paper.show_presence("ann", [TextRange("b2", 0, 0)])
    assert {c.params["block"] for c in suggestions(plan(paper, "check this paragraph"))} == {"b2"}
    assert {c.params["block"] for c in suggestions(plan(paper, "check everything"))} == {"b1", "b2"}
    assert {c.params["block"] for c in suggestions(plan(paper, "review this text"))} == {"b1", "b2"}, "this text: all"


def test_it_does_not_suggest_again_what_is_already_open(paper):
    write(paper, "teh end")
    (call,) = suggestions(plan(paper))
    from claudia_composes import ProposeSuggestion

    paper.execute(ProposeSuggestion("s1", "b1", 0, 3, "teh", "the", call.params["reason"]), author="ai")
    steps = plan(paper)
    assert not suggestions(steps) and isinstance(steps[0], Say) and "nothing" in steps[0].text.casefold()


def test_it_says_when_it_finds_nothing(paper):
    write(paper, "All good here.")
    steps = plan(paper)
    assert len(steps) == 1 and isinstance(steps[0], Say) and "nothing" in steps[0].text.casefold()


def test_it_makes_at_most_so_many_suggestions_and_says_so(paper):
    write(paper, "teh " * (MAX_SUGGESTIONS + 5))
    steps = plan(paper)
    assert len(suggestions(steps)) == MAX_SUGGESTIONS
    assert isinstance(steps[-1], Say) and "more" in steps[-1].text


def test_overlapping_findings_make_one_suggestion(paper):
    write(paper, "In order to  be very sure.")  # wordiness and a double space meet at the edge, not inside
    spans = [(c.params["start"], c.params["end"]) for c in suggestions(plan(paper))]
    assert all(a[1] <= b[0] for a, b in zip(sorted(spans), sorted(spans)[1:], strict=False))


def test_help_and_the_unknown_are_answered_honestly(paper):
    (helped,) = plan(paper, "hello")
    assert isinstance(helped, Say) and "stand-in" in helped.text
    (lost,) = plan(paper, "write me a novel")
    assert isinstance(lost, Say) and "did not understand" in lost.text


# ----------------------------------------------------------------------------- with a real hub and assistant
def test_a_review_in_the_chat_ends_in_suggestions_people_can_accept():
    import asyncio
    import json

    from claudia_server.assistant import Assistant
    from claudia_server.auth import Account
    from claudia_server.composes import composes_methods
    from claudia_server.hub import Hub, MemoryProvider

    async def run():
        hosted = await Hub(MemoryProvider(TextModel), methods=composes_methods).open("essay", create=True)
        assistant = Assistant(TextEngine(), pause=0, allowed_methods=("suggest",), suggest_methods=("suggest",))
        assistant.attach(hosted)
        frames: list[dict] = []
        ann = hosted.connect(Account("ann", "owner"), lambda text: frames.append(json.loads(text)))

        def request(method, params=None):
            ann.handle(json.dumps({"id": len(frames) + 1000, "method": method, "params": params}))
            return frames[-1]

        request("replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "We recieve mail."})
        request("chat", {"text": "@ai please proofread", "ai_mode": "suggest"})
        await assistant.idle()
        (item,) = request("suggestions")["result"]
        assert (item["author"], item["original"], item["replacement"]) == ("ai", "recieve", "receive")
        assert request("blocks")["result"]["blocks"][0]["text"] == "We recieve mail.", "nothing written yet"
        request("accept_suggestion", {"id": item["id"]})
        block = request("blocks")["result"]["blocks"][0]
        assert block["text"] == "We receive mail." and [7, "ann", "ai"] in block["runs"]

    asyncio.run(run())
