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
.. autoclass:: claudia_creates.ShapeDefinition
.. autoexception:: claudia_creates.ShapeError
.. autofunction:: claudia_creates.parse_shape

Styles
------

.. automodule:: claudia_creates.styles
   :no-members:

.. autoclass:: claudia_creates.Style
.. py:data:: claudia_creates.BUILTIN_STYLES
   :type: dict[str, Style]

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
.. autoclass:: claudia_creates.SlideObject
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

.. autoclass:: claudia_creates.AddObject
.. autoclass:: claudia_creates.MoveObject
.. autoclass:: claudia_creates.ResizeObject
.. autoclass:: claudia_creates.SetText
.. autoclass:: claudia_creates.RemoveObject
.. autoclass:: claudia_creates.DefineShape
.. autoclass:: claudia_creates.ForgetShape
.. autoclass:: claudia_creates.DefineImage
.. autoclass:: claudia_creates.ForgetImage
.. autoclass:: claudia_creates.AddSlide
.. autoclass:: claudia_creates.RemoveSlide

Regions
-------

.. autoclass:: claudia_creates.ObjectSet

State events
------------

What a view is told when a command changed the document; the server sends them as they are (``to_data``), except
``objects``, whose ``to_data_for(viewer)`` masks an image's import record for anyone but its importer.

.. autoclass:: claudia_creates.ObjectsChanged
.. autoclass:: claudia_creates.ShapesChanged
.. autoclass:: claudia_creates.ImagesChanged
.. autoclass:: claudia_creates.SlidesChanged
