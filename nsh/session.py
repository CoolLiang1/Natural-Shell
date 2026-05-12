"""Local session cache — short-term memory for NL→command context.

When the user says "install nginx" and then "start it", the session
remembers that "it" refers to nginx by feeding recent translations back
into the system prompt on subsequent calls.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from nsh.config import CONFIG_DIR

SESSION_PATH = CONFIG_DIR / "session.json"
MAX_ENTRIES = 10


class Session:
    """Stores recent NL→command pairs and formats them as context."""

    def __init__(self, path: Path = SESSION_PATH, max_entries: int = MAX_ENTRIES) -> None:
        self._path = path
        self._max_entries = max_entries
        self._entries: list[dict[str, str]] = []
        self._load()

    # ---- public API --------------------------------------------------------

    def add(self, nl: str, command: str) -> None:
        """Record a translation pair, trimming to *max_entries*."""
        self._entries.append({
            "nl": nl,
            "command": command,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        self._save()

    def get_context(self) -> str:
        """Format recent translations as a context block for the system prompt.

        Returns an empty string when there are no prior entries.
        """
        if not self._entries:
            return ""
        lines = ["## 会话历史（最近的操作）"]
        for i, entry in enumerate(self._entries, 1):
            lines.append(f"{i}. 用户: \"{entry['nl']}\" → 命令: `{entry['command']}`")
        return "\n".join(lines)

    def last(self) -> dict[str, str] | None:
        """Return the most recent entry, or None."""
        return self._entries[-1] if self._entries else None

    def clear(self) -> None:
        """Wipe all session entries from memory and disk."""
        self._entries.clear()
        self._save()

    # ---- internal ----------------------------------------------------------

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self._entries = raw[-self._max_entries:]
        except (FileNotFoundError, json.JSONDecodeError):
            self._entries = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
