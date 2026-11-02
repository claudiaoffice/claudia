"""The OpenVINO model: against a stand-in for ``openvino_genai`` and, if it is installed, the names of the real one."""

import enum
import sys
import types

import pytest

from claudia_ai import ModelError, OpenVinoModel

USER = [{"role": "user", "content": "u"}]


class Status(enum.Enum):
    RUNNING = 0
    STOP = 1


def fake_genai(text="the answer is four", fail_loading=None, record=None):
    record = {} if record is None else record
    genai = types.SimpleNamespace(StreamingStatus=Status)

    class GenerationConfig:
        pass

    class Tokenizer:
        def apply_chat_template(self, messages, add_generation_prompt):
            record["messages"], record["generation_prompt"] = messages, add_generation_prompt
            return "|".join(m["role"] + ":" + m["content"] for m in messages) + "|assistant:"

    class Result:
        def __init__(self, texts):
            self.texts = texts

    class LLMPipeline:
        def __init__(self, path, device):
            if fail_loading:
                raise RuntimeError(fail_loading)
            record["loaded"] = (path, device)

        def get_tokenizer(self):
            return Tokenizer()

        def generate(self, prompt, config, streamer):
            record["prompt"], record["config"] = prompt, config
            made = []
            for word in text.split():
                made.append(word)
                if streamer(word + " ") == Status.STOP:
                    break
            return Result([" ".join(made)])

    genai.GenerationConfig, genai.LLMPipeline = GenerationConfig, LLMPipeline
    return genai


@pytest.fixture
def folder(tmp_path):
    model = tmp_path / "qwen-ov"
    model.mkdir()
    (model / "openvino_model.xml").write_text("<net/>")
    return model


def test_the_model_is_loaded_and_answers(folder):
    record = {}
    model = OpenVinoModel(folder, "NPU", genai=fake_genai(record=record))
    assert record["loaded"] == (str(folder), "NPU") and model.name == "qwen-ov on NPU"
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert model.generate(messages, max_new_tokens=77, stop=lambda: False) == "the answer is four"
    config = record["config"]
    assert (config.max_new_tokens, config.apply_chat_template, config.do_sample) == (77, False, True)
    assert record["generation_prompt"] is True and record["prompt"] == "system:s|user:u|assistant:"


def test_the_gpu_is_the_default_device(folder):
    record = {}
    OpenVinoModel(folder, genai=fake_genai(record=record))
    assert record["loaded"][1] == "GPU"


def test_generation_stops_when_asked(folder):
    model = OpenVinoModel(folder, genai=fake_genai("one two three four"))
    seen = []

    def stop():
        seen.append(1)
        return len(seen) >= 2

    assert model.generate(USER, max_new_tokens=9, stop=stop) == "one two"


def test_an_older_library_stops_by_returning_true(folder):
    genai = fake_genai()
    del genai.StreamingStatus

    def generate(self, prompt, config, streamer):
        stopped = streamer("a ")
        return types.SimpleNamespace(texts=["stopped" if stopped else "went on"])

    genai.LLMPipeline.generate = generate
    model = OpenVinoModel(folder, genai=genai)
    assert model.generate(USER, max_new_tokens=9, stop=lambda: True) == "stopped"


def test_greedy_decoding_can_be_chosen(folder):
    record = {}
    model = OpenVinoModel(folder, temperature=0, genai=fake_genai(record=record))
    model.generate(USER, max_new_tokens=5, stop=lambda: False)
    assert not hasattr(record["config"], "do_sample")


def test_a_failing_generation_is_a_model_error(folder):
    genai = fake_genai()
    genai.LLMPipeline.generate = lambda self, *args: (_ for _ in ()).throw(RuntimeError("out of memory"))
    with pytest.raises(ModelError, match="the model failed: out of memory"):
        OpenVinoModel(folder, genai=genai).generate(USER, max_new_tokens=5, stop=lambda: False)


def test_start_up_problems_say_what_to_do(tmp_path, folder):
    with pytest.raises(ModelError, match="is not a folder.*optimum-cli export openvino"):
        OpenVinoModel(tmp_path / "nope", genai=fake_genai())
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ModelError, match=r"openvino_model\.xml is missing"):
        OpenVinoModel(empty, genai=fake_genai())
    with pytest.raises(ModelError, match="cannot load the model.*on NPU: no such device.*--ai-device"):
        OpenVinoModel(folder, "NPU", genai=fake_genai(fail_loading="no such device"))


def test_a_missing_library_says_how_to_install_it(folder, monkeypatch):
    monkeypatch.setitem(sys.modules, "openvino_genai", None)  # makes the import fail
    with pytest.raises(ModelError, match="pip install openvino-genai"):
        OpenVinoModel(folder)


def test_the_names_used_exist_in_the_real_library():
    genai = pytest.importorskip("openvino_genai")
    config = genai.GenerationConfig()
    config.max_new_tokens, config.apply_chat_template, config.do_sample, config.temperature = 5, False, True, 0.3
    assert (config.max_new_tokens, config.apply_chat_template, config.do_sample) == (5, False, True)
    assert {"RUNNING", "STOP"} <= set(genai.StreamingStatus.__members__)
    assert callable(genai.LLMPipeline.generate) and callable(genai.LLMPipeline.get_tokenizer)
    assert callable(genai.Tokenizer.apply_chat_template)
