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
.. autoclass:: claudia_server.HubError

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

Assistant
---------

.. autoclass:: claudia_server.Assistant
.. autoclass:: claudia_server.Engine
.. autoclass:: claudia_server.Task
.. autoclass:: claudia_server.Say
.. autoclass:: claudia_server.Call
.. autoclass:: claudia_server.ScriptedEngine
.. autofunction:: claudia_server.stand_in_assistant_for

Users
-----

.. autoclass:: claudia_server.Account
.. autoclass:: claudia_server.Credentials
.. autoclass:: claudia_server.UserDirectory
.. autoclass:: claudia_server.ScryptDirectory
.. autoclass:: claudia_server.AuthRefused

Encryption
----------

.. autoclass:: claudia_server.Certificate
.. autofunction:: claudia_server.ensure_certificate
.. autoclass:: claudia_server.CertificateError
