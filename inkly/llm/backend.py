from __future__ import annotations


class LLMBackend:
    """
    Thin backend selector for Milestone 2.5 skeleton work.

    Real Ollama invocation belongs to Issue 6.
    CLI backend routing belongs to Issue 8.
    """

    def __init__(self, config):
        self.config = config

    def selected_backend(self) -> str:
        # Temporary bridge until config.py grows typed llm/core sections.
        raw = getattr(self.config, "raw_config", {}) or {}
        llm_cfg = raw.get("llm", {})
        return llm_cfg.get("backend", "github")

    def selected_model(self) -> str:
        raw = getattr(self.config, "raw_config", {}) or {}
        llm_cfg = raw.get("llm", {})
        return llm_cfg.get("model", "llama3")

    def max_prompt_length(self) -> int:
        raw = getattr(self.config, "raw_config", {}) or {}
        core_cfg = raw.get("core", {})
        return int(core_cfg.get("max_prompt_length", 8000))

    def generate(self, prompt: str) -> str:
        prompt = prompt[: self.max_prompt_length()]
        backend = self.selected_backend()

        if backend == "ollama":
            return self._generate_ollama(prompt)

        if backend == "github":
            return self._generate_github(prompt)

        raise ValueError(f"Unsupported backend: {backend}")

    def _generate_ollama(self, prompt: str) -> str:
        model = self.selected_model()
        return f"[ollama placeholder: model={model}]\n{prompt[:500]}"

    def _generate_github(self, prompt: str) -> str:
        return f"[github placeholder]\n{prompt[:500]}"