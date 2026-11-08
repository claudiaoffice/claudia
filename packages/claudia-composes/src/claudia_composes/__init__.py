"""claudia-composes: the text app (E9.1).

model      TextModel, TextObject: paragraphs, authorship, open suggestions, styles, and floating objects (E10.16)
anchors    BlockAnchor: where an object hangs in a text, and why it follows the text where a sheet's is frozen
commands   InsertText, DeleteText, SplitBlock, JoinBlocks, SetStyle and the suggestion commands (D63)
region     TextRange, and ``word_window``: the ± n words zone around a cursor (D11)
runs       authorship runs (E9.10), kept by the commands so that the log alone rebuilds them
events     what a client that holds the paragraphs needs to follow them
"""

# The object commands, the object types and the object region are shared by all three apps and live in
# ``claudia_core`` (E10.16). They are re-exported here so that an app package names everything it can do.
from claudia_core import (  # noqa: F401
    AddObject,
    DefineImage,
    DefineShape,
    ForgetImage,
    ForgetShape,
    MoveObject,
    ObjectBody,
    ObjectSet,
    RemoveObject,
    ResizeObject,
    RotateObject,
    SetSnap,
    SetText,
    VisualObject,
)

from . import commands  # noqa: F401  (registers the commands)
from .anchors import BlockAnchor
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
from .model import (
    BUILTIN_STYLES,
    DEFAULT_STYLE,
    Block,
    Suggestion,
    TextModel,
    TextObject,
    builtin_styles,
    next_style,
)
from .region import TextRange, word_window
from .runs import Run
from .spans import TextCommand

__all__ = [
    "AcceptSuggestion",
    "AddObject",
    "Block",
    "BlockAnchor",
    "builtin_styles",
    "BUILTIN_STYLES",
    "DEFAULT_STYLE",
    "DefineImage",
    "DefineShape",
    "DeleteText",
    "ForgetImage",
    "ForgetShape",
    "InsertText",
    "JoinBlocks",
    "MoveObject",
    "next_style",
    "ObjectBody",
    "ObjectSet",
    "ProposeSuggestion",
    "RemoveObject",
    "ResizeObject",
    "ResolveSuggestion",
    "RotateObject",
    "Run",
    "SetSnap",
    "SetStyle",
    "SetText",
    "SplitBlock",
    "Suggestion",
    "TextCommand",
    "TextModel",
    "TextObject",
    "TextRange",
    "VisualObject",
    "word_window",
]
