from __future__ import annotations

from types import SimpleNamespace

from inkly.llm.ollama_tunnel import OllamaTunnelManager


def make_config(tmp_path, **overrides):
    state = SimpleNamespace(inkly_home=tmp_path / ".inkly")
    llm = SimpleNamespace(backend="ollama", model="llama3.1:8b")
    core = SimpleNamespace(max_prompt_length=4000)

    ollama_defaults = dict(
        tunnel_enabled=False,
        ssh_target="",
        remote_host="127.0.0.1",
        remote_port=11434,
        local_host="127.0.0.1",
        local_port=11434,
        startup_timeout_sec=2,
        manage_server=False,
    )
    ollama_defaults.update(overrides)
    ollama = SimpleNamespace(**ollama_defaults)

    return SimpleNamespace(state=state, llm=llm, core=core, ollama=ollama)


def test_ensure_ready_uses_existing_local_service(monkeypatch, tmp_path):
    manager = OllamaTunnelManager(make_config(tmp_path))

    monkeypatch.setattr(manager, "_is_local_healthy", lambda timeout=1.0: True)

    # Should not raise and should not try to open a tunnel.
    manager.ensure_ready()


def test_ensure_ready_fails_when_disabled_and_unhealthy(monkeypatch, tmp_path):
    manager = OllamaTunnelManager(make_config(tmp_path))

    monkeypatch.setattr(manager, "_is_local_healthy", lambda timeout=1.0: False)

    try:
        manager.ensure_ready()
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == (
            "Ollama is not reachable on localhost and SSH tunneling is disabled."
        )


def test_ensure_ready_starts_tunnel_when_enabled(monkeypatch, tmp_path):
    manager = OllamaTunnelManager(
        make_config(
            tmp_path,
            tunnel_enabled=True,
            ssh_target="rrv9177@gpuj042",
        )
    )

    calls = {"start": 0}

    health_checks = iter([False, True])

    def fake_health(timeout=1.0):
        return next(health_checks)

    def fake_reuse():
        return False

    def fake_start():
        calls["start"] += 1

    monkeypatch.setattr(manager, "_is_local_healthy", fake_health)
    monkeypatch.setattr(manager, "_reuse_existing_tunnel", fake_reuse)
    monkeypatch.setattr(manager, "_start_tunnel", fake_start)

    manager.ensure_ready()
    assert calls["start"] == 1


def test_manage_server_explicitly_disabled(monkeypatch, tmp_path):
    manager = OllamaTunnelManager(
        make_config(
            tmp_path,
            tunnel_enabled=False,
            manage_server=True,
        )
    )

    monkeypatch.setattr(manager, "_is_local_healthy", lambda timeout=1.0: False)

    try:
        manager.ensure_ready()
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "Automatic Ollama server submission is disabled." in str(exc)