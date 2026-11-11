"""Editing one XML part by splicing bytes into the original (D401).

An OpenDocument file keeps every paragraph, every sheet and every slide of a document in one ``content.xml``, so
the whole-part restore that keeps an untouched xlsx sheet or pptx slide byte for byte (D219, D220) has nothing to
work with. Parsing the part and writing the tree back is no answer either: a tree library's serialisation changes
bytes nobody edited (``&apos;`` becomes ``'``, the quotes of the XML declaration change), and a person who opens
the file again in the program it came from should find nothing changed that they did not change.

So an :class:`XmlPart` parses the part only to *find* things. Every element has a byte span in the original, edits
are recorded against elements (replace, remove, insert next to, insert into), and :meth:`XmlPart.result` splices
the new markup into the original bytes. Without edits the result is the original, identical; with edits, all
bytes outside the edited elements are.

The spans come from expat, which reports the byte offset of every start and end tag; they pair up with lxml's
elements by document order. The parsed tree is for reading: edit by recording, never by changing it, or the spans
no longer describe it. To change an element, build a changed copy and :meth:`~XmlPart.replace` the original.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from xml.parsers import expat

from lxml import etree

from .names import NS

_NAME = re.compile(rb"<([^\s/>]+)")


class OdfError(Exception):
    """A file that is not the OpenDocument this layer can work with, or an edit that cannot be made. The message is
    a sentence for the person who has to decide what to do with the file."""


@dataclass(frozen=True)
class Span:
    """Where an element is in the bytes of its part: ``start``..``end`` is all of it, the start tag ends at
    ``open_end``, the end tag starts at ``close`` (``-1`` for an element written as one empty tag, ``<a/>``)."""

    start: int
    end: int
    open_end: int
    close: int


def _tag_end(raw: bytes, start: int) -> int:
    """The offset just after the ``>`` that closes the tag starting at ``start``; a ``>`` inside a quoted
    attribute value does not count."""
    quote = 0
    for position in range(start, len(raw)):
        byte = raw[position]
        if quote:
            if byte == quote:
                quote = 0
        elif byte in b"\"'":
            quote = byte
        elif byte == 0x3E:  # ">"
            return position + 1
    raise OdfError("the file ends inside a tag")  # pragma: no cover - expat has parsed it, so it cannot


def _spans(raw: bytes) -> list[Span]:
    """The span of every element of ``raw``, in document order."""
    found: list[list[int]] = []
    open_ones: list[int] = []
    parser = expat.ParserCreate()

    def start(_name: str, _attributes: Mapping[str, str]) -> None:
        at = parser.CurrentByteIndex
        found.append([at, -1, _tag_end(raw, at), -1])
        open_ones.append(len(found) - 1)

    def end(_name: str) -> None:
        item = found[open_ones.pop()]
        if raw[item[2] - 2 : item[2]] == b"/>":  # an empty element is one tag, and has no end tag to find
            item[1] = item[2]
        else:
            at = parser.CurrentByteIndex
            item[3] = at
            item[1] = raw.index(b">", at) + 1

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(raw, True)
    return [Span(*item) for item in found]


class XmlPart:
    """One XML part of a package, to be edited by splicing. See the module description."""

    def __init__(self, data: bytes):
        self.raw = data
        try:
            self.root: etree._Element = etree.fromstring(
                data, etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
            )
        except etree.XMLSyntaxError as problem:
            raise OdfError(f"this part of the file is not well-formed XML: {problem}") from problem
        info = self.root.getroottree().docinfo
        if (info.encoding or "UTF-8").upper().replace("-", "") != "UTF8":
            raise OdfError(f"this part of the file is not in UTF-8 but in {info.encoding}")
        if info.internalDTD is not None or info.externalDTD is not None:
            raise OdfError("this part of the file has a document type declaration, which OpenDocument does not use")
        self._elements: list[etree._Element] = list(self.root.iter(etree.Element))
        self._spans = _spans(data)
        if len(self._spans) != len(self._elements):  # pragma: no cover - the two parsers disagree: a bug here
            raise OdfError("the part could not be mapped to bytes")
        self._index = {element: number for number, element in enumerate(self._elements)}
        self._edits: list[tuple[int, int, int, bytes]] = []  # start, end, order made, new bytes
        self._declared: dict[str, str] = {p: uri for p, uri in self.root.nsmap.items() if p is not None}

    # -- reading -----------------------------------------------------------------
    def elements(self) -> list[etree._Element]:
        """Every element of the part, in document order."""
        return list(self._elements)

    def span(self, element: etree._Element) -> tuple[int, int]:
        """Where ``element`` is in the original bytes: ``(start, end)``, end excluded."""
        found = self._span(element)
        return found.start, found.end

    def _span(self, element: etree._Element) -> Span:
        try:
            return self._spans[self._index[element]]
        except KeyError:
            raise OdfError("that is not an element of this part") from None

    # -- new markup ----------------------------------------------------------------
    def make(self, tag: str, attrib: Mapping[str, str] | None = None, text: str | None = None) -> etree._Element:
        """A new element ``tag`` (``"text:p"``) with attributes (names with prefixes too) and text, for use in an
        edit. A prefix the part declares is the part's; any other must be one this layer knows (``NS``), and is
        declared on the new element."""
        attrib = attrib or {}
        prefixes = {tag.partition(":")[0]} | {name.partition(":")[0] for name in attrib if ":" in name}
        nsmap = {prefix: self._declared.get(prefix) or NS[prefix] for prefix in sorted(prefixes)}
        element = etree.Element(qname_in(tag, nsmap), nsmap=nsmap)
        for name, value in attrib.items():
            element.set(qname_in(name, nsmap) if ":" in name else name, value)
        element.text = text
        return element

    def _bytes_of(self, new: etree._Element | bytes) -> bytes:
        if isinstance(new, bytes):
            return new
        data = etree.tostring(new, encoding="utf-8", with_tail=False)
        head_end = _tag_end(data, 0)
        head = data[:head_end]
        for prefix, uri in self._declared.items():  # what the part declares at its root need not be said again
            head = head.replace(f' xmlns:{prefix}="{uri}"'.encode(), b"")
        return head + data[head_end:]

    # -- editing ---------------------------------------------------------------------
    def _edit(self, start: int, end: int, new: bytes) -> None:
        self._edits.append((start, end, len(self._edits), new))

    def replace(self, element: etree._Element, new: etree._Element | bytes) -> None:
        """Put ``new`` (an element made with :meth:`make` or copied and changed, or markup as bytes) in place of
        ``element``."""
        span = self._span(element)
        self._edit(span.start, span.end, self._bytes_of(new))

    def remove(self, element: etree._Element) -> None:
        """Take ``element`` out, with what is inside it."""
        span = self._span(element)
        self._edit(span.start, span.end, b"")

    def insert_before(self, element: etree._Element, new: etree._Element | bytes) -> None:
        """Put ``new`` right before ``element``, as its sibling."""
        start = self._span(element).start
        self._edit(start, start, self._bytes_of(new))

    def insert_after(self, element: etree._Element, new: etree._Element | bytes) -> None:
        """Put ``new`` right after ``element``, as its sibling. Several inserts at one place come out in the order
        they were made."""
        end = self._span(element).end
        self._edit(end, end, self._bytes_of(new))

    def insert_into(self, parent: etree._Element, *new: etree._Element | bytes, at_start: bool = False) -> None:
        """Put ``new`` in ``parent`` as its last children (its first, with ``at_start``), in the order given. A
        parent written as one empty tag is opened for them -- so give everything that goes into one in one call: two
        calls would both rewrite that one tag."""
        span = self._span(parent)
        data = b"".join(self._bytes_of(item) for item in new)
        if span.close < 0:
            tag = self.raw[span.start : span.end].rstrip(b">").rstrip(b"/").rstrip()
            name = _NAME.match(tag)
            assert name is not None  # expat has parsed this tag
            self._edit(span.start, span.end, tag + b">" + data + b"</" + name.group(1) + b">")
        elif at_start:
            self._edit(span.open_end, span.open_end, data)
        else:
            self._edit(span.close, span.close, data)

    # -- the result ------------------------------------------------------------------
    def result(self) -> bytes:
        """The part with every recorded edit made. ``OdfError`` if two edits overlap (one replaces an element,
        another reaches into it): nothing sensible can be made of that."""
        out = bytearray()
        position = 0
        for start, end, _order, data in sorted(self._edits):
            if start < position:
                raise OdfError("two edits overlap: one reaches into an element that another replaces or removes")
            out += self.raw[position:start]
            out += data
            position = end
        out += self.raw[position:]
        return bytes(out)

    def __iter__(self) -> Iterator[etree._Element]:
        return iter(self._elements)


def qname_in(prefixed: str, nsmap: Mapping[str, str]) -> str:
    """``"p:name"`` as a Clark name, with the namespace ``nsmap`` gives the prefix."""
    prefix, _, name = prefixed.partition(":")
    return f"{{{nsmap[prefix]}}}{name}"
