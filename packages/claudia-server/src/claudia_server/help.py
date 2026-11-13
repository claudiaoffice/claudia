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

``apps``, ``tags`` and ``explains`` are comma-separated lists; every other field is one line of text.

D99's draft is the real format now (E13.1): this module is what makes that so, not a change to the file. A topic
missing ``id`` or ``title`` is refused when the library loads — help is not optional for what ships it, the same
spirit as a function refused for having no description (``claudia_computes.functions.registry``): a maintainer sees
the mistake at once, never a user who searched and found nothing.

A topic can be translated (E13.8, D294): a second file next to it, ``writing-a-formula.de.md``, with the same ``id``,
its own ``language`` and ``source-hash``, the fingerprint of the English file it was made from
(:attr:`Topic.fingerprint`). ``HelpLibrary.stale`` lists the translations whose source has changed since, and a test
fails on any. Search and ``get`` give the translation in the language asked for and the English topic where there is
none.

The body is kept as Markdown but shown as plain text for now: full LaTeX/Markdown rendering through the
typesetting service (D30, D88) is further out than this iteration, which only needed the format settled and the
topics searchable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = ("id", "title")
SOURCE_LANGUAGE = "en"


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
    source_hash: str = ""  # of a translation: the fingerprint of the English file it was made from
    fingerprint: str = field(default="", compare=False)  # of this file's own text (line endings do not count)

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
    text = text.replace("\r\n", "\n")
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
    language = meta.get("language", "").strip() or SOURCE_LANGUAGE
    if language != SOURCE_LANGUAGE and not meta.get("source-hash"):
        raise HelpContentError(
            f"{source}: a translation says which English text it was made from (source-hash: the fingerprint)"
        )
    return Topic(
        id=meta["id"],
        title=meta["title"],
        apps=_list(meta.get("apps", "")),
        language=language,
        tags=_list(meta.get("tags", "")),
        explains=_list(meta.get("explains", "")),
        body=body.strip(),
        source_hash=meta.get("source-hash", ""),
        fingerprint=_fingerprint(text),
    )


def _fingerprint(text: str) -> str:
    """Twelve hex digits that change when the text of a topic file does; a different line ending does not."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:12]


class HelpLibrary:
    """Every help topic the server has loaded, searchable by text (E13.3's "search by text"; lookup by id and by
    context, E13.3's other two, are :meth:`get` and still to come). Built once, read by many requests. A topic can
    exist in several languages (E13.8); one id, one topic per language, and English is the one that always exists."""

    def __init__(self, topics: Iterable[Topic] = ()):
        self._topics: dict[tuple[str, str], Topic] = {}
        for topic in topics:
            self.add(topic)

    def add(self, topic: Topic) -> None:
        """Add one topic. Refuses (:class:`HelpContentError`) if its id is already taken in its language."""
        key = (topic.id, topic.language)
        if key in self._topics:
            raise HelpContentError(f"two topics share the id {topic.id!r} in the language {topic.language!r}")
        self._topics[key] = topic

    def check(self) -> None:
        """Refuse (:class:`HelpContentError`) a translation whose English topic is not there. Not done by
        :meth:`add`: a folder lists ``how.de.md`` before ``how.md``, so the source may come second."""
        for id_, language in self._topics:
            if language != SOURCE_LANGUAGE and (id_, SOURCE_LANGUAGE) not in self._topics:
                raise HelpContentError(f"the {language!r} topic {id_!r} has no English topic to translate")

    def stale(self) -> list[tuple[str, str]]:
        """``(id, language)`` of every translation made from an English text that has changed since (E13.8)."""
        return sorted(
            (id_, language)
            for (id_, language), topic in self._topics.items()
            if language != SOURCE_LANGUAGE
            and (id_, SOURCE_LANGUAGE) in self._topics
            and topic.source_hash != self._topics[(id_, SOURCE_LANGUAGE)].fingerprint
        )

    def load_folder(self, folder: Path) -> None:
        """Every ``*.md`` file directly in ``folder`` (not recursive: a help folder is flat), in name order, so
        loading the same folder twice always gives the same result. Does nothing for a folder that is not there."""
        if not folder.is_dir():
            return
        for path in sorted(folder.glob("*.md")):
            self.add(parse_topic(path.read_text(encoding="utf-8"), source=str(path)))

    def __len__(self) -> int:
        return len(self._topics)

    def _languages(self, language: str) -> tuple[str, ...]:
        """The languages to look in for ``language`` (a locale tag), best first: itself, its language without region,
        English."""
        return tuple(dict.fromkeys((language, language.split("-", 1)[0], SOURCE_LANGUAGE)))

    def _ids(self) -> list[str]:
        return sorted({id_ for id_, _language in self._topics})

    def get(self, topic_id: str, language: str = SOURCE_LANGUAGE) -> Topic | None:
        """The topic with this id in ``language`` (a locale tag such as ``de-AT``), else in English; ``None`` if
        there is no such topic."""
        for candidate in self._languages(language):
            found = self._topics.get((topic_id, candidate))
            if found is not None:
                return found
        return None

    def search(self, query: str, *, app: str | None = None, language: str = SOURCE_LANGUAGE) -> list[Topic]:
        """Topics whose title, tags or ``explains`` contain ``query`` (case-insensitive), by title; every topic, by
        title, if ``query`` is blank. Each topic is shown once, in ``language`` where it has been translated and in
        English where not; a query matches the words of both, since a person may know the English name of what they
        look for. Full-text search over the body is future work (E13.3 proposes SQLite FTS5); a handful of short
        topics does not need it yet.

        ``app``, when given, keeps only topics that name it in their own ``apps`` front matter, or that name no app
        at all (a topic with an empty ``apps`` is for every app). This is what keeps one app's results from
        showing another's: a topic says who it is for itself, in its own file, rather than this method needing a
        table of which id belongs to which app."""
        needle = query.strip().casefold()
        found = []
        for id_ in self._ids():
            shown = self.get(id_, language)
            source = self._topics.get((id_, SOURCE_LANGUAGE))
            if shown is None or (needle and not self._matches(shown, source, needle)):
                continue
            if app is None or not shown.apps or app in shown.apps:
                found.append(shown)
        return sorted(found, key=lambda topic: topic.title)

    @staticmethod
    def _matches(topic: Topic, source: Topic | None, needle: str) -> bool:
        words = (topic.title, *topic.tags, *topic.explains)
        if source is not None and source is not topic:
            words = (*words, source.title, *source.tags, *source.explains)
        return needle in " ".join(words).casefold()


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
        library.check()
        _default_library = library
    return _default_library
