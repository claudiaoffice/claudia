"""The AI's lens on a presentation (E7.9, D265): slides and their objects in the words a person uses, and every change
reported as a re-read of the slides it touched.

A slide is 1600 by 900 units, the top left corner is (0, 0). The model is told so, with the slides and what is on the
first few, and the ids it needs: a slide's id for ``add_object``, an object's id for ``set_text``, ``move_object``
and the rest. Text on a slide is somebody's text, so it is fenced as data like everything else that comes out of a
document (``lens.fence``).

Not here yet (D265): the model cannot see that text overflows its box (E10.13), and it is not shown a picture of a
slide (E10.9, E7.5).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from claudia_core import Document, ObjectsChanged
from claudia_creates import SlideModel
from claudia_creates.events import SlidesChanged
from claudia_creates.model import SLIDE_HEIGHT, SLIDE_WIDTH

from .lens import fence, shorten

MAX_LISTED_SLIDES = 40  # slides named to the model; a small model has little room
PREVIEW_SLIDES = 3  # slides whose objects are shown at the start
MAX_OBJECTS = 30  # objects of one slide described
MAX_TEXT = 80  # characters of one object's words shown
KINDS = {
    "text": "text box",
    "shape": "shape",
    "image": "picture",
    "diagram": "chart",
    "rendered": "rendered text (picture made from text)",  # D340
}

ORIENTATION = (
    "A slide is {w} units wide and {h} high; x and y are the top left corner of an object, from the top left of the "
    "slide. Everything must stay on the slide. A text box's words follow a paragraph style (body-text by default), a "
    "shape is drawn from an outline of the shapes list (circle, rectangle, triangle, ...).{example}"
)
EXAMPLE = (
    ' A request looks like {{"method": "add_object", "params": {{"slide": "s1", "kind": "text", "x": 160, "y": 120, '
    '"w": 1280, "h": 160, "text": "Agenda"}}}}.'
)  # left out when the asker's mode or role lets the AI change nothing: it would only invite a refused request


def describe_object(data: dict) -> str:
    """One object for the model: ``o1a2b text box at (160, 120) 1280×160, words body-text: "Agenda"``."""
    kind = KINDS.get(data.get("kind", ""), data.get("kind", "object"))
    anchor = data.get("anchor") or {}
    line = f"{data['id']} {kind}"
    if data.get("shape"):
        line += f" ({data['shape']})"
    line += f" at ({anchor.get('x')}, {anchor.get('y')}) {data.get('w')}×{data.get('h')}, style {data.get('style')}"
    words = data.get("paragraph")
    if words is not None:
        line += f", words {words.get('style')}"
        if words.get("text"):
            line += ': "' + shorten(" ".join(str(words["text"]).split()), MAX_TEXT) + '"'
    if data.get("rotation"):
        line += f", turned {data['rotation']}°"
    return line


def describe_slide(model: SlideModel, slide: str) -> str:
    """A slide and its objects, the one in front last."""
    objects = model.objects_on(slide)
    head = f"{slide} ({len(objects)} object{'s' if len(objects) != 1 else ''})"
    lines = [describe_object(obj.to_data()) for obj in objects[:MAX_OBJECTS]]
    if len(objects) > MAX_OBJECTS:
        lines.append(f"... and {len(objects) - MAX_OBJECTS} more objects")
    return "\n".join([head, *("  " + line for line in lines)])


class SlideLens:
    """The lens for creates."""

    look_methods: tuple[str, ...] = ("slides", "slide", "shapes", "styles")

    # -- where the model starts
    def orient(self, document: Document, *, can_write: bool) -> str:
        """How a slide is measured, the slides with how many objects, and what is on the first few."""
        model = document.model
        assert isinstance(model, SlideModel)
        text = ORIENTATION.format(w=SLIDE_WIDTH, h=SLIDE_HEIGHT, example=EXAMPLE if can_write else "")
        slides = list(model.slides)
        if not slides:
            return text + "\nThere are no slides yet: add one with add_slide."
        names = [f"{s} ({len(model.objects_on(s))})" for s in slides[:MAX_LISTED_SLIDES]]
        if len(slides) > MAX_LISTED_SLIDES:
            names.append(f"... and {len(slides) - MAX_LISTED_SLIDES} more")
        text += "\nSlides in order (id (objects)): " + ", ".join(names)
        shown = [describe_slide(model, s) for s in slides[:PREVIEW_SLIDES]]
        return text + "\nThe first slides:\n" + fence("\n".join(shown))

    # -- what the read requests show
    def show(self, method: str, params: dict, result: Any) -> str:
        """The answer of a read request, fenced as data and without what a model cannot use (outline paths)."""
        if method == "slides":
            return fence("\n".join(f"{s['id']} ({s['objects']} objects)" for s in result) or "There are no slides.")
        if method == "slide":
            lines = [describe_object(obj) for obj in result["objects"][:MAX_OBJECTS]] or ["(empty)"]
            return fence(f"{result['slide']}:\n" + "\n".join(lines))
        if method == "shapes":
            names = [f"{s['id']} ({s['name']})" for s in result["library"]]
            return fence("Shapes you can add (the shape parameter of add_object): " + ", ".join(names))
        if method == "styles":
            return fence(self._styles(result))
        return fence(json.dumps(result, separators=(",", ":"), ensure_ascii=False))

    @staticmethod
    def _styles(result: Any) -> str:
        styles = result.get("styles", result) if isinstance(result, dict) else result
        lines = []
        for style in styles:
            purpose = shorten(style.get("purpose") or "", MAX_TEXT)
            lines.append(
                f"{style['id']}: {style.get('name', '')} ({style.get('kind', 'paragraph')}) {purpose}".rstrip()
            )
        return "Styles (id: name (kind) what it is for); words take a paragraph style:\n" + "\n".join(lines)

    # -- what a change did
    def recorder(self, document: Document) -> SlideRecorder:
        """Hold round one write request."""
        return SlideRecorder(document)


class SlideRecorder:
    """Listens while one request runs, then re-reads the slides it touched (D265: the report is a re-read)."""

    def __init__(self, document: Document):
        self._document = document
        self._slides: list[str] = []
        self._removed: list[str] = []
        self._slides_changed = False
        self._stop: Callable[[], None] | None = None

    def __enter__(self) -> SlideRecorder:
        self._stop = self._document.subscribe(self._hear)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._stop is not None:
            self._stop()
            self._stop = None

    def _hear(self, event: object) -> None:
        if isinstance(event, ObjectsChanged):
            if event.container not in self._slides:
                self._slides.append(event.container)
            self._removed += [r for r in event.removed if r not in self._removed]
        elif isinstance(event, SlidesChanged):
            self._slides_changed = True

    def report(self) -> str:
        """The touched slides as they are now, and what was taken away; fenced as data."""
        model = self._document.model
        assert isinstance(model, SlideModel)
        lines = []
        if self._slides_changed:
            lines.append("The slides are now: " + (", ".join(model.slides) or "none"))
        lines += [describe_slide(model, s) for s in self._slides if s in model.slides]
        if self._removed:
            lines.append("Removed: " + ", ".join(self._removed))
        return fence("\n".join(lines) or "Nothing changed.")


__all__ = ["SlideLens", "SlideRecorder", "describe_object", "describe_slide"]
