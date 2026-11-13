"""claudia-composes: the text app (E9.1).

model      TextModel, TextObject: paragraphs, authorship, open suggestions, styles, and floating objects (E10.16)
anchors    BlockAnchor: where an object hangs in a text, and why it follows the text where a sheet's is frozen
commands   the text and structure commands (SetStyle, SetListItem, SetPageSetup, SetLanguage, …), suggestions (D63)
page       PageSetup: the paper, orientation, margins and page numbers a text is printed with (D904)
language   normalize_language: the BCP 47 tag of the language a text is written in (D915)
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
    Paragraph,
    RemoveObject,
    ResizeObject,
    RotateObject,
    Run,
    SetParagraphStyle,
    SetSnap,
    SetText,
    VisualObject,
    paragraph_for,
)

from . import commands  # noqa: F401  (registers the commands)
from ._version import __version__
from .anchors import BlockAnchor
from .commands import (
    AcceptSuggestion,
    DeleteText,
    InsertText,
    JoinBlocks,
    ProposeSuggestion,
    ResolveSuggestion,
    SetLanguage,
    SetListItem,
    SetPageSetup,
    SetStyle,
    SplitBlock,
)
from .events import ItemChanged, LabelsChanged
from .language import LanguageError, normalize_language
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
from .page import PAPERS, PageSetup, PageSetupError
from .region import TextRange, word_window
from .spans import TextCommand

__all__ = [
    "__version__",
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
    "ItemChanged",
    "JoinBlocks",
    "LanguageError",
    "LabelsChanged",
    "MoveObject",
    "next_style",
    "normalize_language",
    "ObjectBody",
    "ObjectSet",
    "PageSetup",
    "PageSetupError",
    "PAPERS",
    "Paragraph",
    "paragraph_for",
    "ProposeSuggestion",
    "RemoveObject",
    "ResizeObject",
    "ResolveSuggestion",
    "RotateObject",
    "Run",
    "SetLanguage",
    "SetListItem",
    "SetPageSetup",
    "SetParagraphStyle",
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
