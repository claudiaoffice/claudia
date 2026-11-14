claudia-server API reference
============================

.. module:: claudia_server

The public API is exactly what ``claudia_server.__all__`` lists (see :doc:`../versioning`). The network protocol itself
is described on :doc:`../server`.

Application
-----------

.. autofunction:: claudia_server.create_app
.. autoclass:: claudia_server.Gateway

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

Worker pool
-----------

.. autoclass:: claudia_server.WorkerPool
.. autodata:: claudia_server.DEFAULT_WORKERS

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

What ``ModelEngine`` is given (not in ``__all__``; documented so its signature resolves): one question's limits, and the
app's view of its documents for the model.

.. autoclass:: claudia_server.model_engine.Budget
.. autoclass:: claudia_server.lens.Lens
.. autoclass:: claudia_server.lens.Recorder

Printing
--------

What the apps that print share (D917): the ``language`` and ``set_language`` methods, and the rule that only people
(not the AI) change how a document prints.

.. autofunction:: claudia_server.printing.add_language_methods
.. autofunction:: claudia_server.printing.people_only

Fonts
-----

What ``create_app`` is given to serve fonts to clients (not in ``__all__``; documented so its signature resolves):
``GET /api/fonts``, ``/api/fonts/{sha256}`` and ``/api/fonts/{sha256}.woff2`` (D905).

.. autoclass:: claudia_server.fonts.FontService
   :members:
.. autofunction:: claudia_server.fonts.font_router
.. autodata:: claudia_server.fonts.FONTS_FORMAT

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
.. autoexception:: claudia_server.hyphenation.FetchError
.. autodata:: claudia_server.hyphenation.HYPHENATION_FORMAT

Rendered text containers
------------------------

What makes the picture of a rendered text container (D395; not in ``__all__``, documented so the signatures that name
it resolve): the methods that put one in a document, and the job that renders it as an ordinary edit.

.. autoclass:: claudia_server.rendered.RenderDesk
   :members:

Users
-----

.. autoclass:: claudia_server.Account
.. autoclass:: claudia_server.Credentials
.. autoclass:: claudia_server.UserDirectory
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
.. autofunction:: claudia_server.admin_router
.. autoclass:: claudia_server.ServerSettings
.. autoclass:: claudia_server.AiSettings
.. autoclass:: claudia_server.TypesetSettings
.. autoclass:: claudia_server.server_settings.RenderSettings
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
