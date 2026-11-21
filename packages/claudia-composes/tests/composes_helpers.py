"""Helpers shared by the tests of claudia-composes (a module of its own: ``conftest`` names clash between packages)."""

SENTENCE = "the quick brown fox jumps over the lazy dog"


def text_of(doc, paragraph="b1"):
    return doc.model.paragraph(paragraph).text


def texts(doc):
    return [b.text for b in doc.model.paragraphs]
