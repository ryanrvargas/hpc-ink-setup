from __future__ import annotations


class LLMBackend:
    """
    This class is my abstraction layer for talking to different LLM backends.

    Right now this is intentionally minimal because this is still skeleton work.
    The real implementations (actual API calls, CLI calls, etc.) will come later.

    The goal here is just to:
    - pick the correct backend
    - enforce prompt limits
    - route the request cleanly
    """

    def __init__(self, config):
        # I store config so I can pull backend + model settings from it
        self.config = config

    def selected_backend(self) -> str:
        # Returns which backend I should use (ex: "github", "ollama")
        return self.config.llm.backend

    def selected_model(self) -> str:
        # Returns which model should be used for the selected backend
        return self.config.llm.model

    def max_prompt_length(self) -> int:
        # This is the hard limit for prompt size coming from config
        return self.config.core.max_prompt_length

    def generate(self, prompt: str) -> str:
        # I always enforce prompt length here as a final safeguard
        prompt = prompt[: self.max_prompt_length()]

        backend = self.selected_backend()

        # Route to the correct backend implementation
        if backend == "ollama":
            return self._generate_ollama(prompt)

        if backend == "github":
            return self._generate_github(prompt)

        # If the backend is unknown, I fail fast instead of silently continuing
        raise ValueError(f"Unsupported backend: {backend}")

    def _generate_ollama(self, prompt: str) -> str:
        # Placeholder for future Ollama integration
        # This will eventually call the Ollama runtime or API
        model = self.selected_model()
        return f"[ollama placeholder: model={model}] Simulated response."

    def _generate_github(self, prompt: str) -> str:
        # Placeholder for GitHub Copilot CLI integration
        # This will eventually call the copilot CLI or API
        return "[github placeholder] Simulated response."