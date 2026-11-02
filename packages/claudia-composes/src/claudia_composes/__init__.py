"""claudia-composes: the text app (E9.1).

model      TextModel: named paragraphs, who wrote each stretch, the AI's open suggestions
commands   InsertText, DeleteText, SplitBlock, JoinBlocks, SetStyle and the suggestion commands (D63)
region     TextRange, and ``word_window``: the ± n words zone around a cursor (D11)
runs       authorship runs (E9.10), kept by the commands so that the log alone rebuilds them
events     what a client that holds the paragraphs needs to follow them
"""

from . import commands  # noqa: F401  (registers the commands)
from .commands import (
    AcceptSuggestion,
    DeleteText,
    InsertText,
    JoinBlocks,
    ProposeSuggestion,
    ResolveSuggestion,
    SetStyle,
    SplitBlock,
)
from .model import DEFAULT_STYLE, STYLES, Block, Style, Suggestion, TextModel
from .region import TextRange, word_window
from .runs import Run
from .spans import TextCommand

__all__ = [
    "DEFAULT_STYLE",
    "STYLES",
    "AcceptSuggestion",
    "Block",
    "DeleteText",
    "InsertText",
    "JoinBlocks",
    "ProposeSuggestion",
    "ResolveSuggestion",
    "Run",
    "SetStyle",
    "SplitBlock",
    "Style",
    "Suggestion",
    "TextCommand",
    "TextModel",
    "TextRange",
    "word_window",
]
