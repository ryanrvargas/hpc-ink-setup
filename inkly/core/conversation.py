from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConversationManager:
    """
    Handles persistent conversation history per user and builds prompt-ready context.

    Full history storage and prompt-context generation are intentionally separate:
    - full history is stored on disk
    - processed history is built only when needed for prompt injection

    This preserves the complete conversation record while still allowing
    truncation or summarization when prompt size is limited.
    """

    def __init__(self, config):
        """
        Initialize the conversation manager.

        Expected config fields:
        - conversation.enabled
        - conversation.max_messages
        - conversation.summary_trigger
        - conversation.summarize
        - conversation.max_summary_chars
        """
        self.config = config

        # Whether conversation history is enabled at all.
        self.enabled = self.config.conversation.enabled

        # Directory where per-user conversation files are stored.
        # File structure: ~/.inkly/conversations/<user_id>.json
        self.base_dir = Path.home() / ".inkly" / "conversations"

        # Ensure the conversation directory exists before any reads or writes happen.
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _conversation_file(self, user_id: str) -> Path:
        """
        Build the file path for a user's conversation history.
        """
        return self.base_dir / f"{user_id}.json"

    def _read_full_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Read full conversation history from disk.

        This method is intentionally defensive:
        - returns [] if conversation history is disabled
        - returns [] if the file does not exist
        - returns [] if the file is unreadable or invalid
        - filters out malformed entries instead of trusting file contents blindly

        Returns:
            A list of validated conversation entries.
        """
        if not self.enabled:
            return []

        path = self._conversation_file(user_id)

        # No history exists yet for this user.
        if not path.exists():
            return []

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            # Fail safely if the file cannot be read or parsed.
            return []

        # Stored history must be a list of turn objects.
        if not isinstance(data, list):
            return []

        # Keep only entries with the minimum expected structure.
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
        Write full conversation history back to disk.

        This replaces the stored JSON file with the updated history list.
        """
        path = self._conversation_file(user_id)

        with path.open("w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def append_turn(self, user_id: str, role: str, content: str) -> None:
        """
        Append a single turn to the user's conversation history.

        Args:
            user_id: User identifier
            role: Conversation role, typically "user" or "assistant"
            content: Message content
        """
        if not self.enabled:
            return

        history = self._read_full_history(user_id)

        history.append(
            {
                # Store timestamps in UTC so ordering stays consistent across environments.
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "content": content,
            }
        )

        self._write_full_history(user_id, history)

    def append_exchange(self, user_id: str, question: str, answer: str) -> None:
        """
        Append a full user/assistant exchange as two consecutive turns.
        """
        self.append_turn(user_id, "user", question)
        self.append_turn(user_id, "assistant", answer)

    def load_recent(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Load the most recent N messages from conversation history.

        This is a simple truncation path with no summarization.
        """
        history = self._read_full_history(user_id)

        # Keep only the most recent configured number of messages.
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

        High-level flow:
        - load full history
        - optionally remove a duplicate current query
        - either keep recent turns as-is or summarize older turns
        - optionally trim the final lines to fit a prompt budget

        Returns:
            A list of prompt-ready text lines.
        """
        if not self.enabled:
            return []

        history = self._read_full_history(user_id)
        if not history:
            return []

        # Prevent the current query from appearing twice in the prompt.
        # This handles the case where the caller already appended the query
        # to conversation history before asking for built context.
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

        # If history is already small enough, keep it verbatim.
        if len(history) <= max_messages:
            lines = self._format_recent(history)

        # If summarization is enabled and history is large enough, summarize
        # older turns and keep the most recent turns verbatim.
        elif summarize and len(history) >= summary_trigger:
            older = history[:-max_messages]
            # recent = history[-max_messages:] NOTE: Not used

            lines = []

            summary = self._summarize_turns(older)

            if summary:
                lines.append("[SUMMARY OF OLDER CONTEXT]")
                lines.extend(summary)
                lines.append
