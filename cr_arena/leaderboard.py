"""Small, append-only leaderboard for the single-process shared game server."""

from __future__ import annotations

import csv
import os
import threading
from pathlib import Path


def guest_name(player_id: str) -> str:
    return f"Player {player_id[:6].upper()}"


class Leaderboard:
    fields = ("match_id", "player_id", "player_name", "winner")

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def _rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def record(self, match_id: str, player_id: str, player_name: str, winner: int) -> None:
        # Draws do not change either column. Only the server supplies outcomes.
        if winner not in (0, 1):
            return
        with self.lock:
            if any(row["match_id"] == match_id for row in self._rows()):
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            header = not self.path.exists() or self.path.stat().st_size == 0
            with self.path.open("a", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=self.fields)
                if header:
                    writer.writeheader()
                writer.writerow(dict(zip(self.fields, (match_id, player_id, player_name, winner))))
                file.flush()
                os.fsync(file.fileno())

    def standings(self, player_id: str, limit: int = 50) -> dict:
        with self.lock:
            rows = self._rows()
        players = {}
        for row in rows:
            player = players.setdefault(row["player_id"], {
                "player_id": row["player_id"], "name": "", "wins": 0, "losses": 0,
            })
            # The latest recorded name wins, ready for the future naming flow.
            player["name"] = row["player_name"] or guest_name(row["player_id"])
            player["wins" if row["winner"] == "0" else "losses"] += 1
        ranked = sorted(players.values(), key=lambda p: (-p["wins"], p["losses"], p["player_id"]))
        previous = None
        rank = 0
        for index, player in enumerate(ranked, 1):
            score = (player["wins"], player["losses"])
            if score != previous:
                rank = index
            player["rank"], player["is_you"] = rank, player["player_id"] == player_id
            previous = score
        you = next((p for p in ranked if p["is_you"]), {
            "player_id": player_id, "name": guest_name(player_id),
            "wins": 0, "losses": 0, "rank": None, "is_you": True,
        })
        # Keep browser identifiers out of the public response.
        def public(player):
            return {key: value for key, value in player.items() if key != "player_id"}
        return {"entries": [public(p) for p in ranked[:limit]], "you": public(you), "total": len(ranked)}
