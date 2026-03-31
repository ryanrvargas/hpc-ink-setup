from __future__ import annotations


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
        # Apply a final hard limit before sending the prompt to any backend.
        prompt = prompt[: self.max_prompt_length()]

        backend = self.selected_backend()

        # Route to the Ollama backend handler.
        if backend == "ollama":
            return self._generate_ollama(prompt)

        # Route to the GitHub backend handler.
        if backend == "github":
            return self._generate_github(prompt)

        # Fail fast if the configured backend is unknown.
        raise ValueError(f"Unsupported backend: {backend}")

    def _generate_ollama(self, prompt: str) -> str:
        """
        Placeholder Ollama backend implementation.

        This currently returns a simulated response and does not yet
        perform a real Ollama request.
        """
        # Model selection is included in the placeholder so the configured
        # model still shows up in the response path.
        model = self.selected_model()
        return f"[ollama placeholder: model={model}] Simulated response."

    def _generate_github(self, prompt: str) -> str:
        """
        Placeholder GitHub backend implementation.

        This currently returns a simulated response and does not yet
        perform a real GitHub Copilot CLI or API request.
        """
        return "[github placeholder] Simulated response."