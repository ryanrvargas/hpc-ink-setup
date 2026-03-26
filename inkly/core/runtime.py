from __future__ import annotations

from threading import BoundedSemaphore

from inkly.core.conversation import ConversationManager
from inkly.llm.backend import LLMBackend
from inkly.plugins.manager import PluginManager


class InklyRuntime:
    """
    Lightweight modular runtime for Milestone 2.5 Issue 1.
    """

    def __init__(self, config):
        self.config = config
        self.conversation = ConversationManager(config)
        self.plugins = PluginManager()
        self.backend = LLMBackend(config)
        self._request_gate = BoundedSemaphore(
            value=self.config.core.max_concurrent_requests
        )

    def handle_query(self, user_id: str, query: str) -> str:
        with self._request_gate:
            prior_history = self.conversation.load(user_id)
            self.conversation.append_turn(user_id, "user", query)

            discovered = self.plugins.discover()

            plugin_outputs = {}
            for name, plugin in discovered.items():
                try:
                    plugin_outputs[name] = plugin.run()
                except Exception as exc:
                    plugin_outputs[name] = f"Plugin error: {exc}"

            prompt = self._build_prompt(prior_history, plugin_outputs, query)

            try:
                response = self.backend.generate(prompt)
            except Exception as exc:
                failure_text = f"Backend error: {exc}"
                self.conversation.append_turn(user_id, "assistant", failure_text)
                raise

            self.conversation.append_turn(user_id, "assistant", response)
            return response

    def _build_prompt(self, history, plugin_outputs, query: str) -> str:
        lines = []

        if history:
            lines.append("=== CONVERSATION HISTORY ===")
            for turn in history:
                lines.append(f"{turn['role']}: {turn['content']}")

        if plugin_outputs:
            lines.append("=== PLUGIN CONTEXT ===")
            for name, output in plugin_outputs.items():
                lines.append(f"[{name}]")
                lines.append(output)

        lines.append("=== USER QUERY ===")
        lines.append(query)

        return "\n".join(lines)
