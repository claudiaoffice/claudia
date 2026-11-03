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

Types that appear in the signatures above:

.. autoclass:: claudia_computes.refs.SheetId
.. autoclass:: claudia_computes.refs.CellRef
.. autoclass:: claudia_computes.refs.RangeRef
.. autoclass:: claudia_computes.refs.StructuralEdit
.. autoclass:: claudia_computes.model.Sheet

composes
--------

.. automodule:: claudia_composes
   :members:

creates
-------

The presentation app has grown past a proof: see :doc:`claudia_creates`.
