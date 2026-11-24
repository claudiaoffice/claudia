claudia-server API reference
============================

.. module:: claudia_server

The public API is exactly what ``claudia_server.__all__`` lists (see :doc:`../versioning`). The network protocol itself
is described on :doc:`../server`.

Application
-----------

.. autofunction:: claudia_server.create_app
.. autoclass:: claudia_server.Gateway
.. autoclass:: claudia_server.IdleWatch
.. autoclass:: claudia_server.LoginThrottle
   :members:
.. autoclass:: claudia_server.KdfPolicy
   :members:

Apps on one server
------------------

.. autoclass:: claudia_server.Suite
.. autoclass:: claudia_server.Module
.. autodata:: claudia_server.suite.APP_MODELS
.. autoclass:: claudia_server.FolderLock
.. autoclass:: claudia_server.FolderLocked

Hub
---

.. autoclass:: claudia_server.Hub
.. autoclass:: claudia_server.HostedDocument
.. autoclass:: claudia_server.Connection
.. autoclass:: claudia_server.DocumentProvider
.. autoclass:: claudia_server.MemoryProvider
.. autoclass:: claudia_server.StoredInfo
.. autoclass:: claudia_server.FileProvider
.. autoclass:: claudia_server.FileDirectory
.. autoclass:: claudia_server.SealedDocuments
.. autoclass:: claudia_server.HubError
.. autoclass:: claudia_server.Room

Worker pool
-----------

.. autoclass:: claudia_server.WorkerPool
.. autodata:: claudia_server.DEFAULT_WORKERS
.. autodata:: claudia_server.DEFAULT_MAX_WAITING
.. autoexception:: claudia_server.PoolBusy

Administrators
--------------

Not in ``__all__`` (the admin API is reached over HTTP, see :doc:`../server`, *The first administrator*); documented
for the setup code and the start options ``--reset-administrators`` and ``--admin`` (SEC-12, D1370–D1376).

.. automodule:: claudia_server.setup_code
   :members: SetupCode, normalize, code_path, write_code, read_code, remove_code

.. automodule:: claudia_server.admin_start
   :members: AdminOptions, AdminStart, ResetNote, prepare_administrators, read_password_file, load_reset_note,
      dismiss_reset_note

Heavy-call dispatch
--------------------

Resolves a document's deferred heavy formula calls (``Calculator.pending_heavy``) on the worker pool above
(decisions D37, D1314).

.. autoclass:: claudia_server.HeavyDispatcher
.. autoclass:: claudia_server.Submittable
.. autodata:: claudia_server.DEFAULT_TIMEOUT

Protocol
--------

.. autodata:: claudia_server.PROTOCOL_VERSION
.. autoclass:: claudia_server.MethodTable
.. autoclass:: claudia_server.Method
.. autoclass:: claudia_server.Limits
.. autoclass:: claudia_server.protocol.Context
.. autoclass:: claudia_server.protocol.Param
.. autoclass:: claudia_server.RequestError
.. autofunction:: claudia_server.parse_request
.. autofunction:: claudia_server.methods_for
.. autodata:: claudia_server.computes_methods
   :no-value:
.. autodata:: claudia_server.creates_methods
   :no-value:
.. autofunction:: claudia_server.creates_methods_with

Restore
-------

.. autoclass:: claudia_server.RestoreCoordinator
.. autoclass:: claudia_server.Proposal
.. autoclass:: claudia_server.Resolution
.. autoclass:: claudia_server.RestoreError

Help
----

.. autoclass:: claudia_server.HelpLibrary
.. autoclass:: claudia_server.Topic
.. autofunction:: claudia_server.parse_topic
.. autofunction:: claudia_server.default_library
.. autoclass:: claudia_server.HelpContentError

Assistant
---------

.. autoclass:: claudia_server.Assistant
.. autoclass:: claudia_server.Engine
.. autoclass:: claudia_server.Task
.. autoclass:: claudia_server.Say
.. autoclass:: claudia_server.Call
.. autoclass:: claudia_server.AsyncEngine
.. autoclass:: claudia_server.ScriptedEngine
.. autofunction:: claudia_server.stand_in_assistant_for
.. autoclass:: claudia_server.ModelEngine
.. autofunction:: claudia_server.model_assistant_for

What ``ModelEngine`` is given (not in ``__all__``; documented so its signature resolves): one question's limits, the
app's view of its documents for the model, and what the app teaches the AI about working in it (E7.2).

.. autoclass:: claudia_server.model_engine.Budget
.. autoclass:: claudia_server.model_engine.ConversationMemory
.. autoclass:: claudia_server.lens.Lens
.. autoclass:: claudia_server.lens.Recorder
.. autoclass:: claudia_server.ai_guidance.Guidance
.. autoclass:: claudia_server.ai_guidance.Recipe
.. autofunction:: claudia_server.ai_guidance.load_guidance
.. autofunction:: claudia_server.ai_guidance.parse_recipes

Printing
--------

What the apps that print share (D917): the ``language`` and ``set_language`` methods, and the rule that only people
(not the AI) change how a document prints.

.. autofunction:: claudia_server.printing.add_language_methods
.. autofunction:: claudia_server.printing.people_only

Fonts
-----

What ``create_app`` is given to serve fonts to clients (not in ``__all__``; documented so its signature resolves):
``GET /api/fonts``, ``/api/fonts/{sha256}`` and ``/api/fonts/{sha256}.woff2`` (D905). Fonts for this server only go to
its own people (D1041).

.. autoclass:: claudia_server.fonts.FontService
   :members:
.. autofunction:: claudia_server.fonts.font_router
.. autodata:: claudia_server.fonts.FONTS_FORMAT
.. autodata:: claudia_server.fonts.Origin

Hyphenation patterns for the clients' layout, the same way (D913): ``GET /api/hyphenation`` and
``/api/hyphenation/{sha256}``, and ``python -m claudia_server.hyphenation fetch DIR``.

.. autoclass:: claudia_server.hyphenation.HyphenationService
   :members:
.. autoclass:: claudia_server.hyphenation.Language
   :members:
.. autoclass:: claudia_server.hyphenation.PatternFile
   :members:
.. autofunction:: claudia_server.hyphenation.hyphenation_router
.. autofunction:: claudia_server.hyphenation.read_lock
.. autofunction:: claudia_server.hyphenation.fetch
.. autodata:: claudia_server.hyphenation.HYPHENATION_FORMAT

Containers
------------------------

What makes the picture of a container (D395; not in ``__all__``, documented so the signatures that name
it resolve): the methods that put one in a document, and the job that renders it as an ordinary edit.

.. autoclass:: claudia_server.containers.RenderDesk
   :members:

Users
-----

.. autoclass:: claudia_server.Account
.. autoclass:: claudia_server.Credentials
.. autoclass:: claudia_server.UserDirectory
.. autoclass:: claudia_server.WarmableDirectory
.. autoclass:: claudia_server.ScryptDirectory
.. autoclass:: claudia_server.AuthRefused

Server settings
----------------

Who may configure the server — a separate identity from any document's own users, above — and what they have
configured it to do.

.. autoclass:: claudia_server.AdminAccount
.. autoclass:: claudia_server.AdminDirectory
.. autofunction:: claudia_server.needs_administrator
.. autoclass:: claudia_server.AdminSession
.. autoclass:: claudia_server.AdminSessions
.. autoclass:: claudia_server.AdminContext
.. autoclass:: claudia_server.AiRuntime
.. autoclass:: claudia_server.ai_desk.ProviderDesk
.. autoclass:: claudia_server.ai_desk.Decision
.. autoclass:: claudia_server.ai_consent.AiConsent
.. autoclass:: claudia_server.ai_consent.ConsentBook
.. autofunction:: claudia_server.admin_router

Server settings ▸ Fonts (E3.13 f, D1041): ``/api/admin/fonts``, its ``files``, ``check`` and ``collections`` routes.

.. automodule:: claudia_server.admin_fonts
   :no-index:
.. autofunction:: claudia_server.admin_fonts.font_admin_routes
.. autoclass:: claudia_server.admin_fonts.FontUploads
   :members:
.. autodata:: claudia_server.admin_fonts.ADMIN_FONTS_FORMAT
.. autodata:: claudia_server.admin_fonts.HOLD_SECONDS
.. autoclass:: claudia_server.ServerSettings
.. autoclass:: claudia_server.AiSettings
.. autoclass:: claudia_server.SecuritySettings
.. autoclass:: claudia_server.TypesetSettings
.. autoclass:: claudia_server.server_settings.RenderSettings
.. autoclass:: claudia_server.server_settings.ClaudeSettings
.. autoclass:: claudia_server.Changed
.. autofunction:: claudia_server.load_settings
.. autofunction:: claudia_server.save_settings
.. autofunction:: claudia_server.load_admins
.. autofunction:: claudia_server.save_admins

Encryption
----------

.. autoclass:: claudia_server.Certificate
.. autofunction:: claudia_server.ensure_certificate
.. autoclass:: claudia_server.CertificateError
