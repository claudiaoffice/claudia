"""A chat model run by OpenVINO GenAI on this machine's CPU, GPU or NPU (D13)."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .model import Message, ModelError

DEFAULT_DEVICE = "GPU"  # D13: OpenVINO is the primary runtime, the GPU the default device
INSTALL_HINT = "install it with `pip install openvino-genai`"
CONVERT_HINT = (
    "a folder with a model converted for OpenVINO is needed, e.g. made with "
    "`optimum-cli export openvino --model Qwen/Qwen2.5-7B-Instruct --weight-format int4 qwen-ov` "
    "or downloaded from huggingface.co/OpenVINO"
)


class OpenVinoModel:
    """A chat model run by ``openvino_genai.LLMPipeline``.

    ``model_dir`` holds the converted model (``openvino_model.xml``, the tokenizer, ``config.json``); ``device`` is
    what OpenVINO calls it: CPU, GPU, NPU or AUTO. The model is loaded here, in the constructor, so a wrong path, a
    missing library or a device that is not there is a start-up error and not a surprise at the first question.
    ``genai`` is the module to use (``openvino_genai``; given in tests). ``temperature`` 0 means greedy decoding.
    """

    def __init__(
        self, model_dir: str | Path, device: str = DEFAULT_DEVICE, *, temperature: float = 0.3, genai: Any = None
    ):
        self.path = Path(model_dir)
        self.device = device
        self.temperature = temperature
        self.name = f"{self.path.name} on {device}"
        if not self.path.is_dir():
            raise ModelError(f"{self.path} is not a folder: {CONVERT_HINT}")
        if not (self.path / "openvino_model.xml").is_file():
            raise ModelError(f"{self.path} holds no OpenVINO model (openvino_model.xml is missing): {CONVERT_HINT}")
        self._genai = genai if genai is not None else self._import_genai()
        try:
            self._pipe = self._genai.LLMPipeline(str(self.path), device)
            self._tokenizer = self._pipe.get_tokenizer()
        except Exception as exc:  # the library raises RuntimeError and friends; the text says what is wrong
            raise ModelError(
                f"cannot load the model from {self.path} on {device}: {exc} (another device: --ai-device CPU)"
            ) from exc

    @staticmethod
    def _import_genai() -> Any:
        try:
            return importlib.import_module("openvino_genai")
        except ImportError as exc:
            raise ModelError(f"openvino-genai is not installed: {INSTALL_HINT}") from exc

    def generate(self, messages: list[Message], *, max_new_tokens: int, stop: Callable[[], bool]) -> str:
        """The next message of the assistant; stops early (with what it has) when ``stop()`` turns true."""
        genai = self._genai
        try:
            prompt = self._tokenizer.apply_chat_template(messages, add_generation_prompt=True)
            config = genai.GenerationConfig()
            config.max_new_tokens = max_new_tokens
            config.apply_chat_template = False  # the template was applied above
            if self.temperature > 0:
                config.do_sample = True
                config.temperature = self.temperature
            status = getattr(genai, "StreamingStatus", None)  # newer versions: an enum; older ones: True stops
            keep_going, halt = (status.RUNNING, status.STOP) if status is not None else (False, True)
            pieces: list[str] = []

            def streamer(piece: str):
                pieces.append(piece)
                return halt if stop() else keep_going

            result = self._pipe.generate(prompt, config, streamer)
            texts = getattr(result, "texts", None)
            text = texts[0] if texts else str(result)
        except Exception as exc:
            raise ModelError(f"the model failed: {exc}") from exc
        return text or "".join(pieces)
