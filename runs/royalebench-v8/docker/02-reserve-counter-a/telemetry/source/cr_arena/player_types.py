"""Shared player interface and decision/result types for bots and model players."""
from __future__ import annotations

from dataclasses import dataclass, field

from .game import Game, Move


class InfraError(RuntimeError):
    """The model could not be reached (rate limit, CLI/network failure) after retries. The match is
    aborted and re-queued instead of being scored, so infrastructure problems never count as moves."""


@dataclass
class DeckBuild:
    deck: list
    raw: str = ""
    ok: bool = True
    error: str = ""
    latency_s: float = 0.0
    usage: dict = field(default_factory=dict)


@dataclass
class Decision:
    index: int
    raw: str = ""
    ok: bool = True  # False when the reply could not be parsed / errored -> treated as wait
    error: str = ""
    latency_s: float = 0.0
    usage: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)


class Player:
    name: str

    def start(self, game: Game, team: int) -> None:  # called once per match
        pass

    def decide(self, game: Game, team: int, text: str, moves: list[Move]) -> Decision:
        raise NotImplementedError

    def build_deck(self, pool: list[str], pool_text: str, interval: float) -> DeckBuild | None:
        """Deck-building track. None = this player has no opinion (it plays its fixed/default deck)."""
        return None
