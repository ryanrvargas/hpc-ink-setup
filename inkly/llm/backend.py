from __future__ import annotations

import subprocess
import os
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
    Thin abstraction layer for routing prompts to the configured LLM backend.

    This is intentionally minimal in the current milestone.
    Real backend integrations such as Ollama calls or GitHub CLI routing
    are expected to be implemented later.

    Current responsibilities:
    - read backend configuration
    - enforce prompt-length limits
    - route requests to the correct backend handler
    """

    def __init__(self, config):
        # Shared config object used to determine backend, model, and prompt limits.
        self.config = config
        # Tunnel management is optional and should not be initialized eagerly.
        # Several tests construct minimal config objects that do not include
        # ollama/state sections because they are not exercising tunnel logic.
        self.ollama_tunnel = None

    def selected_backend(self) -> str:
        """
        Return the configured backend name.

        Example values:
        - "github"
        - "ollama"
        """
        return self.config.llm.backend

    def selected_model(self) -> str:
        """
        Return the configured model name for the selected backend.
        """
        return self.config.llm.model

    def max_prompt_length(self) -> int:
        """
        Return the configured hard limit for prompt size.
        """
        return self.config.core.max_prompt_length

    def _has_ollama_service_config(self) -> bool:
        """
        Return True only when the config includes the sections required by the
        optional tunnel/service layer.

        This keeps older tests and minimal config objects compatible.
        """
        return hasattr(self.config, "ollama") and hasattr(self.config, "state")

    def _get_ollama_tunnel(self) -> OllamaTunnelManager:
        """
        Lazily construct the tunnel manager only when the Ollama path actually
        needs it.
        """
        if self.ollama_tunnel is None:
            self.ollama_tunnel = OllamaTunnelManager(self.config)
        return self.ollama_tunnel

    def generate(self, prompt: str) -> str:
        """
        Generate a response using the configured backend.

        Flow:
        - trim the prompt to the configured maximum length
        - check which backend is selected
        - route the request to the matching backend method

        Raises:
            ValueError: If the configured backend is not supported.
        """
        prompt = prompt[: self.max_prompt_length()]
        backend = self.selected_backend()

        if backend == "ollama":
            return self._generate_ollama(prompt)

        if backend == "github":
            return self._generate_github(prompt)

        raise ValueError(f"Unsupported backend: {backend}")

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

        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Admin Ollama command not found: {ollama_cfg.command_path}"
            ) from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if not stderr:
                stderr = "unknown Ollama error"
            raise RuntimeError(f"Ollama admin command failed: {stderr}")

        output = _clean_terminal_output(result.stdout or "")
        if not output:
            raise RuntimeError("Ollama admin command returned an empty response.")

        return output


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
            raise RuntimeError("Ollama CLI not found on PATH.") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if not stderr:
                stderr = "unknown Ollama error"
            raise RuntimeError(f"Ollama generation failed: {stderr}")

        output = (result.stdout or "").strip()
        if not output:
            raise RuntimeError("Ollama returned an empty response.")

        return output

    
    def _generate_github(self, prompt: str) -> str:
        """
        Placeholder GitHub backend implementation.

        This currently returns a simulated response and does not yet
        perform a real GitHub Copilot CLI or API request.
        """
        return "[github placeholder] Simulated response."