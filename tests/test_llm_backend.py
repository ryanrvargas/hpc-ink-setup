from __future__ import annotations

from types import SimpleNamespace
import subprocess

from inkly.llm.backend import LLMBackend


def make_config():
    llm = SimpleNamespace(backend="ollama", model="llama3.1:8b")
    core = SimpleNamespace(max_prompt_length=4000)
    return SimpleNamespace(llm=llm, core=core)


def test_generate_ollama_success(monkeypatch):
    backend = LLMBackend(make_config())

    def fake_run(cmd, input, stdout, stderr, text, check, **kwargs):
        assert cmd == ["ollama", "run", "llama3.1:8b"]
        assert input == "hello"
        return SimpleNamespace(returncode=0, stdout="Hi there\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backend.generate("hello")
    assert result == "Hi there"


def test_generate_ollama_missing_binary(monkeypatch):
    backend = LLMBackend(make_config())

    def fake_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        backend.generate("hello")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == "Ollama CLI not found on PATH."


def test_generate_ollama_nonzero_exit(monkeypatch):
    backend = LLMBackend(make_config())

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="model not found")

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        backend.generate("hello")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == "Ollama generation failed: model not found"


def test_generate_ollama_empty_output(monkeypatch):
    backend = LLMBackend(make_config())

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout="   \n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        backend.generate("hello")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == "Ollama returned an empty response."
