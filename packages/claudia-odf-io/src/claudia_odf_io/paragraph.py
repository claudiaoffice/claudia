"""The text of one ODF paragraph, and changing it in place (D401).

A paragraph of the model is plain text. A paragraph of an ODF file is that text cut into spans and links, with
bookmarks, footnotes, fields and frames standing between the characters, and with spaces, tabs and line breaks
written as elements because ODF collapses white space like HTML does. This module reads the text of such a
paragraph and changes it **in place**: only the characters that differ are edited, every element stays where it
was, and a changed word costs the paragraph none of its links, its bold or its footnotes. That is what makes an
edited file still the file it was (D401).

What counts as text: the characters of the paragraph, of its spans, links and meta elements, and of ruby bases;
``text:s``, ``text:tab`` and ``text:line-break`` as the spaces, tab and newline they stand for. Everything else is
**not text** and is never read, edited or removed here: bookmarks, change marks and soft page breaks (they show
nothing), and notes, fields, frames and comments (they show something that is not characters of this paragraph).

White space follows ODF: a run of literal white space is one space, and none at the start or end of the paragraph
counts. So that the text of a paragraph read back is exactly the text that was written, every space the new text
needs that a reader would collapse is written as ``text:s``.

Everything here works on a *copy* of a paragraph element (see :mod:`claudia_odf_io.splice`): change the copy,
then replace the original with it.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from lxml import etree

from .names import NS

_TEXT = NS["text"]
_WHITE = " \t\r\n"
#: What cannot be written in an XML 1.0 document at all; it becomes U+FFFD, so a stray control character in a text
#: cannot make a file that no program opens.
_NOT_XML = re.compile("[^\x09\x0a\x0d\x20-퟿-�\U00010000-\U0010ffff]")
_TOKEN = re.compile(r"\w+|\s+|[^\w\s]")
#: The most token pairs the diff of one paragraph compares; beyond it the paragraph is diffed as one block between
#: its common start and end, which changes more of its markup but cannot take long.
_DIFF_LIMIT = 4_000_000


def _t(name: str) -> str:
    return f"{{{_TEXT}}}{name}"


_DESCEND = {_t(name) for name in ("span", "a", "meta", "meta-field", "ruby", "ruby-base")}
_SPACE, _TAB, _BREAK = _t("s"), _t("tab"), _t("line-break")
#: Elements that sit in the text and show nothing, or nothing in the line: they never get in the way of text.
_MARKERS = {
    _t(name)
    for name in (
        "bookmark",
        "bookmark-start",
        "bookmark-end",
        "reference-mark",
        "reference-mark-start",
        "reference-mark-end",
        "change",
        "change-start",
        "change-end",
        "soft-page-break",
        "alphabetical-index-mark",
        "alphabetical-index-mark-start",
        "alphabetical-index-mark-end",
        "toc-mark",
        "toc-mark-start",
        "toc-mark-end",
        "user-index-mark",
        "user-index-mark-start",
        "user-index-mark-end",
        "ruby-text",
    )
} | {f"{{{NS['office']}}}annotation", f"{{{NS['office']}}}annotation-end"}


def xml_safe(text: str) -> str:
    """``text`` with every character an XML file cannot hold replaced by U+FFFD."""
    return _NOT_XML.sub("�", text)


@dataclass(frozen=True)
class _Piece:
    """One thing a paragraph's text is made of, in order: a stretch of characters (``text``: the ``attr`` of
    ``owner``, which is ``"text"`` or ``"tail"``), a run of spaces, a tab, a line break, or something shown that is
    no character of the paragraph (``visible``: a field, a note, a frame)."""

    kind: str
    owner: etree._Element
    attr: str = ""

    def value(self) -> str:
        return getattr(self.owner, self.attr) or ""

    def size(self) -> int:
        match self.kind:
            case "text":
                return len(self.value())
            case "space":
                return int(self.owner.get(f"{{{_TEXT}}}c") or 1)
            case "tab" | "break":
                return 1
        return 0


def _kind(child: etree._Element) -> str:
    tag = child.tag
    if not isinstance(tag, str):
        return "marker"  # a comment or a processing instruction
    if tag in _DESCEND:
        return "descend"
    return {_SPACE: "space", _TAB: "tab", _BREAK: "break"}.get(tag) or ("marker" if tag in _MARKERS else "visible")


def _walk(parent: etree._Element) -> Iterator[_Piece]:
    if parent.text:
        yield _Piece("text", parent, "text")
    for child in parent:
        kind = _kind(child)
        if kind == "descend":
            yield from _walk(child)
        elif kind != "marker":
            yield _Piece(kind, child)
        if child.tail:
            yield _Piece("text", child, "tail")


# -- reading -------------------------------------------------------------------------------------------------------
def _collapsed(paragraph: etree._Element) -> list[tuple[_Piece, str]]:
    """Every piece with the string it has once white space is collapsed the way ODF says: a run is one space, none
    at the start of the paragraph, none at its end."""
    out: list[tuple[_Piece, str]] = []
    after_space = True  # the start of a paragraph counts as white space
    ends_in_literal = False
    for piece in _walk(paragraph):
        if piece.kind == "text":
            kept: list[str] = []
            for char in piece.value():
                if char in _WHITE:
                    if after_space:
                        continue
                    kept.append(" ")
                    after_space = ends_in_literal = True
                else:
                    kept.append(char)
                    after_space = ends_in_literal = False
            out.append((piece, "".join(kept)))
        else:  # a run of spaces, a tab, a break, a field: shown, so the white space after it is its own
            out.append((piece, ""))
            after_space = ends_in_literal = False
    if ends_in_literal:
        for index in range(len(out) - 1, -1, -1):
            if out[index][1]:
                out[index] = (out[index][0], out[index][1][:-1])
                break
    return out


def read_text(paragraph: etree._Element) -> str:
    """The text of ``paragraph`` (a ``text:p`` or ``text:h``)."""
    out = []
    for piece, collapsed in _collapsed(paragraph):
        match piece.kind:
            case "text":
                out.append(collapsed)
            case "space":
                out.append(" " * piece.size())
            case "tab":
                out.append("\t")
            case "break":
                out.append("\n")
    return "".join(out)


def hidden_content(paragraph: etree._Element) -> list[str]:
    """What ``paragraph`` shows that its text cannot: ``"footnote"``, ``"endnote"``, ``"field"``, ``"frame"``,
    ``"comment"`` or ``"ruby"``, one entry for each, in the order they come."""
    found: list[str] = []
    draw, office = f"{{{NS['draw']}}}", f"{{{NS['office']}}}"

    def visit(parent: etree._Element) -> None:
        for child in parent:
            tag = child.tag
            if not isinstance(tag, str):
                continue
            if tag == _t("ruby-text"):
                found.append("ruby")
            elif tag == f"{office}annotation":
                found.append("comment")
            elif tag == _t("note"):
                found.append(child.get(f"{{{_TEXT}}}note-class") or "footnote")
            elif tag in _DESCEND:
                visit(child)
            elif _kind(child) == "visible":
                found.append("frame" if tag.startswith(draw) else "field")

    visit(paragraph)
    return found


# -- changing ----------------------------------------------------------------------------------------------------
def _put(owner: etree._Element, attr: str, value: str) -> None:
    setattr(owner, attr, value or None)


def _drop(element: etree._Element, name: str) -> None:
    """Take the attribute ``text:name`` off ``element`` if it has it."""
    if (key := _t(name)) in element.attrib:
        del element.attrib[key]


def _el(name: str, **attributes: str) -> etree._Element:
    element = etree.Element(_t(name), nsmap={"text": _TEXT})
    for key, value in attributes.items():
        element.set(_t(key), value)
    return element


def _space(count: int) -> etree._Element:
    return _el("s", **({"c": str(count)} if count > 1 else {}))


def _encode(text: str) -> list[str | etree._Element]:
    """``text`` as what goes into a paragraph: strings, and the elements that tabs and line breaks need."""
    items: list[str | etree._Element] = []
    buffer: list[str] = []
    for char in text.replace("\r\n", "\n").replace("\r", "\n"):
        if char in "\t\n":
            if buffer:
                items.append("".join(buffer))
                buffer = []
            items.append(_el("tab" if char == "\t" else "line-break"))
        else:
            buffer.append(char)
    if buffer:
        items.append("".join(buffer))
    return items


def _write(owner: etree._Element, attr: str, head: str, items: list[str | etree._Element], rest: str) -> None:
    """Set what the slot ``attr`` of ``owner`` holds to ``head``, then ``items`` (strings and elements, in order),
    then ``rest``. Elements go where the slot is: a ``"text"`` slot is before the first child, a ``"tail"`` slot is
    right behind its owner."""
    if attr == "text":
        container, position = owner, 0
    else:
        parent = owner.getparent()
        assert parent is not None  # a tail belongs to a child, which has a parent
        container, position = parent, parent.index(owner) + 1
    slot: tuple[etree._Element, str] = (owner, attr)
    buffer = head
    for item in items:
        if isinstance(item, str):
            buffer += item
            continue
        _put(*slot, buffer)
        container.insert(position, item)
        position += 1
        slot, buffer = (item, "tail"), ""
    _put(*slot, buffer + rest)


def _slot_before(element: etree._Element) -> tuple[etree._Element, str, int]:
    """The place for text that goes right before ``element``: the end of what precedes it."""
    previous = element.getprevious()
    if previous is not None:
        return previous, "tail", len(previous.tail or "")
    parent = element.getparent()
    assert parent is not None
    return parent, "text", len(parent.text or "")


def _remove_keeping_tail(element: etree._Element) -> None:
    parent = element.getparent()
    assert parent is not None
    tail = element.tail
    previous = element.getprevious()
    parent.remove(element)
    if tail:
        if previous is not None:
            previous.tail = (previous.tail or "") + tail
        else:
            parent.text = (parent.text or "") + tail


def _located(paragraph: etree._Element) -> list[tuple[_Piece, int, int]]:
    out, offset = [], 0
    for piece in _walk(paragraph):
        size = piece.size()
        out.append((piece, offset, offset + size))
        offset += size
    return out


def _prune(paragraph: etree._Element, containers: set[etree._Element]) -> None:
    """Take out the spans and links that a deletion has emptied, and the ones they were inside."""
    for container in containers:
        current: etree._Element | None = container
        while current is not None and current is not paragraph and current.tag in {_t("span"), _t("a")}:
            if len(current) or current.text:
                break
            parent = current.getparent()
            _remove_keeping_tail(current)
            current = parent


def _delete(paragraph: etree._Element, start: int, stop: int) -> None:
    containers: set[etree._Element] = set()
    for piece, first, last in reversed(_located(paragraph)):
        low, high = max(start, first), min(stop, last)
        if low >= high:
            continue
        match piece.kind:
            case "text":
                value = piece.value()
                _put(piece.owner, piece.attr, value[: low - first] + value[high - first :])
                containers.add(piece.owner if piece.attr == "text" else piece.owner.getparent())  # type: ignore[arg-type]
            case "space":
                left = piece.size() - (high - low)
                if left > 0:
                    if left > 1:
                        piece.owner.set(f"{{{_TEXT}}}c", str(left))
                    else:
                        _drop(piece.owner, "c")
                else:
                    containers.add(piece.owner.getparent())  # type: ignore[arg-type]
                    _remove_keeping_tail(piece.owner)
            case _:  # a tab or a line break
                containers.add(piece.owner.getparent())  # type: ignore[arg-type]
                _remove_keeping_tail(piece.owner)
    _prune(paragraph, containers)


def _split_space(element: etree._Element, keep: int) -> None:
    """Cut the run of spaces ``element`` into ``keep`` spaces and the rest, as two elements."""
    total = int(element.get(f"{{{_TEXT}}}c") or 1)
    rest = _space(total - keep)
    rest.tail, element.tail = element.tail, None
    parent = element.getparent()
    assert parent is not None
    parent.insert(parent.index(element) + 1, rest)
    if keep > 1:
        element.set(f"{{{_TEXT}}}c", str(keep))
    else:
        _drop(element, "c")


def _insert(paragraph: etree._Element, at: int, text: str) -> None:
    _place(paragraph, at, _encode(text))


def _place(paragraph: etree._Element, at: int, items: list[str | etree._Element]) -> None:
    """Put ``items`` (text and elements, see :func:`_write`) into ``paragraph`` where its character ``at`` is."""
    located = [(piece, first, last) for piece, first, last in _located(paragraph) if last > first]
    if not located:
        _write(paragraph, "text", paragraph.text or "", items, "")
        return
    if at == 0:
        piece = located[0][0]
        if piece.kind == "text":
            _write(piece.owner, piece.attr, "", items, piece.value())
        else:
            owner, attr, index = _slot_before(piece.owner)
            value = getattr(owner, attr) or ""
            _write(owner, attr, value[:index], items, value[index:])
        return
    piece, first, last = next((item for item in located if item[1] < at <= item[2]), located[-1])
    if piece.kind == "text":
        value = piece.value()
        _write(piece.owner, piece.attr, value[: at - first], items, value[at - first :])
        return
    if piece.kind == "space" and at < last:
        _split_space(piece.owner, at - first)
    _write(piece.owner, "tail", "", items, piece.owner.tail or "")


def insert_elements(paragraph: etree._Element, placements: Sequence[tuple[int, etree._Element]]) -> None:
    """Put each element of ``placements`` into ``paragraph`` (a copy, see the module description) between the
    characters at its offset, inside the span or link that is there. Elements for the same offset go in the order
    they are given. They are meant for what shows nothing -- change marks, bookmarks -- so the text is the same
    afterwards."""
    by_offset: dict[int, list[etree._Element]] = {}
    for offset, element in placements:
        by_offset.setdefault(offset, []).append(element)
    for offset in sorted(by_offset, reverse=True):  # from the end, so a place that is still to come does not move
        _place(paragraph, offset, list(by_offset[offset]))


def _classified(paragraph: etree._Element) -> list[tuple[_Piece, int, str]]:
    """Every character and every other piece of the paragraph, in order, as ``(piece, index in the piece, class)``:
    ``ch`` for a character that is not a space, ``lit`` for a plain space, ``sp`` for a ``text:s``, and ``wall`` for
    what ends a stretch of text (a tab, a line break, a marker)."""
    stream: list[tuple[_Piece, int, str]] = []
    for piece in _walk(paragraph):
        if piece.kind == "text":
            stream.extend((piece, index, "lit" if char == " " else "ch") for index, char in enumerate(piece.value()))
        elif piece.kind == "space":
            stream.append((piece, 0, "sp"))
        else:
            stream.append((piece, 0, "ch" if piece.kind == "visible" else "wall"))
    return stream


def _rewritten_spaces(piece: _Piece, indices: set[int]) -> list[str | etree._Element]:
    """The text of ``piece`` with the plain spaces at ``indices`` written as ``text:s`` elements."""
    items: list[str | etree._Element] = []
    buffer: list[str] = []
    run = 0
    for index, char in enumerate(piece.value()):
        if index in indices:
            if buffer:
                items.append("".join(buffer))
                buffer = []
            run += 1
            continue
        if run:
            items.append(_space(run))
            run = 0
        buffer.append(char)
    if buffer:
        items.append("".join(buffer))
    if run:
        items.append(_space(run))
    return items


def _normalise_spaces(paragraph: etree._Element) -> None:
    """Write as ``text:s`` every plain space that a reader would collapse: one next to another space, or at the
    start or end of the paragraph, or next to a tab or a line break. Spaces that are fine are left as they are."""
    stream = _classified(paragraph)
    convert: dict[_Piece, set[int]] = {}
    for position, (piece, index, kind) in enumerate(stream):
        if kind != "lit":
            continue
        before = stream[position - 1][2] if position else "wall"
        after = stream[position + 1][2] if position + 1 < len(stream) else "wall"
        if before != "ch" or after not in {"ch", "sp"}:
            convert.setdefault(piece, set()).add(index)
    for piece, indices in convert.items():
        _write(piece.owner, piece.attr, "", _rewritten_spaces(piece, indices), "")


def _opcodes(old: str, new: str) -> list[tuple[int, int, int, int]]:
    """What to change to get from ``old`` to ``new``, as ``(old_start, old_stop, new_start, new_stop)``: the
    ranges to replace, in order. Compared word by word, so that a replaced word is replaced and not stitched from
    letters of both; within a replaced stretch, what its two sides share at the start and end is kept when that is
    at least half of the shorter side (so ``bold`` to ``bolder`` adds letters, ``rejected`` to ``approved`` swaps
    the word)."""
    a, b = _TOKEN.findall(old), _TOKEN.findall(new)
    a_at, b_at = [0], [0]
    for token in a:
        a_at.append(a_at[-1] + len(token))
    for token in b:
        b_at.append(b_at[-1] + len(token))
    if len(a) * len(b) > _DIFF_LIMIT:
        blocks = [("replace", 0, len(a), 0, len(b))]
    else:
        blocks = [
            block for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if block[0] != "equal"
        ]
    out = []
    for _tag, i1, i2, j1, j2 in blocks:
        x1, x2, y1, y2 = a_at[i1], a_at[i2], b_at[j1], b_at[j2]
        left, right = old[x1:x2], new[y1:y2]
        shared_start = len(_common(left, right))
        shared_end = len(_common(left[shared_start:][::-1], right[shared_start:][::-1]))
        if (shared_start + shared_end) * 2 >= min(len(left), len(right)) > 0:
            x1, y1, x2, y2 = x1 + shared_start, y1 + shared_start, x2 - shared_end, y2 - shared_end
        if x1 != x2 or y1 != y2:
            out.append((x1, x2, y1, y2))
    return out


def _common(a: str, b: str) -> str:
    count = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        count += 1
    return a[:count]


def _rebuild(paragraph: etree._Element, text: str) -> None:
    """The last resort: all text and all spaces, tabs and breaks out, the new text in. Only what is not text
    (bookmarks, notes, fields, frames) and the now empty spans and links are kept."""
    for piece in list(_walk(paragraph)):
        if piece.kind == "text":
            _put(piece.owner, piece.attr, "")
    for piece in list(_walk(paragraph)):
        if piece.kind in {"space", "tab", "break"}:
            _remove_keeping_tail(piece.owner)
    _write(paragraph, "text", "", _encode(text), paragraph.text or "")
    _normalise_spaces(paragraph)


def set_text(paragraph: etree._Element, text: str) -> None:
    """Change the text of ``paragraph`` (a ``text:p`` or ``text:h``, a copy: see the module description) to
    ``text``, editing only what differs. Afterwards :func:`read_text` of it is ``text`` -- with each character an
    XML file cannot hold as U+FFFD -- whatever the paragraph looked like."""
    text = xml_safe(text)
    if read_text(paragraph) == text:
        return
    for piece, collapsed in _collapsed(paragraph):  # a file that was indented gets what it says it means
        if piece.kind == "text" and collapsed != piece.value():
            _put(piece.owner, piece.attr, collapsed)
    for old_start, old_stop, new_start, new_stop in reversed(_opcodes(read_text(paragraph), text)):
        if old_stop > old_start:
            _delete(paragraph, old_start, old_stop)
        if new_stop > new_start:
            _insert(paragraph, old_start, text[new_start:new_stop])
    _normalise_spaces(paragraph)
    if read_text(paragraph) != text:
        _rebuild(paragraph, text)
