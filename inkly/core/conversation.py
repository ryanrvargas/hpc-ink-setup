from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class ConversationManager:
    """
    Persistent per-user conversation history for Milestone 2.5.

    This is separate from structured event logging.
    """

    def __init__(self, config):
        self.config = config
        self.enabled = self.config.conversation.enabled
        self.base_dir = Path.home() / ".inkly" / "conversations"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _max_messages(self) -> int:
        return self.config.conversation.max_messages

    def _conversation_file(self, user_id: str) -> Path:
        return self.base_dir / f"{user_id}.json"

    def load(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        path = self._conversation_file(user_id)
        if not path.exists():
            return []

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        return data[-self._max_messages() :]

    def append_turn(self, user_id: str, role: str, content: str) -> None:
        if not self.enabled:
            return

        history = self.load(user_id)
        history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "content": content,
            }
        )

        history = history[-self._max_messages() :]

        path = self._conversation_file(user_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def append_exchange(self, user_id: str, question: str, answer: str) -> None:
        self.append_turn(user_id, "user", question)
        self.append_turn(user_id, "assistant", answer)
