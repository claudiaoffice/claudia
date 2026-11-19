claudia-core API reference
==========================

.. module:: claudia_core

The public API is exactly what ``claudia_core.__all__`` lists (see :doc:`../versioning`). This page is generated
from the docstrings of the code.

Documents
---------

.. autoclass:: claudia_core.Document
.. autoclass:: claudia_core.Applied
.. autoclass:: claudia_core.Line
.. autoclass:: claudia_core.CheckpointInfo
.. autoclass:: claudia_core.Look
.. autoclass:: claudia_core.Changes
.. autoclass:: claudia_core.RedactionPlan
   :members: revisions
.. autodata:: claudia_core.FILLER

Names of things
---------------

One namespace for every thing of a document that can be pointed at (D550, D552, D554).

.. autofunction:: claudia_core.clean_name
.. autofunction:: claudia_core.name_key
.. autofunction:: claudia_core.name_problem
.. autofunction:: claudia_core.free_name
.. autoclass:: claudia_core.RenameThing
.. autoclass:: claudia_core.ThingRenamed

Commands
--------

.. autoclass:: claudia_core.Command
.. autoclass:: claudia_core.Batch
.. autoclass:: claudia_core.Setup
.. autoclass:: claudia_core.CommandRegistry
.. autofunction:: claudia_core.encode
.. autofunction:: claudia_core.new_registry
.. autoclass:: claudia_core.Checkpoint
.. autoclass:: claudia_core.Redaction
.. autoclass:: claudia_core.Restore
.. autoclass:: claudia_core.Switch
.. autoclass:: claudia_core.Redacted
.. autoclass:: claudia_core.Context

Paragraphs
----------

.. automodule:: claudia_core.paragraphs
   :no-members:

.. currentmodule:: claudia_core

A paragraph is the same entity wherever text appears: a paragraph of a composes document, the words in a creates
text box, the label inside a shape on a sheet (E10.17, D181).

.. autoclass:: claudia_core.Paragraph
.. autoclass:: claudia_core.Run
.. autoclass:: claudia_core.ListItem
   :exclude-members: list

Lists
-----

.. automodule:: claudia_core.lists
   :no-members:

.. currentmodule:: claudia_core

A paragraph is an item of a list by structure only (``Paragraph.item``); how it looks, and which number it carries,
is derived (E9.21). (The field ``list`` of ``ListItem`` and of the commands is left out of the member lists below,
because a documented attribute called ``list`` makes every ``list[...]`` in a signature ambiguous for Sphinx; each
class docstring says what it holds.) How a list is drawn is its scheme, part of the document (below).

.. autoclass:: claudia_core.ListDef
.. autoclass:: claudia_core.ListBook
.. autoclass:: claudia_core.Label
.. autofunction:: claudia_core.numbering_labels
.. autoclass:: claudia_core.ListsChanged
.. autoclass:: claudia_core.CreateList
   :exclude-members: list
.. autoclass:: claudia_core.ChangeList
   :exclude-members: list
.. autoclass:: claudia_core.RemoveList
   :exclude-members: list
.. autoclass:: claudia_core.SetListItem
.. autoclass:: claudia_core.ItemHost

Numbering schemes
-----------------

.. automodule:: claudia_core.schemes
   :no-members:

.. currentmodule:: claudia_core

.. autoclass:: claudia_core.LevelFormat
.. autoclass:: claudia_core.Scheme
.. autoclass:: claudia_core.SchemeBook
.. autofunction:: claudia_core.builtin_schemes
.. autofunction:: claudia_core.builtin_scheme
.. autodata:: claudia_core.FORMATS
.. autoclass:: claudia_core.SchemesChanged
.. autoclass:: claudia_core.CreateScheme
.. autoclass:: claudia_core.ChangeScheme
.. autoclass:: claudia_core.RemoveScheme

Text structure
--------------

.. automodule:: claudia_core.structure
   :no-members:

.. currentmodule:: claudia_core

.. autoclass:: claudia_core.ParagraphHost
.. autoclass:: claudia_core.Placed
.. autoclass:: claudia_core.TextStructure
.. autoclass:: claudia_core.LabelsChanged
.. autoclass:: claudia_core.Emitter

Typing
------

.. automodule:: claudia_core.writing
   :no-members:

.. currentmodule:: claudia_core

.. autoclass:: claudia_core.InsertText
.. autoclass:: claudia_core.DeleteText
.. autoclass:: claudia_core.TextCommand
.. autoclass:: claudia_core.TypingHost
.. autofunction:: claudia_core.word_changes

References
----------

.. automodule:: claudia_core.fields
   :no-members:

.. currentmodule:: claudia_core

