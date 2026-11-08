claudia-ai API reference
========================

.. module:: claudia_ai

The language model behind the AI user (E7.1): the interface to a model, the OpenVINO model, the prompt and the reading
of the answer, and the runner that gives the whole server one model and one question at a time. The package knows
nothing of documents or protocols; ``claudia_server`` connects it to the user ``ai`` (see :doc:`../server`). Like the
apps it is a first version and not yet under the API snapshot rule (E11.5).

The model
---------

.. autoclass:: claudia_ai.LanguageModel
.. autoclass:: claudia_ai.OpenVinoModel
.. autoclass:: claudia_ai.ModelError
.. autodata:: claudia_ai.DEFAULT_DEVICE
.. py:data:: claudia_ai.Message

   One message of a conversation: ``{"role": "system" | "user" | "assistant", "content": text}``.

The agent
---------

.. autoclass:: claudia_ai.Agent
.. autoclass:: claudia_ai.Request
.. autoclass:: claudia_ai.Turn
.. autoclass:: claudia_ai.ToolSpec
.. autoclass:: claudia_ai.ToolCall
.. autodata:: claudia_ai.CALL_LIMIT

The runner
----------

.. autoclass:: claudia_ai.ModelRunner
