"""The one way a package's XML is read (SEC-15).

A part of a Word, Excel, PowerPoint or OpenDocument file is written by whoever made the file. XML lets its author
define entities -- names that stand for text, which may stand for more entities -- so a few hundred bytes can ask a
parser for gigabytes, or name a file on the reader's disk. :func:`parse_xml` is lxml with entities never resolved, no
network, no DTD loaded and the limits on depth and size left at lxml's own (``huge_tree`` stays off). Every reader of
a package's XML uses it, never ``etree.fromstring`` on its own.
"""

from __future__ import annotations

from lxml import etree

#: One parser for all callers: lxml gives each thread its own copy of a parser it is shared by.
_SAFE = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False, huge_tree=False)


def parse_xml(data: bytes) -> etree._Element:
    """The root of the XML in ``data``. Raises ``lxml.etree.XMLSyntaxError`` for anything that is not well formed, and
    for a document nested more deeply than lxml allows; entities are left as they are, never expanded or fetched."""
    return etree.fromstring(data, _SAFE)
