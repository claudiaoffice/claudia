claudia-creates API reference
=============================

.. module:: claudia_creates

The public API is exactly what ``claudia_creates.__all__`` lists (see :doc:`../versioning`).

Shapes
------

A shape is one JSON file; the layout of the file is described with :mod:`claudia_creates.shapes`.

.. automodule:: claudia_creates.shapes
   :no-members:

.. autoclass:: claudia_creates.ShapeLibrary
.. autoclass:: claudia_core.ShapeDefinition
   :no-index:
.. autoexception:: claudia_creates.ShapeError
.. autofunction:: claudia_creates.parse_shape

Styles
------

.. automodule:: claudia_creates.styles
   :no-members:

.. autoclass:: claudia_core.StyleDef
   :no-index:
.. py:data:: claudia_creates.BUILTIN_STYLES
   :type: tuple[StyleDef, ...]

   The styles every document can use, by id: ``body-text``, ``plain-shape`` and ``plain-image``.

.. py:data:: claudia_creates.ALLOWED_CSS
   :type: frozenset[str]

   The CSS properties a style may set. Widened on purpose, one property at a time, as the apps need them.

The slide model
---------------

.. automodule:: claudia_creates.model
   :no-members:

An image object's ``image`` and ``imported`` are a :class:`claudia_core.ImageAsset` id and a
:class:`claudia_core.ImageImport`, shared with composes and computes; this app only places one on a slide and keeps
its proportions, exactly as it does for a shape with an ``aspect``.

.. autoclass:: claudia_creates.SlideModel
.. autoclass:: claudia_creates.SlideAnchor

``SlideObject`` is ``VisualObject[SlideAnchor]``: a shared
:class:`~claudia_core.ObjectBody` and that anchor (E10.16, D177).
.. autodata:: claudia_creates.SLIDE_WIDTH
.. autodata:: claudia_creates.SLIDE_HEIGHT
.. autodata:: claudia_creates.MIN_OBJECT_SIZE
.. autodata:: claudia_creates.MAX_OBJECT_TEXT
.. autodata:: claudia_creates.MAX_OBJECTS_PER_SLIDE
.. autodata:: claudia_creates.ASPECT_TOLERANCE
.. autodata:: claudia_creates.OBJECT_KINDS

Commands
--------

.. automodule:: claudia_creates.commands
   :no-members:

.. autoclass:: claudia_creates.AddSlide
.. autoclass:: claudia_creates.RemoveSlide

Printing
--------

.. automodule:: claudia_creates.printing
   :no-members:

How a presentation prints (D917): slides one to a page or handouts, on a page set up as in composes; its language is
:class:`claudia_core.SetLanguage`'s.

.. autoclass:: claudia_creates.PrintSetup
.. autoexception:: claudia_creates.PrintSetupError
.. autodata:: claudia_creates.LAYOUTS
.. autoclass:: claudia_creates.SetPrintSetup
.. autoclass:: claudia_creates.PrintSetupChanged

Regions
-------

The object commands, the object region and the object events are shared by all three apps and are
documented in :doc:`claudia_core`:
:class:`~claudia_core.AddObject`, :class:`~claudia_core.RemoveObject`,
:class:`~claudia_core.MoveObject`, :class:`~claudia_core.ResizeObject`,
:class:`~claudia_core.RotateObject`, :class:`~claudia_core.SetText`, :class:`~claudia_core.SetSnap`, :class:`~claudia_core.DescribeObject`,
:class:`~claudia_core.DefineShape`, :class:`~claudia_core.ForgetShape`,
:class:`~claudia_core.DefineImage`, :class:`~claudia_core.ForgetImage`, :class:`~claudia_core.ObjectSet`.

State events
------------

What a view is told when a command changed the document; the server sends them as they are (``to_data``), except
``objects``, whose ``to_data_for(viewer)`` masks an image's import record for anyone but its importer.

.. autoclass:: claudia_creates.SlidesChanged
