from __future__ import annotations

import subprocess
from types import SimpleNamespace
from inkly.llm.backend import LLMBackend


def make_config():
    llm = SimpleNamespace(backend="ollama", model="llama3.1:8b")
    core = SimpleNamespace(max_prompt_length=4000)
    state = SimpleNamespace(inkly_home=".inkly")
    ollama = SimpleNamespace(
        mode="cli_run",
        command_path="",
        command_args=[],
        tunnel_enabled=False,
        ssh_target="",
        remote_host="127.0.0.1",
        remote_port=11434,
        local_host="127.0.0.1",
        local_port=11434,
        startup_timeout_sec=2,
        manage_server=False,
        use_direct_host=False,
        direct_host="",
        direct_port=11434,
    )
    return SimpleNamespace(llm=llm, core=core, state=state, ollama=ollama)


def test_generate_ollama_calls_tunnel_manager(monkeypatch):
    cfg = make_config()
    cfg.ollama.mode = "ssh_tunnel"
    cfg.ollama.tunnel_enabled = True
    cfg.ollama.ssh_target = "rrv9177@gpu1"

    backend = LLMBackend(cfg)

    called = {"ensure": 0}

    fake_tunnel = SimpleNamespace(
        ensure_ready=lambda: called.__setitem__("ensure", called["ensure"] + 1)
    )

    monkeypatch.setattr(backend, "_get_ollama_tunnel", lambda: fake_tunnel)

    def fake_run(cmd, input, stdout, stderr, text, check, **kwargs):
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backend.generate("hello")

    assert result == "ok"
    assert called["ensure"] == 1


def test_generate_ollama_uses_direct_host(monkeypatch):
    cfg = make_config()
    cfg.ollama.mode = "direct_host"
    cfg.ollama.use_direct_host = True
    cfg.ollama.direct_host = "gpu1"
    cfg.ollama.direct_port = 11434

    backend = LLMBackend(cfg)

    captured = {}

    def fake_run(cmd, input, stdout, stderr, text, check, **kwargs):
        captured["env"] = kwargs.get("env", {})
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backend.generate("hello")

    assert result == "ok"
    assert captured["env"]["OLLAMA_HOST"] == "http://gpu1:11434"


def test_generate_ollama_admin_command_uses_stdin(monkeypatch):
    cfg = make_config()
    cfg.ollama.mode = "admin_command"
    cfg.ollama.command_path = "/opt/ollama/bin/ollama"
    cfg.ollama.command_args = []

    backend = LLMBackend(cfg)
    captured = {}

    def fake_run(cmd, input, stdout, stderr, text, check, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = input
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backend.generate("hello")

    assert result == "ok"
    assert captured["cmd"] == ["/opt/ollama/bin/ollama"]
    assert captured["input"] == "hello"


def test_generate_ollama_admin_command_missing_binary(monkeypatch):
    cfg = make_config()
    cfg.ollama.mode = "admin_command"
    cfg.ollama.command_path = "/opt/ollama/bin/ollama"

    backend = LLMBackend(cfg)

    def fake_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        backend.generate("hello")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "Admin Ollama command not found" in str(exc)


def test_admin_command_strips_spinner_and_ansi(monkeypatch):
    cfg = make_config()
    cfg.ollama.mode = "admin_command"
    cfg.ollama.command_path = "/opt/ollama/ollama"
    cfg.ollama.command_args = []

    backend = LLMBackend(cfg)

    fake_stdout = "\x1b[?25l\n⠋\n⠙\nHello from model\n\x1b[?25h\n"

    def fake_run(cmd, input, stdout, stderr, text, check, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=fake_stdout,
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backend.generate("hello")
    assert result == "Hello from model"


def test_admin_command_raises_when_cleaned_output_is_empty(monkeypatch):
    cfg = make_config()
    cfg.ollama.mode = "admin_command"
    cfg.ollama.command_path = "/opt/ollama/ollama"
    cfg.ollama.command_args = []

    backend = LLMBackend(cfg)

    fake_stdout = "\x1b[?25l\n⠋\n⠙\n\x1b[?25h\n"

    def fake_run(cmd, input, stdout, stderr, text, check, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=fake_stdout,
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        backend.generate("hello")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "empty response" in str(exc).lower()
