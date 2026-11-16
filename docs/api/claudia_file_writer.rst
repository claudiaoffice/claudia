claudia-file-writer API reference
=================================

.. module:: claudia_file_writer

The public API is exactly what ``claudia_file_writer.__all__`` lists (see :doc:`../versioning`). How a Claudia server
writes a file (D701): all at once, so a reader never sees a part of one; retried on Windows, where a file just written
is held for a moment by antivirus scanning and indexing; once only for a file named by its contents; and fetched files
checked against the SHA-256 their lock gives. The standard library only, so every package that writes files depends on
it; the kernel does no I/O and does not.

Writing a file
--------------

.. autofunction:: claudia_file_writer.write_atomically
.. autofunction:: claudia_file_writer.atomic_file
.. autofunction:: claudia_file_writer.write_once
.. autoclass:: claudia_file_writer.Replacer
   :members:
.. autofunction:: claudia_file_writer.fsync_directory

Pinned files
------------

.. autoclass:: claudia_file_writer.PinnedFile
   :members:
.. autofunction:: claudia_file_writer.fetch_pinned
.. autofunction:: claudia_file_writer.download
.. autoexception:: claudia_file_writer.FetchError
