from __future__ import annotations

import subprocess
import os
from inkly.llm.ollama_tunnel import OllamaTunnelManager


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
        Call Ollama through the CLI and return the generated text.

        Transport priority:
        1. Direct remote host, if configured
        2. SSH tunnel, if configured
        3. Plain localhost CLI behavior
        """
        model = self.selected_model()
        cmd = ["ollama", "run", model]
        env = os.environ.copy()

        if self._has_ollama_service_config():
            ollama_cfg = self.config.ollama

            if getattr(ollama_cfg, "use_direct_host", False):
                env["OLLAMA_HOST"] = f"http://{ollama_cfg.direct_host}:{ollama_cfg.direct_port}"
            else:
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