from __future__ import annotations

from pathlib import Path
from threading import BoundedSemaphore
import textwrap

from inkly.core.conversation import ConversationManager
from inkly.llm.backend import LLMBackend
from inkly.plugins.manager import PluginManager
from inkly.retrieval.retriever import PluginRetriever


class InklyRuntime:
    """
    The main runtime environment for the Inkly HPC assistant.

    Responsible for managing conversation state, plugin execution, LLM backend interaction,
    and prompt assembly for each user query. Handles plugin retrieval, prompt construction,
    and concurrency control for incoming requests.
    """

    def __init__(self, config):
        """
        Initialize the InklyRuntime with the provided configuration.
        Sets up conversation management, plugin manager, LLM backend, and concurrency gate.
        """
        self.config = config
        self.conversation = ConversationManager(
            config
        )  # Tracks conversation history per user
        self.plugins = PluginManager()  # Manages available plugins
        self.backend = LLMBackend(config)  # Handles LLM prompt/response
        self.retriever = None  # Optional plugin retriever (lazy init)
        self._request_gate = BoundedSemaphore(
            value=self.config.core.max_concurrent_requests
        )  # Limits concurrent requests for thread safety

    # The contract that governs all LLM responses for Inkly
    BASE_RESPONSE_CONTRACT = textwrap.dedent("""
    You are Inkly, an HPC assistant for a Slurm-based cluster.

    Rules:
    - Plain text only.
    - Use the provided plugin context and conversation history when relevant.
    - Do not invent cluster state, commands, files, or paths.
    - If something is uncertain, say so clearly.
    - If the request is ambiguous or missing critical details, ask one concise clarifying question.
    - Keep answers concise unless the user asks for more detail.

    When the user asks for code or a configuration change:
    1. Provide one complete code block when appropriate.
    2. Follow it with short numbered instructions.
    3. Keep the explanation concise and practical.

    When the user is not asking for code:
    - Answer directly and do not force a code block.
    """).strip()

    def _build_contract_section(self) -> str:
        """
        Build the base instruction section that defines the assistant's behavior.
        This section is always present in the final prompt.
        """
        return "\n".join(
            [
                "=== INKLY RESPONSE CONTRACT ===",
                self.BASE_RESPONSE_CONTRACT,
            ]
        )

    def _build_history_section(self, history_lines: list[str]) -> str:
        """
        Build the conversation-history section for the prompt.

        Returns an empty string if there is no history, so the prompt assembly can skip it.
        """
        if not history_lines:
            return ""

        return "\n".join(
            [
                "=== CONVERSATION HISTORY ===",
                *history_lines,
            ]
        )

    def _build_plugin_section(self, plugin_outputs: dict[str, str]) -> str:
        """
        Build the plugin-context section for the prompt.

        Each plugin gets a labeled subsection so the LLM can see where each
        piece of context came from.
        Returns an empty string if there are no plugin outputs.
        """
        if not plugin_outputs:
            return ""

        lines = ["=== PLUGIN CONTEXT ==="]

        for plugin_name, output in plugin_outputs.items():
            lines.append(f"[{plugin_name}]")
            lines.append(output.strip() if output else "")
            lines.append("")

        return "\n".join(lines).rstrip()

    def _build_query_section(self, query: str) -> str:
        """
        Build the final user-query section for the prompt.

        This section is always included because it represents the active task.
        """
        return "\n".join(
            [
                "=== USER QUERY ===",
                query.strip(),
            ]
        )

    def assemble_prompt(
        self,
        *,
        query: str,
        history_lines: list[str],
        plugin_outputs: dict[str, str],
    ) -> str:
        """
        Assemble the full prompt from independently formatted sections.

        Empty optional sections are omitted automatically. The section order is:
        1. response contract
        2. conversation history
        3. plugin context
        4. current user query
        Truncates the prompt if it exceeds the configured max length.
        """
        sections = [
            self._build_contract_section(),
            self._build_history_section(history_lines),
            self._build_plugin_section(plugin_outputs),
            self._build_query_section(query),
        ]

        # Only include non-empty sections
        non_empty_sections = [section for section in sections if section.strip()]
        prompt = "\n\n".join(non_empty_sections)

        # Truncate prompt if it exceeds max length
        if len(prompt) > self.config.core.max_prompt_length:
            prompt = prompt[-self.config.core.max_prompt_length :]

        return prompt

    def handle_query(self, user_id: str, query: str) -> str:
        """
        Handle a user query end-to-end:
        - Appends the user turn to the conversation
        - Discovers and selects plugins (optionally using retrieval)
        - Runs selected plugins and collects their outputs
        - Builds conversation history context
        - Assembles the full prompt for the LLM
        - Calls the LLM backend to generate a response
        - Appends the assistant's response to the conversation
        - Returns the assistant's response as a string
        """
        with self._request_gate:
            # Add the user query to the conversation history
            self.conversation.append_turn(user_id, "user", query)
            discovered = self.plugins.discover()  # Find all available plugins

            plugin_outputs = {}
            selected_plugins = []

            # Check if retrieval-based plugin selection is enabled
            retrieval_cfg = getattr(self.config, "retrieval", None)
            retrieval_enabled = bool(retrieval_cfg and retrieval_cfg.enabled)

            if retrieval_enabled:
                try:
                    if self.retriever is not None:
                        # Use the existing retriever if available
                        if hasattr(self.retriever, "select_plugins"):
                            selected_plugins = list(
                                self.retriever.select_plugins(query, discovered)
                            )
                        else:
                            selected_plugins = []
                    else:
                        # Create a new retriever instance for plugin selection
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
                    # On error, optionally fall back to all plugins
                    if retrieval_cfg.fallback_to_all_plugins:
                        selected_plugins = list(discovered.values())
                    else:
                        selected_plugins = []
            else:
                # Retrieval not enabled: use all discovered plugins
                selected_plugins = list(discovered.values())

            # If no plugins selected, optionally fall back to all
            if not selected_plugins and (
                not retrieval_enabled or retrieval_cfg.fallback_to_all_plugins
            ):
                selected_plugins = list(discovered.values())

            # Run each selected plugin and collect its output
            for fallback_name, plugin in discovered.items():
                if plugin not in selected_plugins:
                    continue

                plugin_name = getattr(plugin, "name", fallback_name)

                try:
                    plugin_outputs[plugin_name] = plugin.run()
                except Exception as exc:
                    plugin_outputs[plugin_name] = f"Plugin error: {exc}"

            # Build conversation history context for the prompt
            history_lines = self.conversation.build_context(
                user_id,
                current_query=query,
                max_prompt_length=self.config.core.max_prompt_length // 2,
            )

            # Assemble the full prompt for the LLM
            prompt = self.assemble_prompt(
                query=query,
                history_lines=history_lines,
                plugin_outputs=plugin_outputs,
            )

            # Generate a response from the LLM backend
            try:
                response = self.backend.generate(prompt)
            except Exception as exc:
                # On backend error, log the error in the conversation
                self.conversation.append_turn(
                    user_id,
                    "assistant",
                    f"Backend error: {exc}",
                )
                raise

            # Add the assistant's response to the conversation
            self.conversation.append_turn(user_id, "assistant", response)
            return response
