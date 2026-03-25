from __future__ import annotations

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

    def handle_query(self, user_id: str, query: str) -> str:
        history = self.conversation.load(user_id)

        discovered = self.plugins.discover()

        # Issue 1 skeleton:
        # run all discovered plugins for now.
        # Retrieval/ranking belongs in later work.
        plugin_outputs = {}
        for name, plugin in discovered.items():
            try:
                plugin_outputs[name] = plugin.run()
            except Exception as exc:
                plugin_outputs[name] = f"Plugin error: {exc}"

        prompt = self._build_prompt(history, plugin_outputs, query)
        response = self.backend.generate(prompt)

        self.conversation.append_exchange(user_id, query, response)
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