.. autoclass:: claudia_core.RefField
.. autoclass:: claudia_core.Shown
.. autoclass:: claudia_core.FieldsChanged
.. autoclass:: claudia_core.FieldHost
.. autoclass:: claudia_core.SetField
.. autofunction:: claudia_core.field_from_data
.. autofunction:: claudia_core.fields_before
.. autofunction:: claudia_core.plain
.. autodata:: claudia_core.FIELD_CHAR
.. autodata:: claudia_core.SHOWS

Tables of contents
------------------

.. automodule:: claudia_core.generated
   :no-members:

.. currentmodule:: claudia_core

.. autoclass:: claudia_core.Toc
.. autoclass:: claudia_core.ContentsEntry
.. autoclass:: claudia_core.GeneratedChanged
.. autoclass:: claudia_core.GeneratedHost
.. autoclass:: claudia_core.SetGenerated
.. autofunction:: claudia_core.generated_from_data
.. autodata:: claudia_core.CONTENTS_STYLE

Page setup and language
-----------------------

.. automodule:: claudia_core.page
   :no-members:

.. currentmodule:: claudia_core

The page a document prints on and the language it is written in, shared by the apps that print (D904, D915, D917).

.. autoclass:: claudia_core.PageSetup
.. autoexception:: claudia_core.PageSetupError
.. autodata:: claudia_core.page.PAPERS
   :no-value:
.. autofunction:: claudia_core.normalize_language
.. autoexception:: claudia_core.LanguageError
.. autoclass:: claudia_core.SetLanguage
.. autoclass:: claudia_core.LanguageChanged

Tables
------

A table is plain data (columns and rows with ids, the words of each box, merges, a look) that an object of the kind
``table`` points at (E9.32, D1201–D1214); the commands change it, and a converter or a client reads it.

.. autoclass:: claudia_core.TableDef
.. autoclass:: claudia_core.Column
.. autoclass:: claudia_core.Merge
.. autoclass:: claudia_core.RowSpec
.. autoclass:: claudia_core.ColumnSpec
.. autoclass:: claudia_core.TableLook
.. autoclass:: claudia_core.TableRegion
.. autoclass:: claudia_core.TableSource
.. autofunction:: claudia_core.entry_id
.. autofunction:: claudia_core.parse_entry_id
.. autofunction:: claudia_core.entry_paragraph
.. autofunction:: claudia_core.parse_number
.. autofunction:: claudia_core.format_number
.. autofunction:: claudia_core.decimal_comma
.. autoclass:: claudia_core.TablesChanged
.. autoclass:: claudia_core.table_commands.TableCommand
.. autoclass:: claudia_core.DefineTable
.. autoclass:: claudia_core.ForgetTable
.. autoclass:: claudia_core.SetEntries
.. autoclass:: claudia_core.InsertRows
.. autoclass:: claudia_core.DeleteRows
.. autoclass:: claudia_core.InsertColumns
.. autoclass:: claudia_core.DeleteColumns
.. autoclass:: claudia_core.SetRowOrder
.. autoclass:: claudia_core.SetColumnOrder
.. autoclass:: claudia_core.SetColumn
.. autoclass:: claudia_core.SetTableOptions
.. autoclass:: claudia_core.SetMerge

Objects: shapes, images and text boxes
--------------------------------------

.. automodule:: claudia_core.objects
   :no-members:

.. currentmodule:: claudia_core

An object is a shared body and a per-app anchor; everything but the anchor is written once here (E10.16, D177).

.. autoclass:: claudia_core.ObjectBody
.. autoclass:: claudia_core.VisualObject
.. autoclass:: claudia_core.Anchor
.. autoclass:: claudia_core.ObjectModel
.. autoclass:: claudia_core.ObjectSet
.. autoclass:: claudia_core.ObjectsChanged
.. autoclass:: claudia_core.ImagesChanged
.. autoclass:: claudia_core.ShapesChanged
.. autoclass:: claudia_core.DiagramDefinition
.. autoclass:: claudia_core.DiagramsChanged

The object commands, the same in all three apps:

.. autoclass:: claudia_core.AddObject
.. autoclass:: claudia_core.RemoveObject
.. autoclass:: claudia_core.MoveObject
.. autoclass:: claudia_core.ResizeObject
.. autoclass:: claudia_core.RotateObject
.. autoclass:: claudia_core.SetText
.. autoclass:: claudia_core.SetParagraph
.. autoclass:: claudia_core.SetObjectStyle
.. autoclass:: claudia_core.SetParagraphStyle
.. autoclass:: claudia_core.SetSnap
.. autoclass:: claudia_core.DescribeObject
.. autoclass:: claudia_core.DefineShape
.. autoclass:: claudia_core.ForgetShape
.. autoclass:: claudia_core.DefineImage
.. autoclass:: claudia_core.ForgetImage
.. autoclass:: claudia_core.DefineDiagram
.. autoclass:: claudia_core.UpdateDiagram
.. autoclass:: claudia_core.ForgetDiagram

