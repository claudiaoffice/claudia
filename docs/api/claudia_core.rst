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

Commands
--------

.. autoclass:: claudia_core.Command
.. autoclass:: claudia_core.Batch
.. autoclass:: claudia_core.CommandRegistry
.. autofunction:: claudia_core.encode
.. autofunction:: claudia_core.new_registry
.. autoclass:: claudia_core.Checkpoint
.. autoclass:: claudia_core.Redaction
.. autoclass:: claudia_core.Restore
.. autoclass:: claudia_core.Switch
.. autoclass:: claudia_core.Redacted
.. autoclass:: claudia_core.Context

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

.. autodata:: claudia_core.CSS_VERSION
.. autodata:: claudia_core.ALLOWED_CSS
.. autofunction:: claudia_core.validate_css
.. autofunction:: claudia_core.parse_css
.. autofunction:: claudia_core.format_css
.. autoexception:: claudia_core.CssError
.. autoclass:: claudia_core.CssProblem
.. autoclass:: claudia_core.StyleDef
.. autoclass:: claudia_core.StyleBook
.. autoclass:: claudia_core.StylesChanged
.. autoclass:: claudia_core.CreateStyle
.. autoclass:: claudia_core.ChangeStyle
.. autoclass:: claudia_core.RenameStyle
.. autoclass:: claudia_core.RemoveStyle

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
