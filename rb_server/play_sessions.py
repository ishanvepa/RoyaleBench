"""In-memory store of turn-based games in progress."""

from __future__ import annotations

import threading
import time

from cr_arena.play_session import PlaySession

from .errors import ApiError


class PlaySessions:
    """Games live in memory only. An idle one expires, and the number in progress is capped, so an abandoned
    browser tab cannot pin an engine (and an opponent's model calls) forever."""

    def __init__(self, max_sessions: int = 8, idle_ttl_s: float = 2 * 3600):
        self.max_sessions = max_sessions
        self.idle_ttl_s = idle_ttl_s
        self._items: dict[str, PlaySession] = {}
        self._lock = threading.Lock()

    def _evict_idle(self, now: float) -> None:
        for sid in [sid for sid, s in self._items.items() if now - s.touched > self.idle_ttl_s]:
            del self._items[sid]

    def add(self, session: PlaySession) -> None:
        with self._lock:
            self._evict_idle(time.time())
            if len(self._items) >= self.max_sessions:
                # Make room by dropping the longest-idle game that is already over, else refuse.
                over = sorted((s for s in self._items.values() if s.game.over), key=lambda s: s.touched)
                if not over:
                    raise ApiError(409, "conflict", f"{self.max_sessions} games are already in progress. Finish or abandon one first.")
                del self._items[over[0].id]
            self._items[session.id] = session

    def get(self, session_id: str) -> PlaySession:
        with self._lock:
            self._evict_idle(time.time())
            session = self._items.get(session_id)
        if session is None:
            raise ApiError(404, "not_found", "This game has expired or never existed. Start a new one.")
        return session

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._items.pop(session_id, None)

    def __len__(self) -> int:
        return len(self._items)
