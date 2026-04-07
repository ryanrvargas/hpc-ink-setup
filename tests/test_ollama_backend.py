from __future__ import annotations

from types import SimpleNamespace
import subprocess

from inkly.llm.backend import LLMBackend


def make_config():
    llm = SimpleNamespace(backend="ollama", model="llama3.1:8b")
    core = SimpleNamespace(max_prompt_length=4000)
    state = SimpleNamespace(inkly_home=".inkly")
    ollama = SimpleNamespace(
        tunnel_enabled=False,
        ssh_target="",
        remote_host="127.0.0.1",
        remote_port=11434,
        local_host="127.0.0.1",
        local_port=11434,
        startup_timeout_sec=2,
        manage_server=False,
    )
    return SimpleNamespace(llm=llm, core=core, state=state, ollama=ollama)


def test_generate_ollama_calls_tunnel_manager(monkeypatch):
    backend = LLMBackend(make_config())

    called = {"ensure": 0}

    fake_tunnel = SimpleNamespace(
        ensure_ready=lambda: called.__setitem__("ensure", called["ensure"] + 1)
    )

    monkeypatch.setattr(backend, "_get_ollama_tunnel", lambda: fake_tunnel)

    def fake_run(cmd, input, stdout, stderr, text, check):
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backend.generate("hello")

    assert result == "ok"
    assert called["ensure"] == 1