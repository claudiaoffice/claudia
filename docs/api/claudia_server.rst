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
