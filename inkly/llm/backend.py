from __future__ import annotations

import subprocess
import os
import sys
import threading
import time
import re


from inkly.llm.ollama_tunnel import OllamaTunnelManager


def _clean_terminal_output(text: str) -> str:
    """
    Remove terminal control noise from captured CLI output.

    This handles:
    - ANSI escape sequences such as cursor show/hide
    - carriage-return style progress output
    - one-character spinner frames emitted on separate lines
    """
    if not text:
        return ""

    # Convert carriage-return updates into normal line separators.
    text = text.replace("\r", "\n")

    # Remove ANSI escape codes like \x1b[?25l and \x1b[?25h.
    text = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", text)

    spinner_frames = {"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}

    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if stripped in spinner_frames:
            continue

        cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines).strip()


class LLMBackend:
    """
    Ollama-backed generation layer for Inkly.

    Responsibilities:
    - enforce the configured prompt-length limit
    - route requests through the configured Ollama transport mode
    - return the final model response text

    Supported Ollama transport modes:
    - cli_run
    - direct_host
    - ssh_tunnel
    - admin_command
    """

    def __init__(self, config):
        # Shared config object used to determine Ollama settings, model, and prompt limits.
        self.config = config
        # Tunnel management is optional and should not be initialized eagerly.
        # Several tests construct minimal config objects that do not include
        # ollama/state sections because they are not exercising tunnel logic.
        self.ollama_tunnel = None
        self._stdout_lock = threading.Lock()

    def selected_model(self) -> str:
        """
        Return the configured Ollama model name.
        """
        return self.config.llm.model

    def max_prompt_length(self) -> int:
        """
        Return the configured hard limit for prompt size.
        """
        return self.config.core.max_prompt_length

    def _get_ollama_tunnel(self) -> OllamaTunnelManager:
        """
        Lazily construct the tunnel manager only when the Ollama path actually
        needs it.
        """
        if self.ollama_tunnel is None:
            self.ollama_tunnel = OllamaTunnelManager(self.config)
        return self.ollama_tunnel

    def _spinner_worker(
        self,
        stop_event: threading.Event,
        started_output_event: threading.Event,
    ) -> None:
        """
        Show a spinner until model output starts or generation ends.
        """
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        label = "Inkly is thinking"

        while not stop_event.is_set() and not started_output_event.is_set():
            with self._stdout_lock:
                frame = frames[idx % len(frames)]
                sys.stdout.write(f"\r{label} {frame}")
                sys.stdout.flush()
            idx += 1
            time.sleep(0.1)

        with self._stdout_lock:
            sys.stdout.write("\r" + " " * (len(label) + 4) + "\r")
            sys.stdout.flush()

    def _stream_command(
        self,
        cmd: list[str],
        prompt: str,
        *,
        env: dict[str, str] | None = None,
        not_found_error: str,
        failed_prefix: str,
        empty_output_error: str,
    ) -> str:
        """
        Stream stdout from a command in real time while also collecting the full
        response for runtime/history use.
        """
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(not_found_error) from exc

        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise RuntimeError("Failed to open subprocess pipes for Ollama command.")

        process.stdin.write(prompt)
        process.stdin.close()

        chunks: list[str] = []

        stop_spinner = threading.Event()
        started_output = threading.Event()
        spinner_thread = threading.Thread(
            target=self._spinner_worker,
            args=(stop_spinner, started_output),
            daemon=True,
        )
        spinner_thread.start()

        spinner_joined = False

        try:
            while True:
                ch = process.stdout.read(1)
                if ch == "":
                    break

                if not started_output.is_set():
                    started_output.set()
                    spinner_thread.join(timeout=1.0)
                    spinner_joined = True

                chunks.append(ch)
                with self._stdout_lock:
                    sys.stdout.write(ch)
                    sys.stdout.flush()
        finally:
            stop_spinner.set()
            if not spinner_joined:
                spinner_thread.join(timeout=1.0)

        stderr_text = process.stderr.read()
        return_code = process.wait()

        if return_code != 0:
            stderr_text = (stderr_text or "").strip()
            if not stderr_text:
                stderr_text = "unknown Ollama error"
            raise RuntimeError(f"{failed_prefix}: {stderr_text}")

        output = "".join(chunks).strip()
        if not output:
            raise RuntimeError(empty_output_error)

        return output

    def _run_command_capture(
        self,
        cmd: list[str],
        prompt: str,
        *,
        env: dict[str, str] | None = None,
        not_found_error: str,
        failed_prefix: str,
        empty_output_error: str,
        clean_output: bool = False,
    ) -> str:
        """
        Run a command and capture its full response without streaming.
        """
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(not_found_error) from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if not stderr:
                stderr = "unknown Ollama error"
            raise RuntimeError(f"{failed_prefix}: {stderr}")

        output = result.stdout or ""

        if clean_output:
            output = _clean_terminal_output(output)
        else:
            output = output.strip()

        if not output:
            raise RuntimeError(empty_output_error)

        return output

    def generate(self, prompt: str) -> str:
        """
        Generate a response with Ollama.

        Flow:
        - trim the prompt to the configured maximum length
        - route the request through the configured Ollama mode

        Returns:
            The final text response from Ollama.
        """
        prompt = prompt[: self.max_prompt_length()]
        return self._generate_ollama(prompt)

    def _generate_ollama(self, prompt: str) -> str:
        """
        Route Ollama generation based on the configured transport mode.
        """
        if not hasattr(self.config, "ollama"):
            return self._generate_ollama_cli_run(prompt)

        ollama_cfg = self.config.ollama
        mode = getattr(ollama_cfg, "mode", "cli_run")

        if mode == "admin_command":
            return self._generate_ollama_admin_command(prompt)

        if mode == "direct_host":
            return self._generate_ollama_cli_run(prompt, use_direct_host=True)

        if mode == "ssh_tunnel":
            return self._generate_ollama_cli_run(prompt, use_tunnel=True)

        return self._generate_ollama_cli_run(prompt)

    def _generate_ollama_admin_command(self, prompt: str) -> str:
        """
        Send the prompt to an admin-managed Ollama wrapper command.

        Preferred transport is stdin so long prompts do not hit argv limits.
        """
        ollama_cfg = self.config.ollama
        cmd = [ollama_cfg.command_path, *ollama_cfg.command_args]

        if sys.stdout.isatty():
            return self._stream_command(
                cmd,
                prompt,
                env=None,
                not_found_error=f"Admin Ollama command not found: {ollama_cfg.command_path}",
                failed_prefix="Ollama admin command failed",
                empty_output_error="Ollama admin command returned an empty response.",
            )

        return self._run_command_capture(
            cmd,
            prompt,
            env=None,
            not_found_error=f"Admin Ollama command not found: {ollama_cfg.command_path}",
            failed_prefix="Ollama admin command failed",
            empty_output_error="Ollama admin command returned an empty response.",
            clean_output=True,
        )

    def _generate_ollama_cli_run(
        self,
        prompt: str,
        *,
        use_direct_host: bool = False,
        use_tunnel: bool = False,
    ) -> str:
        """
        Use normal `ollama run <model>` behavior, optionally with direct host or tunnel.
        """
        model = self.selected_model()
        cmd = ["ollama", "run", model]
        env = os.environ.copy()

        if use_direct_host:
            ollama_cfg = self.config.ollama
            env["OLLAMA_HOST"] = (
                f"http://{ollama_cfg.direct_host}:{ollama_cfg.direct_port}"
            )
        elif use_tunnel:
            self._get_ollama_tunnel().ensure_ready()

        if sys.stdout.isatty():
            return self._stream_command(
                cmd,
                prompt,
                env=env,
                not_found_error="Ollama CLI not found on PATH.",
                failed_prefix="Ollama generation failed",
                empty_output_error="Ollama returned an empty response.",
            )

        return self._run_command_capture(
            cmd,
            prompt,
            env=env,
            not_found_error="Ollama CLI not found on PATH.",
            failed_prefix="Ollama generation failed",
            empty_output_error="Ollama returned an empty response.",
            clean_output=True,
        )
