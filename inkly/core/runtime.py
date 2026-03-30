from __future__ import annotations

from pathlib import Path
from threading import BoundedSemaphore

from inkly.core.conversation import ConversationManager
from inkly.llm.backend import LLMBackend
from inkly.plugins.manager import PluginManager
from inkly.retrieval.retriever import PluginRetriever


class InklyRuntime:
    """
    This is the main runtime layer that ties everything together.

    My goal here is to keep this lightweight and modular:
    - Conversation tracking
    - Plugin execution
    - Retrieval (optional)
    - LLM backend

    This class is basically the orchestration layer for a single query.
    """

    def __init__(self, config):
        # Store config so everything downstream can use it
        self.config = config

        # Handles storing + building conversation context
        self.conversation = ConversationManager(config)

        # Responsible for discovering available plugins
        self.plugins = PluginManager()

        # Handles sending prompts to the LLM backend
        self.backend = LLMBackend(config)

        # Optional retriever (can be injected or built dynamically)
        self.retriever = None

        # Limits how many queries can run at once
        # This prevents overload / uncontrolled parallel execution
        self._request_gate = BoundedSemaphore(
            value=self.config.core.max_concurrent_requests
        )

    def handle_query(self, user_id: str, query: str) -> str:
        # Only allow a limited number of concurrent requests
        with self._request_gate:

            # Always log the user's query first
            self.conversation.append_turn(user_id, "user", query)

            # Discover all available plugins at runtime
            discovered = self.plugins.discover()

            plugin_outputs = {}
            selected_plugins = []

            # Pull retrieval config if it exists
            retrieval_cfg = getattr(self.config, "retrieval", None)
            retrieval_enabled = bool(retrieval_cfg and retrieval_cfg.enabled)

            # If retrieval is enabled, try to select only relevant plugins
            if retrieval_enabled:
                try:
                    # If a retriever is already injected, use it
                    if self.retriever is not None:
                        if hasattr(self.retriever, "select_plugins"):
                            selected_plugins = list(
                                self.retriever.select_plugins(query, discovered)
                            )
                        else:
                            # Retriever exists but doesn't support selection → fallback to nothing
                            selected_plugins = []
                    else:
                        # Otherwise, build a retriever on the fly
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
                    # If retrieval fails, fall back depending on config
                    if retrieval_cfg.fallback_to_all_plugins:
                        selected_plugins = list(discovered.values())
                    else:
                        selected_plugins = []

            else:
                # Retrieval disabled → just run everything
                selected_plugins = list(discovered.values())

            # If nothing was selected but fallback is allowed, run all plugins
            if not selected_plugins and (
                not retrieval_enabled or retrieval_cfg.fallback_to_all_plugins
            ):
                selected_plugins = list(discovered.values())

            # Execute selected plugins and collect their outputs
            for fallback_name, plugin in discovered.items():
                # Skip plugins that were not selected
                if plugin not in selected_plugins:
                    continue

                # Use plugin.name if available, otherwise fallback to dict key
                plugin_name = getattr(plugin, "name", fallback_name)

                try:
                    # Run the plugin and store its output
                    plugin_outputs[plugin_name] = plugin.run()
                except Exception as exc:
                    # Never crash the pipeline because of a plugin
                    plugin_outputs[plugin_name] = f"Plugin error: {exc}"

            # Build conversation context (this may include summarization)
            history_lines = self.conversation.build_context(
                user_id,
                current_query=query,
                # Only give half the prompt budget to history
                # The rest is for plugins + query
                max_prompt_length=self.config.core.max_prompt_length // 2,
            )

            # Build the final prompt that goes to the LLM
            prompt = self._build_prompt(history_lines, plugin_outputs, query)

            # Hard truncate prompt if it exceeds max length
            # This is a last-resort safety check
            if len(prompt) > self.config.core.max_prompt_length:
                prompt = prompt[-self.config.core.max_prompt_length :]

            try:
                # Send prompt to LLM backend
                response = self.backend.generate(prompt)
            except Exception as exc:
                # If backend fails, log it in conversation history
                failure_text = f"Backend error: {exc}"
                self.conversation.append_turn(user_id, "assistant", failure_text)
                raise

            # Store successful response in history
            self.conversation.append_turn(user_id, "assistant", response)

            return response

    def _build_prompt(self, history_lines, plugin_outputs, query: str) -> str:
        # Build the prompt step by step as a list of lines
        lines = []

        # Include conversation history if available
        if history_lines:
            lines.append("=== CONVERSATION HISTORY ===")
            lines.extend(history_lines)

        # Include plugin outputs if any were executed
        if plugin_outputs:
            lines.append("=== PLUGIN CONTEXT ===")
            for name, output in plugin_outputs.items():
                lines.append(f"[{name}]")
                lines.append(output)

        # Always include the user's query at the end
        lines.append("=== USER QUERY ===")
        lines.append(query)

        # Join everything into a single string
        return "\n".join(lines)