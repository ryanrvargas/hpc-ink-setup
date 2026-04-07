from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


class OllamaTunnelManager:
    """
    Manage an optional SSH tunnel from the login node to a remote Ollama server.

    Current behavior:
    - Reuse a healthy local Ollama endpoint if one already exists
    - Start an SSH local-forward tunnel only when enabled
    - Never submit Slurm jobs

    Expected remote layout:
    - Ollama server already running on the remote host
    - Remote Ollama reachable on remote_host:remote_port
    """

    def __init__(self, config) -> None:
        self.config = config
        self.ollama_cfg = config.ollama

        run_dir = Path(self.config.state.inkly_home).expanduser() / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        self.state_path = run_dir / "ollama_tunnel.json"

    def ensure_ready(self) -> None:
        """
        Ensure a local Ollama endpoint exists at local_host:local_port.

        If localhost is already healthy, do nothing.
        If not healthy and tunneling is enabled, open a tunnel and wait for health.
        If automatic server management is requested, fail explicitly because it is
        intentionally disabled for now.
        """
        if self._is_local_healthy():
            return

        if self.ollama_cfg.manage_server:
            raise RuntimeError(
                "Automatic Ollama server submission is disabled. "
                "Ask the cluster admin to keep the remote Ollama server running."
            )

        if not self.ollama_cfg.tunnel_enabled:
            raise RuntimeError(
                "Ollama is not reachable on localhost and SSH tunneling is disabled."
            )

        if self._reuse_existing_tunnel():
            return

        self._start_tunnel()
        self._wait_until_healthy()

    def _local_api_base(self) -> str:
        return (
            f"http://{self.ollama_cfg.local_host}:{self.ollama_cfg.local_port}/api"
        )

    def _health_url(self) -> str:
        return f"{self._local_api_base()}/tags"

    def _is_local_healthy(self, timeout: float = 1.0) -> bool:
        try:
            with urlopen(self._health_url(), timeout=timeout) as response:
                return 200 <= response.status < 300
        except (URLError, OSError):
            return False

    def _read_state(self) -> dict | None:
        if not self.state_path.exists():
            return None

        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_state(self, payload: dict) -> None:
        self.state_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _remove_state(self) -> None:
        try:
            self.state_path.unlink()
        except FileNotFoundError:
            pass

    def _pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _reuse_existing_tunnel(self) -> bool:
        state = self._read_state()
        if not state:
            return False

        pid = state.get("pid")
        if not isinstance(pid, int):
            self._remove_state()
            return False

        if not self._pid_alive(pid):
            self._remove_state()
            return False

        # If the tunnel process still exists, verify the local API really works.
        if self._is_local_healthy():
            return True

        return False

    def _start_tunnel(self) -> None:
        spec = (
            f"{self.ollama_cfg.local_host}:{self.ollama_cfg.local_port}:"
            f"{self.ollama_cfg.remote_host}:{self.ollama_cfg.remote_port}"
        )

        cmd = [
            "ssh",
            "-N",
            "-L",
            spec,
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            self.ollama_cfg.ssh_target,
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ssh not found on PATH.") from exc

        self._write_state(
            {
                "pid": process.pid,
                "ssh_target": self.ollama_cfg.ssh_target,
                "local_host": self.ollama_cfg.local_host,
                "local_port": self.ollama_cfg.local_port,
                "remote_host": self.ollama_cfg.remote_host,
                "remote_port": self.ollama_cfg.remote_port,
            }
        )

        # Catch immediate failures early.
        time.sleep(0.3)
        exit_code = process.poll()
        if exit_code is not None:
            stderr = (process.stderr.read() or "").strip()
            self._remove_state()
            if not stderr:
                stderr = f"ssh exited with code {exit_code}"
            raise RuntimeError(f"Failed to start Ollama SSH tunnel: {stderr}")

    def _wait_until_healthy(self) -> None:
        deadline = time.time() + self.ollama_cfg.startup_timeout_sec

        while time.time() < deadline:
            if self._is_local_healthy():
                return
            time.sleep(0.5)

        self._stop_tunnel_from_state()
        raise RuntimeError(
            "Timed out waiting for the local Ollama tunnel to become healthy."
        )

    def _stop_tunnel_from_state(self) -> None:
        state = self._read_state()
        if not state:
            return

        pid = state.get("pid")
        if isinstance(pid, int) and self._pid_alive(pid):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        self._remove_state()