claudia-search API reference
============================

.. module:: claudia_search

The public API is exactly what ``claudia_search.__all__`` lists (see :doc:`../versioning`). The search of all three
apps: a person's description of what to find (:class:`Query`), compiled (:class:`CompiledSearch`) and run on the
``regex`` package with a deadline on every call (SEC-18), and the app-neutral part of searching a document and
planning a replacement, every place named by the app's own ``at`` (CODE-18). It was ``claudia_core.search`` until
claudia-core 0.19.0: the kernel imports the standard library only, and ``regex`` is not part of it.

What to find
------------

.. autoclass:: claudia_search.Query
   :members:
.. autoclass:: claudia_search.Part
   :members:
.. autoclass:: claudia_search.Condition
   :members:
.. autodata:: claudia_search.MODES
.. autodata:: claudia_search.WHOLE
.. autodata:: claudia_search.COMBINE
.. autodata:: claudia_search.COUNTS
.. autodata:: claudia_search.CONDITIONS
.. autoexception:: claudia_search.SearchError

Running it
----------

.. autoclass:: claudia_search.CompiledSearch
   :members:
.. autoclass:: claudia_search.Match
   :members:
.. autoexception:: claudia_search.SearchTimeout
.. autodata:: claudia_search.MAX_SECONDS

Searching a document
--------------------

.. autoclass:: claudia_search.Text
   :members:
.. autodata:: claudia_search.Location
.. autofunction:: claudia_search.location_key
.. autofunction:: claudia_search.scan
.. autoclass:: claudia_search.Scan
   :members:
.. autoclass:: claudia_search.Hit
   :members:
.. autoclass:: claudia_search.LeftOut
   :members:
.. autodata:: claudia_search.MAX_LISTED

Planning a replacement
----------------------

.. autofunction:: claudia_search.plan
.. autoclass:: claudia_search.Plan
   :members:
.. autoclass:: claudia_search.Change
   :members:
.. autoclass:: claudia_search.Skip
   :members:
.. autodata:: claudia_search.Refusal
