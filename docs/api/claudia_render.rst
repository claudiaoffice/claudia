claudia-render API reference
============================

.. module:: claudia_render

The public API is exactly what ``claudia_render.__all__`` lists (see :doc:`../versioning`). A *rendered text
container* keeps a text and shows a picture made from it (D390). This package turns the text into a checked SVG: a
plugin says what it needs and how to ask for it, the administrator's tool registry says which program stands behind
each name, and the service enforces every safety rule in one place (D391-D393). The help topic
``render.configure-tools`` explains the installation to administrators.

The service
-----------

.. autoclass:: claudia_render.RenderService
   :members:
.. autoclass:: claudia_render.RenderPolicy
.. autoclass:: claudia_render.Rendered
.. autofunction:: claudia_render.builtin_registry

Plugins
-------

A plugin is a manifest (data) and, for the built-in LaTeX type, an adapter (code). Third parties bring manifests only.

.. autoclass:: claudia_render.Plugin
   :members:
.. autoclass:: claudia_render.CliPlugin
.. autoclass:: claudia_render.LatexPlugin
.. autoclass:: claudia_render.RenderRequest
.. autoclass:: claudia_render.RenderResult
.. autoexception:: claudia_render.RenderFailed
.. autoclass:: claudia_render.PluginRegistry
   :members:
.. autoclass:: claudia_render.LoadReport
.. autoexception:: claudia_render.UnknownType

The manifest
------------

.. autodata:: claudia_render.API_VERSION
.. autofunction:: claudia_render.parse_manifest
.. autoclass:: claudia_render.Manifest
.. autoclass:: claudia_render.ToolRequirement
.. autoclass:: claudia_render.ParamSpec
.. autoclass:: claudia_render.CliSpec
.. autoclass:: claudia_render.LimitSpec
.. autoclass:: claudia_render.EditorHints
.. autoclass:: claudia_render.Forbidden
.. autoexception:: claudia_render.ManifestError

The administrator's tools
-------------------------

.. autodata:: claudia_render.HELP_TOPIC
.. autoclass:: claudia_render.ToolRegistry
   :members:
.. autoclass:: claudia_render.ToolEntry
.. autoclass:: claudia_render.ResolvedTool
   :members:
.. autoclass:: claudia_render.ToolStatus
.. autoexception:: claudia_render.ToolUnavailable

What a tool complains about, and the picture
--------------------------------------------

.. autodata:: claudia_render.DIAGNOSTIC_READERS
.. autoclass:: claudia_render.Diagnostic
   :members:
.. autofunction:: claudia_render.read_diagnostics
.. autofunction:: claudia_render.svg_size
.. autofunction:: claudia_render.default_alt
