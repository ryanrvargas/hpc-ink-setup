from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConversationManager:
    """
    Manages persistent conversation history per user and prepares context
    for prompt injection into the LLM.

    Key design principle:
    ---------------------
    Storage and prompt-context generation are intentionally separated.

    - Full history:
        Stored on disk as an append-only JSON list per user.

    - Prompt context:
        A processed subset of history used when constructing prompts.
        This may include truncation and/or summarization.

    This separation prevents loss of information while still respecting
    LLM context limits.
    """

    def __init__(self, config):
        """
        Initialize the conversation manager.

        Args:
            config:
                Inkly configuration object. Must contain:
                - conversation.enabled
                - conversation.max_messages
                - conversation.summary_trigger
                - conversation.summarize
                - conversation.max_summary_chars
        """
        self.config = config

        # Whether conversation tracking is enabled at all
        self.enabled = self.config.conversation.enabled

        # Directory where all conversation files are stored
        # Structure: ~/.inkly/conversations/<user_id>.json
        self.base_dir = Path.home() / ".inkly" / "conversations"

        # Ensure directory exists (safe even if already created)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _conversation_file(self, user_id: str) -> Path:
        """
        Resolve the file path for a user's conversation history.

        Args:
            user_id: Unique identifier for the user

        Returns:
            Path to JSON file storing the user's history
        """
        return self.base_dir / f"{user_id}.json"

    def _read_full_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Read full conversation history from disk.

        This function is defensive:
        - Returns [] if disabled
        - Returns [] if file missing
        - Returns [] if file is corrupted or invalid

        Also filters out malformed entries to ensure structure consistency.

        Args:
            user_id: User identifier

        Returns:
            List of valid conversation entries
        """
        if not self.enabled:
            return []

        path = self._conversation_file(user_id)

        # No history yet
        if not path.exists():
            return []

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            # Corrupt or unreadable file → fail safely
            return []

        # Ensure the stored structure is a list
        if not isinstance(data, list):
            return []

        # Validate entries (defensive schema enforcement)
        valid: List[Dict[str, Any]] = []
        for item in data:
            if (
                isinstance(item, dict)
                and isinstance(item.get("role"), str)
                and isinstance(item.get("content"), str)
            ):
                valid.append(item)

        return valid

    def _write_full_history(self, user_id: str, history: List[Dict[str, Any]]) -> None:
        """
        Persist full conversation history to disk.

        This overwrites the existing file with the updated history.

        Args:
            user_id: User identifier
            history: Full conversation history
        """
        path = self._conversation_file(user_id)

        with path.open("w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def append_turn(self, user_id: str, role: str, content: str) -> None:
        """
        Append a single conversation turn to history.

        Args:
            user_id: User identifier
            role: "user" or "assistant"
            content: Message content
        """
        if not self.enabled:
            return

        history = self._read_full_history(user_id)

        history.append(
            {
                # Timestamp is stored for future analysis / ordering
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "content": content,
            }
        )

        self._write_full_history(user_id, history)

    def append_exchange(self, user_id: str, question: str, answer: str) -> None:
        """
        Convenience method for appending a full user → assistant exchange.

        Args:
            user_id: User identifier
            question: User input
            answer: Assistant response
        """
        self.append_turn(user_id, "user", question)
        self.append_turn(user_id, "assistant", answer)

    def load_recent(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Load the most recent N messages from history.

        This is a simple truncation strategy without summarization.

        Args:
            user_id: User identifier

        Returns:
            List of most recent conversation entries
        """
        history = self._read_full_history(user_id)

        # Keep only the last N messages
        return history[-self.config.conversation.max_messages :]

    def build_context(
        self,
        user_id: str,
        *,
        current_query: Optional[str] = None,
        max_prompt_length: Optional[int] = None,
    ) -> List[str]:
        """
        Build processed conversation context for prompt injection.

        Behavior:
        ---------
        1. Loads full history
        2. Optionally removes duplicated current query
        3. Applies:
            - truncation OR
            - summarization + recent history
        4. Optionally enforces character budget

        Args:
            user_id: User identifier
            current_query: The current user query (used to avoid duplication)
            max_prompt_length: Optional character limit

        Returns:
            List of formatted lines ready for prompt inclusion
        """
        if not self.enabled:
            return []

        history = self._read_full_history(user_id)
        if not history:
            return []

        # Prevent duplicate query injection
        # If the caller already appended the current query to history,
        # we remove it so it doesn't appear twice in the prompt.
        if current_query:
            filtered = history.copy()

            if (
                filtered
                and filtered[-1].get("role") == "user"
                and filtered[-1].get("content") == current_query
            ):
                filtered = filtered[:-1]

            history = filtered

        if not history:
            return []

        max_messages = self.config.conversation.max_messages
        summary_trigger = self.config.conversation.summary_trigger
        summarize = self.config.conversation.summarize

        # Case 1: History is small → no summarization needed
        if len(history) <= max_messages:
            lines = self._format_recent(history)

        # Case 2: Large history → summarize older + keep recent
        elif summarize and len(history) >= summary_trigger:
            older = history[:-max_messages]
            recent = history[-max_messages:]

            lines = []

            summary = self._summarize_turns(older)

            if summary:
                lines.append("[SUMMARY OF OLDER CONTEXT]")
                lines.extend(summary)
                lines.append("")

            lines.append("[RECENT HISTORY]")
            lines.extend(self._format_recent(recent))

        # Case 3: No summarization → hard truncate
        else:
            lines = self._format_recent(history[-max_messages:])

        # Optional: enforce prompt length budget
        if max_prompt_length is not None:
            lines = self._fit_lines_to_budget(lines, max_prompt_length)

        return lines

    def _format_recent(self, turns: List[Dict[str, Any]]) -> List[str]:
        """
        Format turns into simple "role: content" strings.

        This is intentionally minimal and predictable for LLM input.

        Args:
            turns: Conversation entries

        Returns:
            List of formatted strings
        """
        return [f"{turn['role']}: {turn['content']}" for turn in turns]

    def _summarize_turns(self, turns: List[Dict[str, Any]]) -> List[str]:
        """
        Deterministic summarization of older conversation turns.

        IMPORTANT:
        ----------
        - This is NOT an LLM-based summarizer
        - It is intentionally simple for reproducibility and safety
        - Required by Issue #82 constraints

        Strategy:
        ---------
        - Normalize whitespace
        - Truncate long messages
        - Convert to bullet list
        - Enforce total character limit

        Args:
            turns: Older conversation turns

        Returns:
            List of summary lines
        """
        bullets: List[str] = []
        max_chars = self.config.conversation.max_summary_chars

        for turn in turns:
            role = turn["role"]

            # Normalize whitespace
            content = " ".join(turn["content"].split())

            # Truncate long content
            if len(content) > 140:
                content = content[:137] + "..."

            bullets.append(f"- {role}: {content}")

        summary_text = "\n".join(bullets)

        # Enforce summary size limit
        if len(summary_text) > max_chars:
            summary_text = summary_text[: max_chars - 3] + "..."

        return summary_text.splitlines()

    def _fit_lines_to_budget(
        self, lines: List[str], max_prompt_length: int
    ) -> List[str]:
        """
        Enforce a rough character budget for prompt context.

        Strategy:
        ---------
        - Join lines into a string
        - If too long → remove oldest lines first
        - Prioritizes recent context (which is more relevant)

        Args:
            lines: Context lines
            max_prompt_length: Max allowed characters

        Returns:
            Trimmed list of lines
        """
        kept = list(lines)

        # Remove oldest lines until under limit
        while kept and len("\n".join(kept)) > max_prompt_length:
            kept.pop(0)

        return kept