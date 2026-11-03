"""claudia-composes: the text app (E9.1).

model      TextModel: named paragraphs, who wrote each stretch, the AI's open suggestions, the styles (CSS, E9.7)
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
from .model import BUILTIN_STYLES, DEFAULT_STYLE, Block, Suggestion, TextModel, builtin_styles, next_style
from .region import TextRange, word_window
from .runs import Run
from .spans import TextCommand

__all__ = [
    "BUILTIN_STYLES",
    "DEFAULT_STYLE",
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
    "Suggestion",
    "TextCommand",
    "TextModel",
    "TextRange",
    "builtin_styles",
    "next_style",
    "word_window",
]
