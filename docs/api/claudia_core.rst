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
