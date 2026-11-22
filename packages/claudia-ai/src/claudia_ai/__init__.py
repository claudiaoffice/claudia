"""claudia-ai: the language model behind the AI user, the prompt, and the reading of its answers (E7.1).

model            LanguageModel (the interface), ModelError
openvino_model   OpenVinoModel: a model run by OpenVINO GenAI on this machine (``pip install claudia-ai[openvino]``)
agent            Agent: what the model is asked and how its answer is read (a placeholder for the real agent, E7.5)
claude           ClaudeModel: Anthropic's Claude behind the same interface, with the reasons it can fail (E7.11)
runner           ModelRunner: one model, one question at a time, on a worker thread, with a time limit

The package knows nothing of documents, protocols or servers: ``claudia_server`` connects it to the user ``ai``.
"""

from ._version import __version__
from .agent import CALL_LIMIT, Agent, Request, ToolCall, ToolSpec, Turn
from .claude import ClaudeModel, FailureReason, ProviderError
from .model import LanguageModel, Message, ModelError
from .openvino_model import DEFAULT_DEVICE, OpenVinoModel
from .runner import ModelRunner

__all__ = [
    "__version__",
    "CALL_LIMIT",
    "ClaudeModel",
    "DEFAULT_DEVICE",
    "FailureReason",
    "Agent",
    "LanguageModel",
    "Message",
    "ModelError",
    "ModelRunner",
    "OpenVinoModel",
    "ProviderError",
    "Request",
    "ToolCall",
    "ToolSpec",
    "Turn",
]
