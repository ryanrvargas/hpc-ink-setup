from __future__ import annotations

from pathlib import Path
from threading import BoundedSemaphore

from inkly.core.conversation import ConversationManager
from inkly.llm.backend import LLMBackend
from inkly.plugins.manager import PluginManager
from inkly.retrieval.retriever import PluginRetriever


class InklyRuntime:
    """
    Main runtime orchestration layer.

    This class ties together the main runtime pieces:
    - conversation history management
    - plugin discovery and execution
    - retrieval-based plugin selection
    - LLM backend prompt generation

    The focus here is to keep runtime flow modular while still providing
    one clear entry point for handling a user query.
    """

    def __init__(self, config):
        # Shared config object used by all runtime components.
        self.config = config

        # Handles persistent conversation storage and prompt context building.
        self.conversation = ConversationManager(config)

        # Discovers available plugins dynamically from the plugin package.
        self.plugins = PluginManager()

        # Handles backend selection and prompt submission to the LLM layer.
        self.backend = LLMBackend(config)

        # Optional retriever instance.
        # This can be injected in tests or replaced at runtime if needed.
        self.retriever = None

        # Concurrency gate used to limit how many requests can run at once.
        # This helps avoid uncontrolled parallel execution.
        self._request_gate = BoundedSemaphore(
            value=self.config.core.max_concurrent_requests
        )

    def handle_query(self, user_id: str, query: str) -> str:
        """
        Handle one user query from start to finish.

        High-level flow:
        - store the user query in conversation history
        - discover plugins
        - optionally use retrieval to choose relevant plugins
        - execute selected plugins
        - build prompt from history + plugin outputs + current query
        - send prompt to backend
        - store backend response in conversation history

        Returns:
            The backend response string.
        """
        # Only allow a limited number of concurrent requests.
        # The context manager acquires the semaphore at entry and releases it on exit.
        with self._request_gate:

            # Store the user's query immediately so the runtime has a full history trail.
            self.conversation.append_turn(user_id, "user", query)

            # Discover all currently available plugins.
            # This keeps plugin registration dynamic instead of hard-coded.
            discovered = self.plugins.discover()

            # plugin_outputs stores final text returned by each executed plugin.
            # selected_plugins stores the subset chosen for execution.
            plugin_outputs = {}
            selected_plugins = []

            # Retrieval config may or may not exist depending on config shape.
            retrieval_cfg = getattr(self.config, "retrieval", None)
            retrieval_enabled = bool(retrieval_cfg and retrieval_cfg.enabled)

            # If retrieval is enabled, try to narrow plugin execution to only
            # the most relevant plugins for the current query.
            if retrieval_enabled:
                try:
                    # If a retriever was already injected, use it directly.
                    # This is useful for tests or future runtime customization.
                    if self.retriever is not None:
                        if hasattr(self.retriever, "select_plugins"):
                            selected_plugins = list(
                                self.retriever.select_plugins(query, discovered)
                            )
                        else:
                            # If an injected retriever does not support the expected method,
                            # treat it as unusable and continue with an empty selection.
                            selected_plugins = []
                    else:
                        # Otherwise, build a retriever from config on demand.
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
                    # Retrieval failure should not crash the whole query pipeline.
                    # Fallback behavior is controlled by config.
                    if retrieval_cfg.fallback_to_all_plugins:
                        selected_plugins = list(discovered.values())
                    else:
                        selected_plugins = []

            else:
                # If retrieval is disabled, all discovered plugins are eligible to run.
                selected_plugins = list(discovered.values())

            # Final fallback:
            # If nothing was selected and fallback is allowed, run all plugins.
            # This prevents empty context in cases where retrieval produces no hits.
            if not selected_plugins and (
                not retrieval_enabled or retrieval_cfg.fallback_to_all_plugins
            ):
                selected_plugins = list(discovered.values())

            # Execute selected plugins and collect their outputs.
            # Iteration still happens over all discovered plugins so the runtime
            # preserves a stable order from discovery.
            for fallback_name, plugin in discovered.items():
                # Skip any plugin that was not selected.
                if plugin not in selected_plugins:
                    continue

                # Prefer the plugin's declared name if it exists.
                # Fall back to the dictionary key if needed.
                plugin_name = getattr(plugin, "name", fallback_name)

                try:
                    # Run the plugin and store its output under its name.
                    plugin_outputs[plugin_name] = plugin.run()
                except Exception as exc:
                    # Plugin failures are captured as text instead of crashing
                    # the whole runtime pipeline.
                    plugin_outputs[plugin_name] = f"Plugin error: {exc}"

            # Build conversation context for prompt injection.
            # current_query is passed in so the conversation layer can avoid
            # duplicating the just-appended user query in the prompt history.
            history_lines = self.conversation.build_context(
                user_id,
                current_query=query,
                # Only half of the total prompt budget is reserved for history.
                # The remaining budget is left for plugin context and the live query.
                max_prompt_length=self.config.core.max_prompt_length // 2,
            )

            # Build the final prompt that will be sent to the backend.
            prompt = self._build_prompt(history_lines, plugin_outputs, query)

            # Final hard prompt-length guard.
            # This is a coarse safety check in case prompt construction still exceeds budget.
            if len(prompt) > self.config.core.max_prompt_length:
                prompt = prompt[-self.config.core.max_prompt_length :]

            try:
                # Send the final prompt to the configured backend.
                response = self.backend.generate(prompt)
            except Exception as exc:
                # Backend failures are recorded in history before re-raising.
                # This preserves the failure in the conversation log.
                failure_text = f"Backend error: {exc}"
                self.conversation.append_turn(user_id, "assistant", failure_text)
                raise

            # Store successful backend response in conversation history.
            self.conversation.append_turn(user_id, "assistant", response)

            return response

    def _build_prompt(self, history_lines, plugin_outputs, query: str) -> str:
        """
        Build the final backend prompt from its main sections.

        Prompt structure:
        - conversation history (if present)
        - plugin context (if present)
        - current user query

        Returns:
            A single newline-joined prompt string.
        """
        # Build the prompt incrementally as a list of lines.
        # This is easier to manage than concatenating raw strings repeatedly.
        lines = []

        # Include processed conversation history first so the backend
        # sees recent context before plugin details and the current query.
        if history_lines:
            lines.append("=== CONVERSATION HISTORY ===")
            lines.extend(history_lines)

        # Include plugin outputs next.
        # Each plugin gets its own labeled block.
        if plugin_outputs:
            lines.append("=== PLUGIN CONTEXT ===")
            for name, output in plugin_outputs.items():
                lines.append(f"[{name}]")
                lines.append(output)

        # Always include the current query last.
        # This keeps the active user request explicit and easy for the backend to identify.
        lines.append("=== USER QUERY ===")
        lines.append(query)

        # Join all prompt sections into one final string.
        return "\n".join(lines)