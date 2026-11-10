"""Help topics: short, example-oriented "how do I" guides, loaded and searched (E13.1, E13.3; D76, D99).

A topic is a Markdown file with simple front matter — exactly the shape ``claudia_typeset/help/configure-latex.md``
shipped as a draft (D99) before this module existed to read it: a block of ``key: value`` lines between two
``---`` lines, then the body::

    ---
    id: computes.writing-a-formula
    title: How do I write a formula?
    apps: computes
    language: en
    tags: formula, cell, reference
    explains: =, SUM
    ---
    ... the body, in Markdown ...

``apps``, ``tags`` and ``explains`` are comma-separated lists; every other field is one line of text. D99's draft is
the real format now (E13.1): this module is what makes that so, not a change to the file. A topic missing ``id`` or
``title`` is refused when the library loads — help is not optional for what ships it, the same spirit as a function
refused for having no description (``claudia_computes.functions.registry``): a maintainer sees the mistake at once,
never a user who searched and found nothing.

The body is kept as Markdown but shown as plain text for now: full LaTeX/Markdown rendering through the
typesetting service (D30, D88) is further out than this iteration, which only needed the format settled and the
topics searchable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REQUIRED = ("id", "title")


class HelpContentError(ValueError):
    """A help topic file is not well formed, or two topics claim the same id. The message says which and why."""


@dataclass(frozen=True, slots=True)
class Topic:
    """One help topic. ``body`` is Markdown, shown as plain text for now (see the module docstring)."""

    id: str
    title: str
    apps: tuple[str, ...]
    language: str
    tags: tuple[str, ...]
    explains: tuple[str, ...]
    body: str

    def summary(self) -> dict:
        """What a search result shows: everything but the body."""
        return {"id": self.id, "title": self.title, "apps": list(self.apps), "tags": list(self.tags)}

    def to_data(self) -> dict:
        """The whole topic, once one has been picked by id."""
        return {**self.summary(), "language": self.language, "explains": list(self.explains), "body": self.body}


def _list(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def parse_topic(text: str, *, source: str = "<topic>") -> Topic:
    """One topic, from the text of its file. Raises :class:`HelpContentError` with ``source`` in the message when
    the front matter is missing, unclosed, not ``key: value``, or has no ``id`` or ``title``."""
    if not text.startswith("---\n"):
        raise HelpContentError(f"{source}: a topic starts with '---', its front matter")
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        raise HelpContentError(f"{source}: the closing '---' of the front matter is missing")
    meta: dict[str, str] = {}
    for line in head.splitlines():
        if not line.strip():
            continue
        key, colon, value = line.partition(":")
        if not colon:
            raise HelpContentError(f"{source}: {line!r} is not a 'key: value' line of the front matter")
        meta[key.strip()] = value.strip()
    missing = [field for field in REQUIRED if not meta.get(field)]
    if missing:
        raise HelpContentError(f"{source}: the topic has no {missing[0]}")
    return Topic(
        id=meta["id"],
        title=meta["title"],
        apps=_list(meta.get("apps", "")),
        language=meta.get("language", "").strip() or "en",
        tags=_list(meta.get("tags", "")),
        explains=_list(meta.get("explains", "")),
        body=body.strip(),
    )


class HelpLibrary:
    """Every help topic the server has loaded, searchable by text (E13.3's "search by text"; lookup by id and by
    context, E13.3's other two, are :meth:`get` and still to come). Built once, read by many requests."""

    def __init__(self, topics: Iterable[Topic] = ()):
        self._topics: dict[str, Topic] = {}
        for topic in topics:
            self.add(topic)

    def add(self, topic: Topic) -> None:
        """Add one topic. Refuses (:class:`HelpContentError`) if its id is already taken."""
        if topic.id in self._topics:
            raise HelpContentError(f"two topics share the id {topic.id!r}")
        self._topics[topic.id] = topic

    def load_folder(self, folder: Path) -> None:
        """Every ``*.md`` file directly in ``folder`` (not recursive: a help folder is flat), in name order, so
        loading the same folder twice always gives the same result. Does nothing for a folder that is not there."""
        if not folder.is_dir():
            return
        for path in sorted(folder.glob("*.md")):
            self.add(parse_topic(path.read_text(encoding="utf-8"), source=str(path)))

    def __len__(self) -> int:
        return len(self._topics)

    def get(self, topic_id: str) -> Topic | None:
        """The topic with this id, or ``None``."""
        return self._topics.get(topic_id)

    def search(self, query: str) -> list[Topic]:
        """Topics whose title, tags or ``explains`` contain ``query`` (case-insensitive), by title; every topic, by
        title, if ``query`` is blank. Full-text search over the body is future work (E13.3 proposes SQLite FTS5); a
        handful of short topics does not need it yet."""
        needle = query.strip().casefold()
        topics = self._topics.values()
        found = list(topics) if not needle else [topic for topic in topics if self._matches(topic, needle)]
        return sorted(found, key=lambda topic: topic.title)

    @staticmethod
    def _matches(topic: Topic, needle: str) -> bool:
        haystack = " ".join((topic.title, *topic.tags, *topic.explains)).casefold()
        return needle in haystack


def _package_help_folders() -> list[Path]:
    """The ``help/`` folder of every installed package that ships one. D76(2) ("every extension brings its own
    help") is why this list exists at all rather than one folder: today it is a fixed set of package names because
    composes and creates have no extension point yet (D29) to register one from; the day one exists, it adds a
    name here instead of this function growing a discovery mechanism nobody asked for yet."""
    from importlib import resources

    found = []
    for name in ("claudia_typeset", "claudia_computes", "claudia_composes", "claudia_creates"):
        try:
            folder = resources.files(name) / "help"
        except ModuleNotFoundError:
            continue
        if folder.is_dir():
            found.append(Path(str(folder)))
    return found


_default_library: HelpLibrary | None = None


def default_library() -> HelpLibrary:
    """The help library built from every installed package's own ``help/`` folder, built once and reused (the
    same lazy-singleton shape as ``claudia_computes.model.default_functions``)."""
    global _default_library  # noqa: PLW0603
    if _default_library is None:
        library = HelpLibrary()
        for folder in _package_help_folders():
            library.load_folder(folder)
        _default_library = library
    return _default_library
