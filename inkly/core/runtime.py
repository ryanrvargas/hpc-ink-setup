from __future__ import annotations

from pathlib import Path
from threading import BoundedSemaphore

from inkly.core.conversation import ConversationManager
from inkly.llm.backend import LLMBackend
from inkly.plugins.manager import PluginManager
from inkly.retrieval.retriever import PluginRetriever

class InklyRuntime:
    """
    Lightweight modular runtime for Milestone 2.5 Issue 1.
    """

    def __init__(self, config):
        self.config = config
        self.conversation = ConversationManager(config)
        self.plugins = PluginManager()
        self.backend = LLMBackend(config)
        self.retriever = None
        self._request_gate = BoundedSemaphore(
            value=self.config.core.max_concurrent_requests
        )

    def handle_query(self, user_id: str, query: str) -> str:
        with self._request_gate:
            self.conversation.append_turn(user_id, "user", query)

            discovered = self.plugins.discover()

            plugin_outputs = {}
            selected_plugins = []

            retrieval_cfg = getattr(self.config, "retrieval", None)
            retrieval_enabled = bool(retrieval_cfg and retrieval_cfg.enabled)

            if retrieval_enabled:
                try:
                    if self.retriever is not None:
                        if hasattr(self.retriever, "select_plugins"):
                            selected_plugins = list(
                                self.retriever.select_plugins(query, discovered)
                            )
                        else:
                            selected_plugins = []
                    else:
                        retriever = PluginRetriever(
                            index_path=Path(retrieval_cfg.index_path).expanduser(),
                            top_k=retrieval_cfg.top_k,
                            min_score=retrieval_cfg.min_score,
                            fallback_to_all_plugins=retrieval_cfg.fallback_to_all_plugins,
                        )
                        selected_plugins = list(
                            retriever.select_plugins(query, discovered)
                        )
                except Exception:
                    if retrieval_cfg.fallback_to_all_plugins:
                        selected_plugins = list(discovered.values())
                    else:
                        selected_plugins = []
            else:
                selected_plugins = list(discovered.values())

            if not selected_plugins and (
                not retrieval_enabled or retrieval_cfg.fallback_to_all_plugins
            ):
                selected_plugins = list(discovered.values())

            for fallback_name, plugin in discovered.items():
                if plugin not in selected_plugins:
                    continue

                plugin_name = getattr(plugin, "name", fallback_name)

                try:
                    plugin_outputs[plugin_name] = plugin.run()
                except Exception as exc:
                    plugin_outputs[plugin_name] = f"Plugin error: {exc}"

            history_lines = self.conversation.build_context(
                user_id,
                current_query=query,
                max_prompt_length=self.config.core.max_prompt_length // 2,
            )

            prompt = self._build_prompt(history_lines, plugin_outputs, query)

            if len(prompt) > self.config.core.max_prompt_length:
                prompt = prompt[-self.config.core.max_prompt_length :]

            try:
                response = self.backend.generate(prompt)
            except Exception as exc:
                failure_text = f"Backend error: {exc}"
                self.conversation.append_turn(user_id, "assistant", failure_text)
                raise

            self.conversation.append_turn(user_id, "assistant", response)
            return response

    def _build_prompt(self, history_lines, plugin_outputs, query: str) -> str:
        lines = []

        if history_lines:
            lines.append("=== CONVERSATION HISTORY ===")
            lines.extend(history_lines)

        if plugin_outputs:
            lines.append("=== PLUGIN CONTEXT ===")
            for name, output in plugin_outputs.items():
                lines.append(f"[{name}]")
                lines.append(output)

        lines.append("=== USER QUERY ===")
        lines.append(query)

        return "\n".join(lines)