Turning: how far a turned object reaches
-----------------------------------------

.. automodule:: claudia_core.turning
   :no-members:

.. currentmodule:: claudia_core

A turn is one :class:`~claudia_core.RotateObject` command (D1021), and what has to lie on a page is the turned
outline, worked out in whole numbers from a table of sines (D910, D1022).

.. autodata:: claudia_core.SINE_MILLIONTHS
.. autofunction:: claudia_core.turned_extent
.. autofunction:: claudia_core.nudge_into

Rendered text containers
------------------------

.. automodule:: claudia_core.renderings
   :no-members:

.. currentmodule:: claudia_core

A rendered text container keeps a text and shows a picture something outside the document made from it (D390); the
kernel keeps the definition and the picture, and never runs anything (D391).

.. autoclass:: claudia_core.RenderedDefinition
.. autoclass:: claudia_core.RenderingsChanged
.. autoclass:: claudia_core.DefineRendering
.. autoclass:: claudia_core.UpdateRendering
.. autoclass:: claudia_core.ForgetRendering

Shape outlines
--------------

.. automodule:: claudia_core.shapes
   :members: ShapeError

.. currentmodule:: claudia_core

.. autoclass:: claudia_core.ShapeDefinition
.. autofunction:: claudia_core.parse_shape
.. autoclass:: claudia_core.objects.ReadAnchor

The model an app implements
---------------------------

.. autoclass:: claudia_core.DocumentModel
.. autoclass:: claudia_core.Snapshot

Log and revisions
-----------------

.. autoclass:: claudia_core.Revision
.. autoclass:: claudia_core.Branch
.. autodata:: claudia_core.MAIN
.. autoclass:: claudia_core.Entry
.. autoclass:: claudia_core.CommandLog
.. autofunction:: claudia_core.replay
.. autofunction:: claudia_core.replay_collecting
.. autoclass:: claudia_core.History
.. autoclass:: claudia_core.Step

Regions, presence and locks
---------------------------

.. autoclass:: claudia_core.Region
.. autofunction:: claudia_core.transform
.. autoclass:: claudia_core.Presence
.. autoclass:: claudia_core.Hold

Messages and events
-------------------

.. autoclass:: claudia_core.ChatRecord
.. autoclass:: claudia_core.Ephemeral
.. autofunction:: claudia_core.parse_chat
.. autoclass:: claudia_core.EventBus
.. autoclass:: claudia_core.CommandApplied
.. autoclass:: claudia_core.HistoryChanged
.. autoclass:: claudia_core.CheckpointSaved
.. autoclass:: claudia_core.ChatPosted
.. autoclass:: claudia_core.EphemeralPublished
.. autoclass:: claudia_core.events.Redacted
.. autoclass:: claudia_core.BranchSwitched
.. autoclass:: claudia_core.Rebuilt
.. autoclass:: claudia_core.ResultsStale

Storage
-------

.. autoclass:: claudia_core.DocumentStore
.. autoclass:: claudia_core.MemoryStore

Manifest and requirements
-------------------------

.. autoclass:: claudia_core.Manifest
.. autoclass:: claudia_core.Requirements
.. autoclass:: claudia_core.FunctionRequirement
.. autoclass:: claudia_core.FontRequirement
.. autoclass:: claudia_core.Environment
.. autoclass:: claudia_core.FunctionInfo
.. autoclass:: claudia_core.RequirementReport
.. autofunction:: claudia_core.check
.. autofunction:: claudia_core.environment_of

Styles and CSS
--------------

A style is CSS from one short, versioned allow-list (``CSS_VERSION``): no ``url()``, ``var()``, ``calc()``,
``@``-rules or ``!important``. An app's model that wants styles holds a ``StyleBook``; the commands are the only ways to
change it.

A colour may be a role of the document's palette (``@accent``, or ``@accent/55`` for that role at 55% opacity) rather
than a literal. ``resolve_css`` replaces the roles with colours, and that is the form a client draws with, so what
reaches a browser is always literal.

.. autodata:: claudia_core.CSS_VERSION
.. autodata:: claudia_core.ALLOWED_CSS
.. autodata:: claudia_core.css.INITIAL_CSS
   :no-value:
