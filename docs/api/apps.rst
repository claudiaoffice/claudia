The apps (kernel proofs)
========================

These packages are the thin first versions that prove the kernel carries three different kinds of document. They
grow in their own epics.

computes
--------

.. automodule:: claudia_computes
   :no-members:

.. autoclass:: claudia_computes.WorkbookModel
.. autoclass:: claudia_computes.SetCells
.. autoclass:: claudia_computes.Structure
.. autoclass:: claudia_computes.AddSheet
.. autoclass:: claudia_computes.RemoveSheet
.. autoclass:: claudia_computes.CellRegion
.. autoclass:: claudia_computes.CellAnchor
.. autoclass:: claudia_computes.Chart
.. autoclass:: claudia_computes.ChartSpec
.. autoclass:: claudia_computes.ChartError
.. autoclass:: claudia_computes.AddChart
.. autoclass:: claudia_computes.RemoveChart
.. autoclass:: claudia_computes.NamedRange
.. autoclass:: claudia_computes.Names
.. autoclass:: claudia_computes.DefineName
.. autoclass:: claudia_computes.RenameName
.. autoclass:: claudia_computes.RemoveName
.. autoclass:: claudia_computes.RestoreNames
.. autoclass:: claudia_computes.spill.Table

Cell styles
~~~~~~~~~~~

A cell has a box and words, two slots of the style model (D304, D307, D311); a sheet keeps style ranges in layers,
not a style per cell.

.. automodule:: claudia_computes.cellstyles
   :no-members:

.. currentmodule:: claudia_computes

.. autoclass:: claudia_computes.CellStyles
.. autoclass:: claudia_computes.SetCellStyle
.. autoclass:: claudia_computes.CellStylesChanged
.. autofunction:: claudia_computes.layer_of

``SheetObject`` is ``VisualObject[CellAnchor]``: a shared :class:`~claudia_core.ObjectBody` and that anchor.
The object commands, region and events are shared by all three apps (:doc:`claudia_core`, E10.16, D177).

Formulas
~~~~~~~~

Formulas are parsed once into a tree, compiled into closures and calculated incrementally (``claudia_computes.calc``).
Choosing and referencing functions (``IF``, ``XLOOKUP``, ``INDEX``, ``OFFSET`` ...) and the operators are part of the
core; every function that takes cell ranges and gives a value is a ``UserFunction``:

.. autoclass:: claudia_computes.functions.base.UserFunction
.. autoclass:: claudia_computes.functions.base.Example
.. autoclass:: claudia_computes.functions.registry.FunctionRegistry
.. autoclass:: claudia_computes.functions.range.Range
.. autoclass:: claudia_computes.values.ErrorValue
.. autoclass:: claudia_computes.values.FormulaError
.. autoclass:: claudia_computes.functions.base.Bound
.. autoclass:: claudia_computes.functions.range.Grid

Every library function and core form, as one searchable catalog for the help system (E13.5/E13.6):

.. autoclass:: claudia_computes.FunctionHelp
.. autofunction:: claudia_computes.function_catalog
.. autofunction:: claudia_computes.search_functions
.. autofunction:: claudia_computes.get_function

Types that appear in the signatures above:

.. autoclass:: claudia_computes.refs.SheetId
.. autoclass:: claudia_computes.refs.CellRef
.. autoclass:: claudia_computes.refs.RangeRef
.. autoclass:: claudia_computes.refs.StructuralEdit
.. autoclass:: claudia_computes.model.Sheet

Import/export
~~~~~~~~~~~~~~

Every format package shares the Open Packaging Conventions mechanics of ``claudia_opc_io`` (D217):

.. automodule:: claudia_opc_io
   :members:

and the OpenDocument formats (odt, ods, odp) share ``claudia_odf_io``: a package from its parts, a part edited
by splicing bytes so that everything outside the edit stays the original's, the text of one paragraph changed in
place, and the list of what a file could not hold (D401):

.. automodule:: claudia_odf_io
   :members:

A base xlsx export and one additive extension openpyxl itself cannot write, pivot tables (D135):

.. automodule:: claudia_computes_io
   :members:

composes
--------

.. automodule:: claudia_composes
   :members:
   :exclude-members: AddObject, DefineImage, DefineShape, ForgetImage, ForgetShape, MoveObject, ObjectBody, ObjectSet, Paragraph, RemoveObject, ResizeObject, RotateObject, Run, SetParagraph, SetParagraphStyle, SetSnap, SetText, VisualObject, paragraph_for

.. automodule:: claudia_composes.anchors
   :no-members:

.. currentmodule:: claudia_composes

``BlockAnchor`` is documented with the rest of the package above. ``TextObject`` is ``VisualObject[BlockAnchor]``: a shared :class:`~claudia_core.ObjectBody` and that anchor
(E10.16, D179). Unlike a sheet anchor, a block anchor follows the text.

Import/export
~~~~~~~~~~~~~~

A base docx export, with open suggestions written as native Word tracked changes (D135), and odt import, export and
edit-and-reexport that keeps everything the text app does not model (D401):

.. automodule:: claudia_composes_io
   :members:

creates
-------

The presentation app has grown past a proof: see :doc:`claudia_creates`.

Import/export
~~~~~~~~~~~~~~

A base pptx export and one additive extension python-pptx itself cannot write, slide transitions (D135):

.. automodule:: claudia_creates_io
   :members:

The test-document catalogue
---------------------------

The engine that runs the round-trip test documents of all three formats (D218); the documents themselves are data,
in ``test-documents/`` at the repository root:

.. automodule:: claudia_test_documents
   :members:
