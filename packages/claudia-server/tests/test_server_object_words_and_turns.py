"""Tests first for D1232 (not built yet): the words of a text box or a shape are written the same way in every app that
has them, and a table is not turned. Each test is ``xfail(strict=True)``: it flips to a failure, and so has to lose the
mark, the day the thing is built.

* creates has ``set_text`` and ``write_words``; composes has the same typing model for the words of its floating
  objects (``claudia_core.TypingHost``, D181) but registers neither method, so the browser cannot save the words of a
  text box there. The methods belong with ``add_object`` (``shape_methods``), where both apps get them.
* ``rotate_object`` is shared by the three apps (``object_methods``); a chart does not turn, and a table, which is in
  the flow of the text (D1224), does not either, but the server only refuses the chart.
"""

import pytest

from claudia_composes import TextModel
from claudia_core import Document, MemoryStore
from claudia_server.auth import Account
from claudia_server.composes import composes_methods
from claudia_server.protocol import Context, Limits, RequestError

ANN = Account("ann", "owner")
BEN = Account("ben", "editor")
NOT_BUILT = pytest.mark.xfail(strict=True, reason="D1232 is not built yet")


@pytest.fixture
def paper():
    document = Document(TextModel(), store=MemoryStore())
    call(
        document, "replace_text", {"block": "b1", "start": 0, "end_block": "b1", "end": 0, "text": "a text with a box"}
    )
    return document


def call(doc, name, params=None, account=ANN):
    ctx = Context(doc, account, Limits(), users=lambda: ["ann", "ben"], lock_seconds=30.0)
    return composes_methods.dispatch(ctx, name, params)


def add_box(doc, kind="text", **params):
    given = {"block": "b1", "offset": 2, "kind": kind, "w": 200, "h": 80, **params}
    return call(doc, "add_object", given)["object"]


def words_of(doc, object_id):
    (found,) = [o for o in call(doc, "objects")["objects"] if o["id"] == object_id]
    return found["paragraph"]


@NOT_BUILT
@pytest.mark.parametrize("kind", ["text", "shape"])
def test_the_words_of_a_box_in_a_text_are_written_as_typed_so_the_words_that_stay_keep_their_writer(paper, kind):
    box = add_box(paper, kind, **({"shape": "rectangle"} if kind == "shape" else {}))
    call(paper, "set_text", {"id": box, "text": "Why we did it"})
    same = call(paper, "write_words", {"id": box, "text": "Why we did it"}, account=BEN)["revision"]
    assert same == paper.revision.to_data(), "the same words are no step at all"
    call(paper, "write_words", {"id": box, "text": "Why we really did it"}, account=BEN)
    found = words_of(paper, box)
    assert found["text"] == "Why we really did it"
    assert [(r[0], r[1]) for r in found["runs"]] == [(7, "ann"), (7, "ben"), (6, "ann")]
    assert paper.history_for("ben").undo_label == "Edit text"


@NOT_BUILT
def test_a_picture_in_a_text_has_no_words_to_write(paper):
    picture = call(
        paper,
        "add_image",
        {
            "block": "b1",
            "offset": 1,
            "w": 4,
            "h": 4,
            "data": "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
            "alt": "a dot",
            "source_name": "dot.gif",
        },
    )["object"]
    with pytest.raises(RequestError, match="no text"):
        call(paper, "write_words", {"id": picture, "text": "x"})


@NOT_BUILT
def test_a_table_does_not_turn_on_the_server_either(paper):
    table = call(paper, "add_table", {"block": "b1", "offset": 4, "cells": [["a", "b"], ["c", "d"]]})["object"]
    with pytest.raises(RequestError, match="table does not turn"):
        call(paper, "rotate_object", {"id": table, "rotation": 90})


def test_a_chart_in_no_app_and_a_box_in_a_text_turn_like_everywhere(paper):
    """What stays: any whole number of degrees, read modulo a turn (the three apps share one implementation)."""
    box = add_box(paper)
    call(paper, "rotate_object", {"id": box, "rotation": -20})
    (found,) = [o for o in call(paper, "objects")["objects"] if o["id"] == box]
    assert found["rotation"] == 340