.. autofunction:: claudia_core.validate_css
.. autofunction:: claudia_core.parse_css
.. autofunction:: claudia_core.format_css
.. autofunction:: claudia_core.resolve_css
.. autofunction:: claudia_core.roles_used
.. autofunction:: claudia_core.rgb_of
.. autoexception:: claudia_core.CssError
.. autoclass:: claudia_core.CssProblem
.. autoclass:: claudia_core.StyleDef
.. autoclass:: claudia_core.StyleBook
.. autoclass:: claudia_core.StylesChanged
.. autoclass:: claudia_core.CreateStyle
.. autoclass:: claudia_core.ChangeStyle
.. autoclass:: claudia_core.RenameStyle
.. autoclass:: claudia_core.RemoveStyle
.. autoclass:: claudia_core.RebaseStyle
.. autoclass:: claudia_core.SetStyleHidden
.. autoclass:: claudia_core.SetHeadingLevel
.. autodata:: claudia_core.MAX_HEADING_LEVEL
.. autoclass:: claudia_core.SetStyleNumbering
.. autodata:: claudia_core.NO_NUMBERING
.. autodata:: claudia_core.styles.ORIGINS
   :no-value:
.. autodata:: claudia_core.styles.DELETE_HOWS
   :no-value:
.. autofunction:: claudia_core.plan_delete_style
.. autofunction:: claudia_core.assign_changes_look
.. autofunction:: claudia_core.held_look

Facets, kinds and slots
-----------------------

.. automodule:: claudia_core.facets
   :no-members:

.. currentmodule:: claudia_core

Every property a style may set belongs to one of four facets (text, paragraph, box, outline); a style's kind says which
facets it may hold; a slot is a place in a thing that reads a style, and the slot table says which slots everything that
can be styled has (D303-D305, D312, D315).

.. autoclass:: claudia_core.Facet
.. autodata:: claudia_core.facets.TEXT_FACET
   :no-value:
.. autodata:: claudia_core.facets.PARAGRAPH_FACET
   :no-value:
.. autodata:: claudia_core.facets.BOX_FACET
   :no-value:
.. autodata:: claudia_core.facets.OUTLINE_FACET
   :no-value:
.. autodata:: claudia_core.facets.FACETS
   :no-value:
.. autodata:: claudia_core.facets.FACET_PROPERTIES
   :no-value:
.. autofunction:: claudia_core.facet_of
.. autodata:: claudia_core.facets.KINDS
   :no-value:
.. autofunction:: claudia_core.check_kind
.. autoclass:: claudia_core.Slot
.. autoclass:: claudia_core.SlotTable
.. autodata:: claudia_core.facets.SLOTS
   :no-value:
.. autofunction:: claudia_core.fits

The palette: colours by what they mean
--------------------------------------

.. automodule:: claudia_core.palette
   :no-members:

.. currentmodule:: claudia_core

A palette is part of the document, so a document looks the same wherever it is opened (D200). A role says what a
colour *means*; change the role and everything that meant it follows, across all three apps.

.. autoclass:: claudia_core.ColourRole
.. autoclass:: claudia_core.Palette
.. autoclass:: claudia_core.Reading
.. autoclass:: claudia_core.PaletteChanged
.. autoclass:: claudia_core.SetRole
.. autoclass:: claudia_core.ReplacePalette
.. autofunction:: claudia_core.builtin_palette
.. autofunction:: claudia_core.contrast
.. autofunction:: claudia_core.luminance
.. autodata:: claudia_core.BUILTIN_ROLES
.. autodata:: claudia_core.PAIRINGS
.. autodata:: claudia_core.TEXT_FLOOR
.. autodata:: claudia_core.UI_FLOOR
.. autodata:: claudia_core.MAX_ROLES

Images
------

An app's own object (a slide's ``SlideObject``, a sheet's picture, a composes anchor) holds an :class:`ImageAsset`
and an :class:`ImageImport`; it decides where the picture sits, not this module.

.. autofunction:: claudia_core.decode_image
.. autoclass:: claudia_core.ImageAsset
.. autoclass:: claudia_core.ImageImport
.. autoexception:: claudia_core.ImageError
.. autodata:: claudia_core.SUPPORTED_IMAGE_FORMATS
.. autodata:: claudia_core.MAX_IMAGE_BYTES

Errors
------

.. autoexception:: claudia_core.KernelError
.. autoexception:: claudia_core.UnknownCommand
.. autoexception:: claudia_core.SchemaTooNew
.. autoexception:: claudia_core.MissingUpcaster
.. autoexception:: claudia_core.RevisionMismatch
.. autoexception:: claudia_core.RegionHeld
.. autoexception:: claudia_core.UndoRefused
.. autoexception:: claudia_core.UndoConflict
.. autoexception:: claudia_core.StaleEdit
.. autoexception:: claudia_core.RedactionError
.. autoexception:: claudia_core.ReplayError
