claudia-typeset API reference
=============================

.. module:: claudia_typeset

The public API is exactly what ``claudia_typeset.__all__`` lists (see :doc:`../versioning`). A formula or a block of
text goes in, a checked SVG comes out; XeLaTeX runs in a sandbox with the fonts of a `claudia_fonts.Catalogue`.

The service
-----------

.. autoclass:: claudia_typeset.Typesetter
   :members:
.. autoclass:: claudia_typeset.Typeset
.. autoexception:: claudia_typeset.TypesetFailed
.. autoexception:: claudia_typeset.EngineUnavailable

Finding and checking LaTeX
--------------------------

Installing LaTeX is the person's job; these say where its programs are, and what is wrong when they are not found
(the help topic ``typeset.configure-latex`` explains the installation).

.. autodata:: claudia_typeset.SETTINGS
.. autodata:: claudia_typeset.HELP_TOPIC
.. autofunction:: claudia_typeset.resolve_program
.. autoclass:: claudia_typeset.Diagnosis
   :members:
.. autoclass:: claudia_typeset.Step
.. autofunction:: claudia_typeset.hint_for

What is asked
-------------

.. autoclass:: claudia_typeset.Mode
   :members:
.. autoclass:: claudia_typeset.Job
   :members:
.. autoclass:: claudia_typeset.Limits
   :members:
.. autoexception:: claudia_typeset.BadJob

The TeX source and its errors
-----------------------------

.. autofunction:: claudia_typeset.build_source
.. autoclass:: claudia_typeset.Built
.. autofunction:: claudia_typeset.parse_log
.. autoclass:: claudia_typeset.TexError
.. autoexception:: claudia_typeset.FontUnavailable

The result
----------

.. autofunction:: claudia_typeset.check_svg
.. autoexception:: claudia_typeset.UnsafeOutput
.. autofunction:: claudia_typeset.cache_key
.. autoclass:: claudia_typeset.ResultCache
   :members:

The sandbox
-----------

.. autofunction:: claudia_typeset.run_sandboxed
.. autoclass:: claudia_typeset.Completed
.. autoexception:: claudia_typeset.SandboxError
.. autoexception:: claudia_typeset.Timeout
.. autoexception:: claudia_typeset.OutputTooLarge
