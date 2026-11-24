"""Who receives and may ask for what in a live document: the roles of the file, applied to the session (D1261, SEC-17).

A document file has three separately encrypted parts, its **content**, its **history** and its **chat**, and a role
holds the keys of some of them (D101, ``claudia_document_file.ROLE_PARTS``): a viewer holds the content key only. The
live session must not give a viewer what her key would not open, so every event the server pushes and every method it
answers belongs to one of those parts, and this module says which.

Two tables, one rule:

* ``EVENT_RULES`` classifies every kind of pushed event once; ``EPHEMERAL_RULES`` does it for the kinds of the
  ``ephemeral`` event. ``shape_for`` applies them. What nobody classified goes to owners and editors only, so a new
  event can leak nothing by being forgotten; a test (``test_server_audience.py``) fails until it is listed.
* A protocol method says what it reads (``reads=`` on ``MethodTable.method``, ``content`` unless stated), and a viewer
  is refused one that reads a part her role does not hold (``MethodTable.dispatch``).

The apps and the kernel know nothing of this; they raise their events and register their methods as before.
"""

from __future__ import annotations

from dataclasses import dataclass

from claudia_document_file import ROLE_PARTS, Part, Role

CONTENT, HISTORY, CHAT = Part.CONTENT, Part.HISTORY, Part.CHAT


@dataclass(frozen=True)
class Rule:
    """The part an event's whole payload belongs to, and what of it a role that does not hold that part still
    receives (``None``: none of it; the keys that stay otherwise)."""

    part: Part
    viewer_keeps: tuple[str, ...] | None = None


_CONTENT = Rule(CONTENT)

# Every kind of event a window can be sent, by the name it travels under (the ``event`` of the frame; the kernel and
# the apps name it in the ``type`` of their payload). The app events (the first block) are the document's content.
EVENT_RULES: dict[str, Rule] = {
    **dict.fromkeys(
        (
            "paragraph_fields",
            "paragraph_generated",
            "cell_styles",
            "cells",
            "charts",
            "diagram",
            "fields",
            "generated",
            "image",
            "item",
            "join",
            "labels",
            "language",
            "lists",
            "names",
            "objects",
            "page",
            "palette",
            "pivots",
            "print_setup",
            "random",
            "container",
            "schemes",
            "shape",
            "sizes",
            "slide_notes",
            "slide_time",
            "slides",
            "split",
            "structure",
            "style",
            "styles",
            "suggestions",
            "table",
            "tabs",
            "text",
            "thing_described",
            "thing_renamed",
        ),
        _CONTENT,
    ),
    # What the kernel and the hub say about the document itself.
    "rebuilt": _CONTENT,  # "reload": the state was rebuilt (no word of why)
    "stale": _CONTENT,  # functions the document uses changed
    "render_result": _CONTENT,  # what the last try to draw a container said
    "joined": _CONTENT,  # the names of the people in the document (D111) and presence
    "left": _CONTENT,
    "ephemeral": _CONTENT,  # by its ``kind``, below
    # A command reaches a viewer as the revision alone: not who made it, when, why or how it was labelled.
    "command": Rule(HISTORY, viewer_keeps=("type", "revision")),
    # A restore or switch reaches a viewer as "reload"; which line it came from and went to is the history.
    "branch": Rule(HISTORY, viewer_keeps=("type",)),
    "history": Rule(HISTORY),  # a person's undo state
    "checkpoint": Rule(HISTORY),
    "redacted": Rule(HISTORY),  # the viewer's reload comes with the `rebuilt` that follows
    "restore_proposed": Rule(HISTORY),
    "restore_resolved": Rule(HISTORY),
    "chat": Rule(CHAT),
}

# The kinds of the ``ephemeral`` event (what is not stored). Presence and the names are not secrets of the history.
EPHEMERAL_RULES: dict[str, Part] = {
    "presence": CONTENT,
    "person_left": CONTENT,
    "owner_changed": CONTENT,
    "role_changed": CONTENT,  # an owner changed somebody's role: {user, role}
    "person_removed": CONTENT,  # an owner removed somebody: {user}
    "document_deleted": CONTENT,
    "details_changed": CONTENT,
    "ai_consent_changed": CONTENT,  # the owners allowed or withdrew a remote AI provider (E7.11): all may know
    "audit_recorded": HISTORY,  # somebody exported, printed or saved a PDF (D1271): the record is history
    "typing": CHAT,  # somebody is writing a chat message
}


def may_read(role: str, part: Part) -> bool:
    """Does a person with this role hold the key of ``part`` (the file's table, D101)? A role nobody knows holds the
    least, a viewer's."""
    try:
        held = ROLE_PARTS[Role(role)]
    except ValueError:
        held = ROLE_PARTS[Role.VIEWER]
    return part in held


def shape_for(role: str, event: str, data: dict) -> dict | None:
    """What a connection of ``role`` receives of the pushed event ``event`` with this payload: the payload itself,
    less than that, or ``None`` for nothing.

    Whoever holds every key (owners, editors) gets everything, an event nobody has classified too. Everybody else gets
    what the tables allow, and nothing of what they do not list."""
    if may_read(role, HISTORY) and may_read(role, CHAT):
        return data
    rule = EVENT_RULES.get(event)
    if rule is None:
        return None
    if event == "ephemeral":
        part = EPHEMERAL_RULES.get(str(data.get("kind")))
        return data if part is not None and may_read(role, part) else None
    if may_read(role, rule.part):
        return data
    if rule.viewer_keeps is None:
        return None
    return {key: data[key] for key in rule.viewer_keeps if key in data}
