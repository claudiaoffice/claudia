"""The text structure every app shares (step C of claudiaoffice-log/notes/text-structure-across-apps.md).

An app says only which paragraphs it has, in the order they are read, and where each one is (a ``ParagraphHost``).
What follows from that, the label of every list item and the events that tell the clients, is worked out here, once,
so that composes and creates cannot count differently."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from claudia_core import (
    LabelsChanged,
    ListBook,
    ListDef,
    ListItem,
    Paragraph,
    Placed,
    StyleBook,
    StyleDef,
    TextStructure,
)


@dataclass
class Host:
    """A ParagraphHost by hand: containers in order, each with its paragraphs in the order they are read."""

    containers: dict[str, list[Paragraph]]
    lists: ListBook = field(default_factory=lambda: ListBook([ListDef("l1", "numbers"), ListDef("l2", "bullets")]))
    styles: StyleBook = field(default_factory=lambda: StyleBook([StyleDef("body", "Body", "", None, {})]))
    asides: frozenset[str] = frozenset()
    order: int = 0

    def reading_order(self):
        for container, paragraphs in self.containers.items():
            for paragraph in paragraphs:
                yield Placed(paragraph, container, container not in self.asides, None)

    @property
    def structure_version(self):
        return (self.order,)


def p(pid: str, item: ListItem | None = None) -> Paragraph:
    return Paragraph(pid, "body", pid, (), item)


class Events:
    def __init__(self):
        self.seen = []

    def emit(self, event):
        self.seen.append(event)


def test_a_list_counts_on_across_containers_in_the_order_they_are_read():
    host = Host({"s1": [p("t1", ListItem("l1")), p("x")], "s2": [p("t2", ListItem("l1")), p("t3", ListItem("l1", 1))]})
    labels = TextStructure(host).labels()
    assert {k: v.marker for k, v in labels.items()} == {"t1": "1.", "t2": "2.", "t3": "a."}
    assert labels["t3"].path == (2, 1)


def test_the_labels_are_worked_out_again_only_when_the_structure_or_the_lists_changed():
    host = Host({"s1": [p("t1", ListItem("l1"))]})
    structure = TextStructure(host)
    first = structure.labels()
    assert structure.labels() is first, "nothing changed: the same answer, not counted again"
    host.containers["s1"].append(p("t2", ListItem("l1")))
    assert structure.labels() is first, "the host has not said that its structure changed"
    host.order += 1
    assert {k: v.marker for k, v in structure.labels().items()} == {"t1": "1.", "t2": "2."}
    again = structure.labels()
    host.lists.replace(ListDef("l1", "numbers", start=5))
    assert structure.labels() is not again and structure.labels()["t1"].marker == "5."


def test_settling_tells_only_what_changed_and_a_label_that_went_away_as_none():
    host = Host({"s1": [p("t1", ListItem("l1")), p("t2", ListItem("l1"))]})
    structure = TextStructure(host)
    events = Events()
    structure.settle(events)
    assert events.seen == [], "the clients learn the first labels with the document"
    host.containers["s1"][0] = p("t1")
    host.order += 1
    structure.settle(events)
    (event,) = events.seen
    assert isinstance(event, LabelsChanged)
    assert event.to_data() == {"type": "labels", "labels": {"t1": None, "t2": {"marker": "1.", "path": [1]}}}
    structure.settle(events)
    assert len(events.seen) == 1, "nothing more to tell"


def test_a_paragraph_that_is_no_longer_there_is_not_told_about():
    host = Host({"s1": [p("t1", ListItem("l1"))], "s2": [p("t2", ListItem("l1"))]})
    structure = TextStructure(host)
    events = Events()
    del host.containers["s1"]
    host.order += 1
    structure.settle(events)
    assert events.seen[0].to_data()["labels"] == {"t2": {"marker": "1.", "path": [1]}}


def test_where_a_paragraph_is_read_and_whether_it_is_part_of_the_main_text_is_the_hosts_word():
    host = Host({"b1": [p("b1"), p("o1")]}, asides=frozenset())
    placed = list(TextStructure(host).reading_order())
    assert [(x.paragraph.id, x.container, x.main, x.place) for x in placed] == [
        ("b1", "b1", True, None),
        ("o1", "b1", True, None),
    ]


@pytest.mark.parametrize("item", [None, ListItem("l9")])
def test_a_paragraph_that_is_no_item_or_an_item_of_a_list_the_book_lacks_has_no_label(item):
    assert TextStructure(Host({"s1": [p("t1", item)]})).labels() == {}


def test_the_effective_item_of_a_paragraph_is_its_own():
    host = Host({"s1": [p("t1", ListItem("l1", 2))]})
    assert TextStructure(host).effective_item(host.containers["s1"][0]) == ListItem("l1", 2)
