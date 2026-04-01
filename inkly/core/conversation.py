from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConversationManager:
    """
    Persistent per-user conversation history.

    Storage and prompt-context generation are intentionally separate:
    - full history is stored on disk
    - processed history is generated for prompt injection
    """

    def __init__(self, config):
        # Store config reference so conversation limits and summarization
        # settings can be read from one place.
        self.config = config

        # Master on/off switch for conversation persistence.
        self.enabled = self.config.conversation.enabled

        # Per-user conversation files live under ~/.inkly/conversations.
        self.base_dir = Path.home() / ".inkly" / "conversations"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _conversation_file(self, user_id: str) -> Path:
        """
        Return the JSON file path for one user's conversation history.
        """
        return self.base_dir / f"{user_id}.json"

    def _read_full_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Load the full stored history for a user.

        Returns:
            A validated list of conversation turn dictionaries.
            Invalid or corrupt data is ignored safely.
        """
        if not self.enabled:
            return []

        path = self._conversation_file(user_id)
        if not path.exists():
            return []

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(data, list):
            return []

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
        Persist the full conversation history for a user.
        """
        path = self._conversation_file(user_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def append_turn(self, user_id: str, role: str, content: str) -> None:
        """
        Append one conversation turn to persistent storage.
        """
        if not self.enabled:
            return

        history = self._read_full_history(user_id)
        history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "content": content,
            }
        )
        self._write_full_history(user_id, history)

    def append_exchange(self, user_id: str, question: str, answer: str) -> None:
        """
        Append a user/assistant exchange as two back-to-back turns.
        """
        self.append_turn(user_id, "user", question)
        self.append_turn(user_id, "assistant", answer)

    def load_recent(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Return the most recent stored turns based on configured history size.
        """
        history = self._read_full_history(user_id)
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
            recent = history[-max_messages:]

            lines = []

            summary = self._summarize_turns(older)
            if summary:
                lines.append("[SUMMARY OF OLDER CONTEXT]")
                lines.extend(summary)
                lines.append("")

            lines.append("[RECENT HISTORY]")
            lines.extend(self._format_recent(recent))

        # Otherwise, just keep the most recent configured number of turns.
        else:
            lines = self._format_recent(history[-max_messages:])

        # Optionally enforce a rough prompt-size budget.
        if max_prompt_length is not None:
            lines = self._fit_lines_to_budget(lines, max_prompt_length)

        return lines

    def _format_recent(self, turns: List[Dict[str, Any]]) -> List[str]:
        """
        Convert recent conversation turns into prompt-ready lines.

        Format:
            user: ...
            assistant: ...
        """
        return [f"{turn['role']}: {turn['content']}" for turn in turns]

    def _summarize_turns(self, turns: List[Dict[str, Any]]) -> List[str]:
        """
        Build a deterministic summary of older conversation turns.

        This is intentionally lightweight and non-LLM-based.
        The goal is to keep older context visible without storing
        too much raw text in the final prompt.
        """
        bullets: List[str] = []
        max_chars = self.config.conversation.max_summary_chars

        for turn in turns:
            role = turn["role"]
            content = " ".join(turn["content"].split())

            # Clamp each summarized line so one long message does not
            # dominate the summary block.
            if len(content) > 140:
                content = content[:137] + "..."

            bullets.append(f"- {role}: {content}")

        summary_text = "\n".join(bullets)

        # Clamp total summary size to configured character budget.
        if len(summary_text) > max_chars:
            summary_text = summary_text[: max_chars - 3] + "..."

        return summary_text.splitlines()

    def _fit_lines_to_budget(
        self, lines: List[str], max_prompt_length: int
    ) -> List[str]:
        """
        Trim lines until the combined text fits within the prompt budget.

        Oldest lines are dropped first because recent turns usually matter more.
        """
        kept = list(lines)

        while kept and len("\n".join(kept)) > max_prompt_length:
            kept.pop(0)

        return kept