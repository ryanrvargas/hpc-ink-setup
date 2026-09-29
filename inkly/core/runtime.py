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

    # Keep safety-critical source-scoping rules early in the contract so they survive
    # prompt-length truncation when optional context or a long query consumes the budget.
    BASE_RESPONSE_CONTRACT = textwrap.dedent("""
    You are Inkly, an assistant for users working on HPC and Slurm systems.

    Follow the user's current request exactly.

    If the user asks for an exact response, return only the exact requested text and nothing else.

    Documentation from a named external institution or cluster is not evidence about the current cluster.
    Never rewrite external commands, modules, paths, licenses, hardware, queues, or policies as local facts.
    If local context does not confirm the answer, say the cluster-specific information is unavailable.
    Present external material only as an explicitly attributed example that requires local verification.

    Context marked scope=verified-local-cluster is trusted local cluster evidence.
    Use that evidence for cluster-specific facts while preserving its evidence labels.
    When trusted local evidence includes a verified job-generation rule, follow that rule
    rather than substituting commands or resource policies from external documentation.
    VERIFIED_CONFIG confirms configuration but does not prove successful runtime behavior.
    UNKNOWN facts must remain unknown and must not be filled from external-cluster examples.
    If local evidence says software is BLOCKED_BY_ACCESS, explain the access prerequisite
    and do not present commands or job scripts as currently runnable for that user.

    Do not reinterpret a general, literal, testing, or unrelated request as an HPC task
    just because Inkly is normally used on an HPC cluster.

    Use the provided plugin context and conversation history only when relevant.

    When cluster-specific context is provided, use it for cluster-specific facts.
    Do not invent cluster state, commands, files, software, or paths.

    If the requested cluster information is unavailable, say so clearly.

    Keep answers concise unless the user requests more detail.
    """).strip()

    CLUSTER_SCOPE_WITHHELD_MARKER = (
        "Cluster-specific Gaussian instructions are unavailable in the current "
        "documentation database."
    )
    CLUSTER_SCOPE_WITHHELD_RESPONSE = (
        "Cluster-specific Gaussian instructions are unavailable in the current "
        "documentation database. I found external Gaussian documentation, but its "
        "commands and policies are not verified for this cluster, so I won't guess "
        "a local module, partition, path, or scheduler command."
    )
    TRUSTED_LOCAL_SCOPE_MARKER = "scope=verified-local-cluster"
    GAUSSIAN_BLOCKED_ACCESS_MARKER = "evidence=BLOCKED_BY_ACCESS"
    GAUSSIAN_ACCESS_ACTION_MARKERS = (
        "run gaussian",
        "running gaussian",
        "load gaussian",
        "loading gaussian",
        "gaussian module",
        "sbatch",
        "submit gaussian",
        "execute gaussian",
        "launch gaussian",
        "permission denied",
    )
    GAUSSIAN_CLUSTER_MARKERS = (
        "this cluster",
        "current cluster",
        "our cluster",
        "cuttlefish",
    )

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

    def _requires_gaussian_source_scoping(self, query: str) -> bool:
        """Return whether a Gaussian query asks for facts about the local cluster."""
        normalized = query.casefold()
        return "gaussian" in normalized and any(
            marker in normalized for marker in self.GAUSSIAN_CLUSTER_MARKERS
        )

    def _requires_gaussian_access_guard(self, query: str) -> bool:
        """Return whether the query asks for Gaussian execution/access guidance."""
        normalized = " ".join(query.casefold().split())

        if "gaussian" not in normalized:
            return False

        return any(
            marker in normalized for marker in self.GAUSSIAN_ACCESS_ACTION_MARKERS
        )

    @staticmethod
    def _extract_local_fact(local_output: str, label: str) -> str | None:
        """Extract one labeled fact from trusted cluster-profile output."""
        marker = f"{label}: "

        for line in local_output.splitlines():
            if marker in line:
                return line.split(marker, 1)[1].strip()

        return None

    def _blocked_gaussian_access_response(self, local_output: str) -> str:
        """Build a deterministic response when Gaussian access is blocked."""
        access_group = self._extract_local_fact(
            local_output,
            "Gaussian access group",
        )
        default_module = self._extract_local_fact(
            local_output,
            "Advertised default Gaussian module",
        )

        lines = [
            (
                "Gaussian is configured on this cluster, but trusted local evidence "
                "shows that it is currently blocked for your account."
            )
        ]

        if access_group:
            lines.append(
                f"Your account does not satisfy the required `{access_group}` "
                "access-group prerequisite."
            )

        if default_module:
            lines.append(
                f"The advertised default module is `{default_module}`, but that is "
                "configuration evidence, not proof that the module is runnable for "
                "your account."
            )

        lines.append(
            "I won't provide a load, run, submit, or runnable SBATCH command until "
            "access is available and Gaussian runtime behavior has been verified."
        )
        lines.append(
            "The trusted local profile does not yet contain a verified procedure "
            "for obtaining Gaussian access."
        )

        return " ".join(lines)

    def _source_scoped_response(
        self,
        plugin_outputs: dict[str, str],
        query: str = "",
    ) -> str | None:
        """Return a deterministic answer when local Gaussian commands are unsafe."""
        gaussian_output = plugin_outputs.get("docs_gaussian", "")
        local_output = plugin_outputs.get("cluster_profile", "")

        if (
            self.GAUSSIAN_BLOCKED_ACCESS_MARKER in local_output
            and self._requires_gaussian_access_guard(query)
        ):
            return self._blocked_gaussian_access_response(local_output)

        if self.CLUSTER_SCOPE_WITHHELD_MARKER not in gaussian_output:
            return None

        if self.TRUSTED_LOCAL_SCOPE_MARKER in local_output:
            return None

        return self.CLUSTER_SCOPE_WITHHELD_RESPONSE

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
        contract_section = self._build_contract_section()
        query_section = self._build_query_section(query)
        max_length = self.config.core.max_prompt_length

        # The response contract and current query are higher priority than optional
        # history/plugin context. Never discard the contract merely because optional
        # context made the assembled prompt too large.
        required_prompt = (
            "\n\n".join([contract_section, query_section]).rstrip("\n") + "\n"
        )
        if len(required_prompt) > max_length:
            query_suffix = f"\n\n{query_section.strip()}\n"
            contract_budget = max_length - len(query_suffix)
            if contract_budget > 0:
                return contract_section[:contract_budget].rstrip("\n") + query_suffix
            return (query_section.strip() + "\n")[-max_length:]

        optional_sections = [
            self._build_history_section(history_lines),
            self._build_plugin_section(plugin_outputs),
        ]
        optional_content = "\n\n".join(
            section for section in optional_sections if section.strip()
        )
        if not optional_content:
            return required_prompt

        optional_budget = max_length - len(required_prompt) - 2
        if optional_budget <= 0:
            return required_prompt

        optional_content = optional_content[:optional_budget].rstrip()
        if not optional_content:
            return required_prompt

        return (
            "\n\n".join([contract_section, optional_content, query_section]).rstrip(
                "\n"
            )
            + "\n"
        )

    def handle_query(self, user_id: str, query: str) -> str:
        """
        Handle a user query end-to-end:
        - Appends the user turn to the conversation
        - Discovers and selects plugins (optionally using retrieval)
        - Forces Gaussian documentation selection for local-cluster Gaussian queries
        - Runs selected plugins with the current query and collects their outputs
        - Enforces deterministic source scoping when local Gaussian facts are unavailable
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

            # Local-cluster Gaussian questions must include both external Gaussian
            # documentation and trusted local cluster evidence even if approximate
            # plugin retrieval misses either plugin.
            if self._requires_gaussian_source_scoping(query):
                for plugin_name in ("docs_gaussian", "cluster_profile"):
                    plugin = discovered.get(plugin_name)
                    if plugin is not None and plugin not in selected_plugins:
                        selected_plugins.append(plugin)

            # Run each selected plugin with the active query and collect its output.
            # Query-aware documentation plugins can use it for retrieval, while
            # cluster-state plugins may ignore it and preserve their existing behavior.
            for fallback_name, plugin in discovered.items():
                if plugin not in selected_plugins:
                    continue

                plugin_name = getattr(plugin, "name", fallback_name)

                try:
                    plugin_outputs[plugin_name] = plugin.run(query)
                except Exception as exc:
                    plugin_outputs[plugin_name] = f"Plugin error: {exc}"

            # When the Gaussian documentation plugin explicitly says that local
            # instructions are unavailable, do not ask a generative model to fill in
            # the missing cluster facts. Return the bounded deterministic answer.
            source_scoped_response = self._source_scoped_response(
                plugin_outputs,
                query=query,
            )
            if source_scoped_response is not None:
                self.conversation.append_turn(
                    user_id, "assistant", source_scoped_response
                )
                return source_scoped_response

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
