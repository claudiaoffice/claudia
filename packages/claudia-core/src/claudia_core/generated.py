"""Generated paragraphs: a paragraph whose content the document derives, never stores (E9.31; step E of
``claudiaoffice-log/notes/text-structure-across-apps.md``).

A table of contents in a text, an agenda on a slide: the same thing. The paragraph stores only its options (a
:class:`Toc`); its entries are worked out from the headings by :class:`~claudia_core.TextStructure` (``entries``), so
there is nothing to update: a new heading, a retyped one, a moved section changes the entries for everybody at once.

* :class:`Toc` is the options: the heading levels listed, whether the entries carry the headings' numbers and their
  places (pages in a text, slide numbers in a presentation), and the leader drawn to the place.
* :class:`ContentsEntry` is one derived line: the heading it goes to, its level, its number, its words, the style it
  is drawn in (``contents-<level>`` where the document has it, else the generated paragraph's own) and its place, if
  the kernel knows it (a slide number; a page is the layout's).
* :class:`SetGenerated` makes a paragraph generated, changes its options or (``None``) makes it plain again. The model
  says how it finds the paragraph (:class:`GeneratedHost`). A generated paragraph has no words: typing into it is
  refused, as joining text into it is.
* :class:`GeneratedChanged` (wire type ``generated``) tells the clients the entries of a generated paragraph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Protocol

from .commands import Command, CommandRegistry, core_commands

if TYPE_CHECKING:
    from .context import Context
    from .region import Region

#: The style an entry of level ``n`` is drawn in, where the document has it (D306: the look is styles).
CONTENTS_STYLE = "contents-{level}"
#: The deepest heading level a table of contents can list (the deepest a style can give).
MAX_LEVEL = 9
LEADERS = ("dots", "none")


@dataclass(frozen=True)
class Toc:
    """The options of a table of contents (an agenda): the heading levels ``first`` to ``last`` it lists, whether
    an entry shows the heading's ``numbers`` and its ``places`` (page or slide), and the ``leader`` to the place."""

    kind: ClassVar[str] = "toc"
    first: int = 1
    last: int = 3
    numbers: bool = True
    places: bool = True
    leader: str = "dots"

    def check(self) -> None:
        """``ValueError`` with a sentence if the options make no sense."""
        for value in (self.first, self.last):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_LEVEL:
                raise ValueError(f"A table of contents lists heading levels 1 to {MAX_LEVEL}, got {value!r}")
        if self.first > self.last:
            raise ValueError(f"A table of contents lists levels {self.first} to {self.last}: the first is deeper")
        if not isinstance(self.numbers, bool) or not isinstance(self.places, bool):
            raise ValueError("Numbers and places are on or off")
        if self.leader not in LEADERS:
            raise ValueError(f"The leader is one of {', '.join(LEADERS)}, got {self.leader!r}")

    def lists(self, level: int | None) -> bool:
        """Does it list a heading of this level?"""
        return level is not None and self.first <= level <= self.last

    def to_data(self) -> dict:
        """The plain-data form that goes into snapshots, commands and events."""
        return {
            "kind": self.kind,
            "first": self.first,
            "last": self.last,
            "numbers": self.numbers,
            "places": self.places,
            "leader": self.leader,
        }

    @classmethod
    def from_data(cls, data: dict) -> Toc:
        """Inverse of ``to_data``."""
        return cls(data["first"], data["last"], data["numbers"], data["places"], data["leader"])


#: What a paragraph can be generated as, by kind. A list of figures or a bibliography is another kind, later.
type Generated = Toc
GENERATED_KINDS: dict[str, type[Toc]] = {Toc.kind: Toc}


def generated_from_data(data: dict) -> Generated:
    """A generated paragraph's options from their plain data; ``ValueError`` for a kind there is none of."""
    kind = GENERATED_KINDS.get(data.get("kind", ""))
    if kind is None:
        raise ValueError(f"A paragraph is generated as one of {', '.join(GENERATED_KINDS)}, got {data.get('kind')!r}")
    made = kind.from_data(data)
    made.check()
    return made


@dataclass(frozen=True)
class ContentsEntry:
    """One line of a table of contents: the heading it goes to (``target``, a paragraph id), its ``level``, its
    ``number`` (``None`` when unnumbered or numbers are off), its ``text``, the ``style`` it is drawn in and its
    ``place`` (the slide number in a presentation; ``None`` where the layout finds it, or places are off)."""

    target: str
    level: int
    number: str | None
    text: str
    style: str
    place: str | None = None

    def to_data(self) -> dict:
        """The plain-data form that is sent to clients."""
        return {
            "target": self.target,
            "level": self.level,
            "number": self.number,
            "text": self.text,
            "style": self.style,
            "place": self.place,
        }


@dataclass(frozen=True)
class GeneratedChanged:
    """The entries of a generated paragraph, worked out again (or ``None``: it is generated no longer)."""

    paragraph: str
    entries: tuple[ContentsEntry, ...] | None

    def to_data(self) -> dict:
        """The plain-data form of the event, as sent to clients."""
        entries = None if self.entries is None else [entry.to_data() for entry in self.entries]
        return {"type": "generated", "paragraph": self.paragraph, "entries": entries}


class GeneratedHost(Protocol):
    """What :class:`SetGenerated` needs of a model: any of its paragraphs by id, whatever holds it."""

    def generated_of(self, paragraph_id: str) -> Generated | None:
        """The paragraph's options; ``KeyError`` (or ``ValueError``) if there is no such paragraph."""
        ...

    def put_generated(self, paragraph_id: str, generated: Generated | None) -> object:
        """Make the paragraph generated as ``generated`` says (``None``: plain again) and return the event that tells
        the clients. ``ValueError`` for a paragraph with words: only an empty one can be generated."""
        ...

    def item_regions(self, paragraph_id: str) -> tuple[Region, ...]:
        """What a change of the paragraph holds against others' edits."""
        ...


def _host(ctx: Context) -> GeneratedHost:
    model = ctx.model
    if not all(hasattr(model, name) for name in ("generated_of", "put_generated")):
        raise TypeError(f"The {model.app} model has no generated paragraphs")
    return model


@core_commands.register
@dataclass(frozen=True)
class SetGenerated(Command):
    """Make an empty paragraph a table of contents (an agenda), change its options, or (``None``) make it a plain
    paragraph again."""

    kind: ClassVar[str] = "core.SetGenerated"
    paragraph: str
    generated: Generated | None

    @property
    def label(self) -> str:
        return "Table of contents"

    @property
    def summary(self) -> str:
        if self.generated is None:
            return "removed a table of contents"
        return f"table of contents, levels {self.generated.first}–{self.generated.last}"

    def apply(self, ctx: Context) -> Command:
        host = _host(ctx)
        if self.generated is not None:
            self.generated.check()
        old = host.generated_of(self.paragraph)
        ctx.emit(host.put_generated(self.paragraph, self.generated))
        return SetGenerated(self.paragraph, old)

    def to_data(self) -> dict:
        return {"paragraph": self.paragraph, "generated": None if self.generated is None else self.generated.to_data()}

    @classmethod
    def from_data(cls, data: dict, registry: CommandRegistry) -> SetGenerated:
        options = data["generated"]
        return cls(data["paragraph"], None if options is None else generated_from_data(options))

    def regions(self, model: object) -> tuple[Region, ...]:
        regions = getattr(model, "item_regions", None)
        return () if regions is None else regions(self.paragraph)

    def shifted_by(self, other: Command) -> Command | None:
        return None if other.ends_paragraph(self.paragraph) else self
