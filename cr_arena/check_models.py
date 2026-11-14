"""Check every LLM in the config answers with a parseable move (one cheap call each).

    uv run python -m cr_arena.check_models --config config.toml
"""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

from dotenv import load_dotenv

from .db import DB
from .game import Game
from .players import LLMPlayer, build_player


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--db", help="Override DATABASE_URL with a SQLite path or Postgres URL")
    args = ap.parse_args()
    load_dotenv()
    cfg = tomllib.loads(Path(args.config).read_text())
    db = DB(args.db)
    deck = (cfg.get("decks", {}).get("list") or [None])[0] or ["Knight", "Archer", "Giant", "Minions", "Fireball", "Zap", "Cannon", "Musketeer"]
    game = Game(deck, deck, seed=1, record=False)
    game.step([game.legal_moves(0)[0], game.legal_moves(1)[0]])
    while len(game.legal_moves(0)) == 1:  # wait out the opening lockout so there are real choices
        game.step([game.legal_moves(0)[0], game.legal_moves(1)[0]])
    moves = game.legal_moves(0)
    text = game.describe(0, moves)
    for spec in cfg["players"]:
        if spec.get("type", "llm") != "llm" or not spec.get("enabled", True):
            continue
        try:
            p = build_player(spec)
        except Exception as exc:
            print(f"FAIL  {spec['name']:<28} could not build: {exc}")
            db.add_model_check(spec["name"], spec.get("provider", ""), spec.get("model", ""), False, 0.0, f"could not build: {exc}")
            continue
        assert isinstance(p, LLMPlayer)
        p.start(game, 0)
        d = p.decide(game, 0, text, moves)
        status = "OK  " if d.ok else "FAIL"
        detail = moves[d.index].label() if d.ok else d.error
        print(f"{status}  {spec['name']:<28} {d.latency_s:5.1f}s  {detail}  usage={d.usage}")
        db.add_model_check(spec["name"], spec["provider"], spec["model"], d.ok, d.latency_s,
                           detail if d.ok else f"{d.error} | raw: {d.raw[:300]}")


if __name__ == "__main__":
    main()
