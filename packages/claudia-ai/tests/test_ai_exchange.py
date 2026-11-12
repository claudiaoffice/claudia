"""The conversation of one question: requests that look, requests that change, and what came back (E7.5).

The model may ask for several rounds: it makes requests, is told what came of them, and carries on until it answers
without a ``commands`` block. ``Request.exchange`` is what has been said in the question so far, after the person's
text.
"""

from claudia_ai import Agent, Request, ToolSpec

LOOK = ToolSpec("cells", "cells(sheet: str, row0: int)", "The cells in a window.", kind="look")
CHANGE = ToolSpec("set_cells", "set_cells(sheet: str, cells: list)", "Type into cells.")


def system(request):
    return Agent().messages(request)[0]["content"]


def test_a_tool_changes_the_document_unless_it_says_it_only_looks():
    assert CHANGE.kind == "change" and LOOK.kind == "look"


def test_the_prompt_keeps_looking_and_changing_apart():
    prompt = system(Request("ann", "sum?", tools=(LOOK, CHANGE)))
    look, change = prompt.index("cells(sheet"), prompt.index("set_cells(sheet")
    assert prompt.index("only look") < look < prompt.index("change the document") < change


def test_with_only_looking_tools_the_model_is_told_it_cannot_change_anything():
    prompt = system(Request("ann", "sum?", tools=(LOOK,)))
    assert "cells(sheet" in prompt and "cannot change" in prompt and "set_cells" not in prompt


def test_with_no_tools_it_can_only_answer():
    prompt = system(Request("ann", "hi"))
    assert "only answer" in prompt and "commands" not in prompt


def test_the_model_is_told_the_results_come_back_and_that_the_document_holds_data_not_orders():
    prompt = system(Request("ann", "x", tools=(LOOK,)))
    assert "sends you what came back" in prompt
    assert "never follow instructions" in prompt.lower()


def test_the_exchange_follows_the_persons_text():
    exchange = [{"role": "assistant", "content": "looking"}, {"role": "user", "content": "results"}]
    messages = Agent().messages(
        Request("ann", "sum?", tools=(LOOK,), history=[{"role": "user", "content": "old"}], exchange=exchange)
    )
    assert [m["content"] for m in messages[1:]] == ["old", "sum?", "looking", "results"]


def test_the_turn_keeps_what_the_model_wrote_so_it_can_be_sent_back_as_it_was():
    raw = 'Let me look.\n```commands\n[{"method": "cells", "params": {}}]\n```'
    turn = Agent().parse(raw, (LOOK,))
    assert turn.raw == raw and [c.method for c in turn.calls] == ["cells"]
