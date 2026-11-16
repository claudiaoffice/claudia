claudia-fonts API reference
===========================

.. module:: claudia_fonts

The public API is exactly what ``claudia_fonts.__all__`` lists (see :doc:`../versioning`). The package is the single
source of truth for fonts on a server: the typesetting engine and the browsers get the same bytes from one catalogue.

Collections
-----------

.. autodata:: claudia_fonts.COLLECTION_FILE
.. autoexception:: claudia_fonts.RecordError
.. autoclass:: claudia_fonts.CollectionRecord
   :members:
.. autoclass:: claudia_fonts.Collection
   :members:

Fonts
-----

.. autoexception:: claudia_fonts.FontProblem
.. autoclass:: claudia_fonts.FontFile
   :members:
.. autoclass:: claudia_fonts.Axis
   :members:
.. autofunction:: claudia_fonts.read_font

The catalogue
-------------

.. autodata:: claudia_fonts.DEFAULT_SUBSTITUTIONS
.. autoclass:: claudia_fonts.Problem
.. autoclass:: claudia_fonts.Resolution
.. autoclass:: claudia_fonts.Catalogue
   :members:

For browsers
------------

.. autoexception:: claudia_fonts.NotServable
.. autoclass:: claudia_fonts.WebFontCache
   :members:
.. autofunction:: claudia_fonts.font_face_css

For the typesetting engine
--------------------------

.. autoclass:: claudia_fonts.JobFonts
.. autofunction:: claudia_fonts.write_fontconfig

The starter set
---------------

A pinned set of open fonts an operator fetches once (``python -m claudia_fonts fetch DIR``), each file checked by its
SHA-256 against ``starter.lock.json`` (D905). ``LockedFile`` and ``FetchError`` are
:class:`claudia_file_writer.PinnedFile` and :class:`claudia_file_writer.FetchError` (D701), which fetch the
hyphenation patterns as well.

.. autofunction:: claudia_fonts.fetch
.. autofunction:: claudia_fonts.read_lock
.. autofunction:: claudia_fonts.collection_folders
.. autoclass:: claudia_fonts.LockedCollection
