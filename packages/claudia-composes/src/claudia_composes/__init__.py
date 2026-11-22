"""claudia-composes: the text app (E9.1).

model      TextModel, TextObject: paragraphs, authorship, open suggestions, styles, and floating objects (E10.16)
anchors    ParagraphAnchor: where an object hangs in a text and how far it floats from there; why it follows the text
commands   the text and structure commands (SetStyle, SetPageSetup, SetLanguage, …), suggestions (D63)
page       PageSetup (the kernel's, D917): the paper, orientation, margins and page numbers a text prints on
language   normalize_language, SetLanguage (the kernel's, D917): the language a text is written in (D915)
region     TextRange, and ``word_window``: the ± n words zone around a cursor (D11)
runs       authorship runs (E9.10), kept by the commands so that the log alone rebuilds them
events     what a client that holds the paragraphs needs to follow them
"""

# The object commands, the object types and the object region are shared by all three apps and live in
# ``claudia_core`` (E10.16). They are re-exported here so that an app package names everything it can do.
from claudia_core import (  # noqa: F401
    AddObject,
    DescribeObject,
    LabelsChanged,  # told by the structure every app shares (step C)
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
from .anchors import DEFAULT_WRAP_GAP, MAX_ANCHOR_OFFSET, MAX_WRAP_GAP, WRAPS, ParagraphAnchor
from .commands import (
    AcceptSuggestion,
    DeleteText,
    InsertText,
    JoinParagraphs,
    ProposeSuggestion,
    ResolveSuggestion,
    SetLanguage,
    SetObjectWrap,
    SetPageSetup,
    SetStyle,
    SplitParagraph,
)
from .events import FieldsPut, ItemChanged, ParagraphGenerated
from .language import LanguageError, normalize_language
from .model import (
    BUILTIN_STYLES,
    DEFAULT_LOOK,
    DEFAULT_STYLE,
    TABLE_FRAME_STYLE,
    TABLE_LOOKS,
    TABLE_OBJECT_WIDTH,
    TABLE_ROW_HEIGHT,
    TABLE_STYLE_IDS,
    Suggestion,
    TextModel,
    TextObject,
    builtin_styles,
    next_style,
    table_body,
)
from .page import PAPERS, PageSetup, PageSetupError
from .region import TextRange, word_window
from .spans import TextCommand

__all__ = [
    "__version__",
    "AcceptSuggestion",
    "AddObject",
    "ParagraphAnchor",
    "builtin_styles",
    "BUILTIN_STYLES",
    "DEFAULT_LOOK",
    "TABLE_FRAME_STYLE",
    "TABLE_LOOKS",
    "TABLE_OBJECT_WIDTH",
    "TABLE_ROW_HEIGHT",
    "TABLE_STYLE_IDS",
    "DEFAULT_STYLE",
    "DescribeObject",
    "DeleteText",
    "InsertText",
    "ItemChanged",
    "ParagraphGenerated",
    "FieldsPut",
    "JoinParagraphs",
    "LanguageError",
    "LabelsChanged",
    "DEFAULT_WRAP_GAP",
    "MAX_ANCHOR_OFFSET",
    "MAX_WRAP_GAP",
    "WRAPS",
    "MoveObject",
    "next_style",
    "table_body",
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
    "SetObjectWrap",
    "SetPageSetup",
    "SetParagraphStyle",
    "SetSnap",
    "SetStyle",
    "SetText",
    "SplitParagraph",
    "Suggestion",
    "TextCommand",
    "TextModel",
    "TextObject",
    "TextRange",
    "VisualObject",
    "word_window",
]
