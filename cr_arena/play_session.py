"""One turn-based game: a human plays a bot or model through the interface the models get.

Every ``decision_ticks`` of game time the human picks one move from the legal-move list, and the game waits
while they decide, exactly as it waits for the models. Finished games are saved to the arena database under
the job "human-play", so they show up on the Job and Match pages with a replay.

This is the logic of the former Streamlit Play page, without any UI: ``snapshot()`` returns plain JSON for a
client to draw, and ``advance()`` applies a move.
"""

from __future__ import annotations

import threading
import time
import tomllib
import uuid
from pathlib import Path

from royalegym.protocol import EntityKind
from royalegym.replay import save_trace

from .game import OWN_ZONES, Game
from .players import Decision, build_player

HUMAN = 0  # the human plays blue, at the bottom of the board
OUT_DIR = Path("runs/round_robin/human-play")
HUMAN_JOB = "human-play"
TICK_CHOICES = (20, 40, 60)

KIND_NAME = {EntityKind.TROOP: "troop", EntityKind.BUILDING: "building", EntityKind.KING_TOWER: "king", EntityKind.PRINCESS_TOWER: "princess"}


def opponents(root: Path) -> dict[str, dict]:
    """The reference search bot plus every LLM player found in the config files (the first definition of a name wins)."""
    out = {"search-bot": {"name": "search-bot", "type": "search", "rollouts": 4, "horizon_s": 12.0}}
    for f in [root / "configs" / "claude.toml", root / "config.toml", *sorted((root / "configs").glob("*.toml"))]:
        try:
            cfg = tomllib.loads(f.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        for p in cfg.get("players", []):
            if p.get("type", "llm") == "llm" and p["name"] not in out:
                out[p["name"]] = {k: v for k, v in p.items() if k != "deck"}
    return out


class PlaySession:
    def __init__(self, session_id: str, opponent_spec: dict, my_deck: list[str], opp_deck: list[str], seed: int, ticks: int):
        self.id = session_id
        self.lock = threading.Lock()  # one request at a time per game
        self.game = Game(my_deck, opp_deck, seed=seed, decision_ticks=ticks)
        self.opp = build_player(opponent_spec)
        self.opp.start(self.game, 1)
        self.opp_name = opponent_spec["name"]
        self.seed, self.ticks = seed, ticks
        self.decks = (my_deck, opp_deck)
        self.step = 0
        self.rows: list[dict] = []
        self.t0 = time.time()
        self.saved: str | None = None
        self.match_id = f"human__vs__{self.opp_name}__{uuid.uuid4().hex}"
        self.log: list[str] = []
        self.opp_think: list[tuple[str, str]] = []
        self.touched = time.time()
        self.fast_forward()  # skip the opening lockout, when waiting is the only legal move

    # ------------------------------------------------------------------ playing
    def advance(self, my_move_index: int | None) -> None:
        """Apply the human's move (None = a forced wait) together with the opponent's, and run one interval."""
        game = self.game
        moves = [game.legal_moves(0), game.legal_moves(1)]
        text_h, text_o = game.describe(0, moves[0]), game.describe(1, moves[1])
        if len(moves[1]) > 1:
            d = self.opp.decide(game, 1, text_o, moves[1])
            game.consume_events(1)
        else:
            d = Decision(0, raw="(forced wait, not asked)")
        asked_h = my_move_index is not None
        if asked_h:
            game.consume_events(0)
        chosen = [moves[0][my_move_index or 0], moves[1][d.index]]
        left, _ = game.time_left_s()
        snap = [(p.elixir_milli / 1000, sum(p.tower_hp)) for p in game.state.players]
        res = game.step(chosen)
        clock = f"{int(left) // 60}:{int(left) % 60:02d}"
        for team, (dd, asked, txt) in enumerate(((Decision(chosen[0].index, raw="(human)"), asked_h, text_h), (d, len(moves[1]) > 1, text_o))):
            self.rows.append({
                "step": self.step, "team": team, "player": "human" if team == 0 else self.opp_name, "time_left": round(left, 1),
                "elixir": snap[team][0], "my_towers": snap[team][1], "enemy_towers": snap[1 - team][1], "n_moves": len(moves[team]),
                "asked": int(asked), "move": chosen[team].label(), "result": res[team], "ok": int(dd.ok), "error": dd.error,
                "latency_s": round(dd.latency_s, 2), "tokens_in": dd.usage.get("in", 0), "tokens_out": dd.usage.get("out", 0),
                "cache_read": dd.usage.get("cache_read", 0), "cache_write": dd.usage.get("cache_write", 0),
                "raw": dd.raw, "state": txt if asked else "", "cost_usd": dd.usage.get("cost", 0.0)})
        if res[1] != "wait":
            self.log.append(f"[{clock}] opponent {res[1]}")
            if d.raw and len(moves[1]) > 1 and not d.raw.startswith("("):
                self.opp_think.append((clock, d.raw))
        if res[0] != "wait":
            self.log.append(f"[{clock}] you {res[0]}")
        self.step += 1
        self.touched = time.time()

    def fast_forward(self, max_steps: int = 400) -> None:
        """Skip intervals where waiting is the only option (no elixir, or the opening lockout)."""
        n = 0
        while not self.game.over and len(self.game.legal_moves(0)) == 1 and n < max_steps:
            self.advance(None)
            n += 1

    def play(self, move_index: int) -> None:
        moves = self.game.legal_moves(0)
        if not 0 <= move_index < len(moves):
            raise ValueError(f"Move {move_index} is not legal right now.")
        self.advance(move_index)
        self.fast_forward()

    # ------------------------------------------------------------------ saving
    def save(self, db) -> str:
        """Store the finished game (decisions, replay) as a match of the "human-play" job. Safe to call twice."""
        if self.saved:
            return self.saved
        game = self.game
        winner, crowns, towers, ticks, trace = game.finish()
        mid = self.match_id
        (OUT_DIR / "replays").mkdir(parents=True, exist_ok=True)
        replay = OUT_DIR / "replays" / f"{mid}.msgpack"
        if trace is not None:
            save_trace(trace, replay)
        with db.transaction():
            jid = db.get_or_create_job(HUMAN_JOB, "", ["human"], [], self.ticks, 0, "Games played by a human on the Play page")
            db.queue_matches(jid, [{"match_id": mid, "blue": "human", "red": self.opp_name, "seed": self.seed,
                                    "deck": {"blue": self.decks[0], "red": self.decks[1]}}])
            db.match_started(jid, mid, "", str(replay))
            db.set_match_decks(jid, mid, *self.decks)
            db.add_decisions([(jid, mid, r["step"], r["team"], r["player"], r["time_left"], r["elixir"], r["my_towers"], r["enemy_towers"],
                               r["n_moves"], r["asked"], r["move"], r["result"], r["ok"], r["error"], r["latency_s"], r["tokens_in"],
                               r["tokens_out"], r["cache_read"], r["cache_write"], r["raw"], r["state"], r["cost_usd"]) for r in self.rows])
            stats = {"decisions": self.step, "asked": sum(r["asked"] for r in self.rows if r["team"] == 0)}
            db.match_finished(jid, {"match_id": mid, "winner": int(winner), "crowns": crowns, "tower_hp": towers, "ticks": ticks,
                                    "wall_s": round(time.time() - self.t0, 1), "stats_blue": stats, "stats_red": {}})
            n = db.query("SELECT COUNT(*) AS n FROM matches WHERE job_id = ?", (jid,))[0]["n"]
            db.execute("UPDATE jobs SET total_matches = ?, status = 'done' WHERE id = ?", (n, jid))
        self.saved = mid
        return mid

    # ------------------------------------------------------------------ what the client draws
    def snapshot(self) -> dict:
        game = self.game
        s = game.state
        me, en = s.players[0], s.players[1]
        left, overtime = game.time_left_s()
        over = game.over
        moves = [] if over else game.legal_moves(0)

        entities = []
        for e in s.entities:
            if e.hp <= 0:
                continue
            tx, ty = game.own_tiles(HUMAN, e.x, e.y)
            kind = KIND_NAME.get(e.kind, "troop")
            name = {"king": "King tower", "princess": "Princess tower"}.get(kind) or game.card_name(e.card_id)
            entities.append({"id": int(e.uid), "team": int(e.team), "kind": kind, "x": tx, "y": ty, "radius": e.radius / game.sub,
                             "hp": int(e.hp), "max_hp": int(e.max_hp), "flying": bool(e.flying), "deploying": e.deploy_ticks > 0,
                             "label": "K" if kind == "king" else "P" if kind == "princess" else name[:2], "name": name})
        spells = []
        for sp in s.spells:
            tx, ty = game.own_tiles(HUMAN, sp.aim_x, sp.aim_y)
            spells.append({"team": int(sp.team), "x": tx, "y": ty, "radius": 1.6, "name": game.card_name(sp.card_id)})

        hand = []
        for slot, cid in enumerate(me.hand):
            card = game.card_by_id.get(cid)
            if card is not None:
                cost = me.hand_costs[slot] if len(me.hand_costs) == len(me.hand) else card.elixir
                hand.append({"slot": slot, "name": card.name, "cost": int(cost), "kind": game.kind_of(card)})

        move_rows = []
        for mv in moves:
            tile = None
            if mv.slot >= 0:
                tx, ty = game.own_tiles(HUMAN, mv.x, mv.y)
                tile = [tx, ty]
            move_rows.append({"index": mv.index, "slot": mv.slot, "card": mv.card, "cost": mv.cost, "kind": mv.kind, "target": mv.target,
                              "x": tile[0] if tile else None, "y": tile[1] if tile else None})
        think = None
        if self.opp_think:
            clock, raw = self.opp_think[-1]
            think = {"time": clock, "text": raw}
        return {
            "id": self.id, "over": over, "winner": int(s.winner) if over else None, "opponent": self.opp_name, "step": self.step,
            "time_left_s": left, "overtime": overtime, "elixir": me.elixir_milli / 1000, "crowns": [int(me.crowns), int(en.crowns)],
            "hand": hand, "next_card": game.card_name(me.next_card), "events": list(game.mem[0].events[-6:]), "moves": move_rows,
            "entities": entities, "spells": spells, "zones": [{"name": k, "x": v[0], "y": v[1]} for k, v in OWN_ZONES.items()],
            "log": self.log[-40:], "opponent_thinking": think, "saved_as": self.saved,
        }
