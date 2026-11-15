"""RoyaleBench v1 scenario specifications. Generate Harbor folders with build_v1."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

from royalegym import deck_ids
from royalegym.protocol import MatchSetup, ShuffleMode

from .decks import CLASSIC_DECKS
from .game import Game

VERSION = "1.0.0"
TITLE = "RoyaleBench v1"
PLANNER = dict(horizon_s=10.0, top_k=4, margin=40.0, two_ply=True, workers=0,
               elixir_hp=150.0, prefilter=True, three_ply=True, answer_k=3)


def protocol_digest() -> str:
    root = Path(__file__).parent
    digest = hashlib.sha256()
    for name in ["game.py", "decks.py", "player_types.py", "royale_task.py",
                 "scenario_task.py", "bots/planner.py", "cr_client.py", "telemetry.py"]:
        digest.update(name.encode())
        digest.update((root / name).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def fireball_damage() -> int:
    """Measure crown damage with this pinned engine, including its crown damage multiplier."""
    deck = CLASSIC_DECKS["giant-beatdown"]
    g = Game(deck, deck, 1, record=False, decision_ticks=100)
    order = ["Fireball"] + [c for c in deck if c != "Fireball"]
    g.setup = MatchSetup(decks=[deck_ids(order, g.cards)] * 2, shuffle=ShuffleMode.NONE,
                         start_tick=3600, elixir_milli=[10000, 0])
    g.engine.reset(1, g.setup)
    before = g.state.players[1].tower_hp[2]
    move = next(m for m in g.legal_moves(0) if m.card == "Fireball" and m.target == "enemy left princess tower")
    g.step([move, g.legal_moves(1)[0]])
    damage = before - g.state.players[1].tower_hp[2]
    if damage <= 0:
        raise RuntimeError("Fireball crown damage probe failed")
    return damage


def unit(card, x, y, team=1, hp=None):
    return {"card": card, "team": team, "x": x, "y": y, **({"hp": hp} if hp else {})}


def catalog() -> list[dict]:
    fb = fireball_damage()
    hp, king = 3052, 4824
    rows = []

    def add(number, slug, title, difficulty, player, enemy, rate, left, horizon, elixir, hand,
            units, objective, grading="win", overtime=False, own=(1, 1), foe=(1, 1),
            budget=None, limit=0, opponent_elixir=0, **extra):
        order = hand + [c for c in CLASSIC_DECKS[player] if c not in hand]
        s = dict(start_tick=(6000 if overtime else 3600) - round(left * 20), horizon_s=horizon,
                 elixir=elixir, opponent_elixir=opponent_elixir, order=order,
                 opponent_order=list(CLASSIC_DECKS[enemy]), units=units, grading=grading,
                 tower_hp=[[king, round(own[0]*hp), round(own[1]*hp)],
                           [king, round(foe[1]*hp), round(foe[0]*hp)]])
        if budget is not None:
            s.update(spend_budget=budget, damage_limit=limit)
        s.update(extra)
        row = dict(id=f"{number:02d}-{slug}", family=number, title=title, difficulty=difficulty,
                   benchmark=TITLE, version=VERSION, seed=100+number, agent_team=0,
                   agent_deck=list(CLASSIC_DECKS[player]), opponent_deck=list(CLASSIC_DECKS[enemy]),
                   player_deck_name=player, opponent_deck_name=enemy, csv_win_rate=rate,
                   opponent="planner", planner=deepcopy(PLANNER), decision_ticks=40,
                   objective=objective, scenario=s, release_gate=None)
        rows.append(row)
        return row

    add(1, "immediate-lethal", "Recognize immediate lethal", "easy", "giant-beatdown", "xbow-cycle", 62.6,
        45, 6, 4, ["Fireball", "Cannon", "Musketeer", "Knight"],
        [unit("Knight", 3.5, 12), unit("Archer", 4.5, 14)],
        "Win after your first decision. You may submit only one decision; the remaining six-second window runs automatically.",
        grading="first_decision_lethal", overtime=True, own=(.25, 1), foe=((fb-1)/hp, 1), max_decisions=1,
        verified_fireball_crown_damage=fb)
    add(2, "efficient-defense", "Efficient defensive placement", "easy", "giant-beatdown", "hog-2.6-cycle", 55.9,
        80, 12, 6, ["Cannon", "Musketeer", "Knight", "Zap"], [unit("HogRider", 3.5, 15)],
        "Over 12 seconds, keep both princess towers alive, take at most 400 total tower damage, and spend at most 4 elixir.",
        grading="defend", own=(.6, 1), budget=4, limit=400)
    add(3, "spell-placement", "Compare spell placements", "easy", "xbow-cycle", "lavaloon", 58.7,
        70, 12, 4, ["Fireball", "Tesla", "Knight", "Archer"],
        [unit("Minions", 3.5, 10, hp=130), unit("MegaMinion", 10.5, 12, hp=200), unit("Balloon", 3.5, 13.5, hp=600)],
        "Cast exactly one Fireball, keep both princess towers alive for 12 seconds, and take at most 150 total tower damage. Only Fireball and waiting are available.",
        grading="one_spell", budget=4, limit=150, only_card="Fireball")
    add(4, "tank-and-support", "Separate tank and support", "medium", "log-bait", "giant-beatdown", 52.8,
        55, 20, 6, ["InfernoTower", "Knight", "GoblinGang", "Log"],
        [unit("Giant", 3.5, 15.5), unit("Musketeer", 3.5, 19.5)],
        "Preserve both princess towers for 20 seconds and spend at most 9 elixir.",
        grading="defend", own=(.35, 1), budget=9, limit=10000)
    add(5, "successive-threats", "Budget across successive threats", "medium", "hog-2.6-cycle", "log-bait", 52.0,
        45, 20, 5, ["Log", "IceGolemite", "IceSpirits", "Musketeer"], [unit("GoblinGang", 3.5, 13)],
        "Keep both princess towers alive for 20 seconds, take at most 450 total tower damage, and spend at most 8 elixir. At elapsed 6.0s the opponent casts its reserved GoblinBarrel on your left tower (3.5, 6.5).",
        grading="defend", budget=8, limit=450, opponent_elixir=3,
        scheduled_attack=dict(after_s=6, card="GoblinBarrel", x=3.5, y=6.5))
    add(6, "unequal-threats", "Prioritize unequal threats", "medium", "giant-beatdown", "pekka-bridge-spam", 51.4,
        40, 20, 6, ["Cannon", "Musketeer", "Knight", "Zap"],
        [unit("BattleRam", 3.5, 14), unit("Bats", 14.5, 14)],
        "Keep both princess towers alive for 20 seconds. Spend at most 8 elixir in total, including at most 4 on placements in the right lane (x > 10.5).",
        grading="defend", own=(.15, .75), budget=8, limit=10000, right_lane_budget=4)
    add(7, "counterpush", "Convert defense into offense", "hard", "giant-beatdown", "pekka-bridge-spam", 51.4,
        35, 155, 7, ["Giant", "Fireball", "Cannon", "Zap"],
        [unit("Musketeer", 3.5, 14, team=0, hp=360), unit("Knight", 3.5, 14.5, team=0, hp=883)],
        "Win the continuation before the match ends (35 seconds of regulation plus up to 120 seconds of overtime).",
        own=(.25, 1), foe=(.35, 1))
    add(8, "cycle-to-lethal", "Cycle while defending", "hard", "hog-2.6-cycle", "giant-beatdown", 44.0,
        18, 18, 6, ["IceSpirits", "Skeletons", "IceGolemite", "Log"], [unit("Giant", 3.5, 12)],
        "Win before your tower falls and before overtime ends in 18 seconds. The full draw order is disclosed below; Fireball enters your hand after two card plays.",
        overtime=True, own=(.15, 1), foe=((fb-1)/hp, 1), verified_fireball_crown_damage=fb,
        disclose_queue=True)
    # Draw Cannon first, then Fireball, so a cheap cycle can expose a defensive building.
    rows[-1]["scenario"]["order"] = ["IceSpirits", "Skeletons", "IceGolemite", "Log", "Cannon", "Fireball", "HogRider", "Musketeer"]
    for variant, gy, by in [("commit", 20, 10.25), ("defend", 20, 10)]:
        add(9, f"tower-race-{variant}", f"Evaluate a tower race ({variant})", "hard", "giant-beatdown", "lavaloon", 46.8,
            30, 30, 5, ["Minions", "Fireball", "Knight", "Cannon"],
            [unit("Giant", 3.5, gy, team=0), unit("Musketeer", 3.5, gy-2, team=0), unit("Balloon", 3.5, by)],
            "Win the overtime continuation within 30 seconds. This is one of two independently graded positions in the tower-race family.",
            overtime=True, own=(.10, 1), foe=(.12, 1))
    add(10, "protect-the-lead", "Protect a crown lead", "hard", "xbow-cycle", "giant-beatdown", 37.3,
        12, 12, 8, ["Tesla", "Knight", "Archer", "Fireball"],
        [unit("Giant", 3.5, 13), unit("Musketeer", 3.5, 17)],
        "Retain a strict crown lead when regulation ends in 12 seconds.", grading="protect_lead", own=(.18, 1), foe=(1, 0))
    for variant, history, enemy_order in [
        ("log-ready", ["At -14s: enemy Log; -12s: Skeletons; -10s: IceSpirits; -8s: Knight; -6s: Archer. No subsequent enemy plays."],
         ["Log", "Tesla", "Fireball", "Xbow", "Skeletons", "IceSpirits", "Knight", "Archer"]),
        ("log-away", ["At -14s: enemy Skeletons; -12s: IceSpirits; -10s: Knight; -8s: Archer; -6s: Log. No subsequent enemy plays."],
         ["Tesla", "Fireball", "Xbow", "Skeletons", "IceSpirits", "Knight", "Archer", "Log"]),
    ]:
        row = add(11, f"opponent-cycle-{variant}", f"Track opponent cycle ({variant})", "hard", "log-bait", "xbow-cycle", 49.4,
                  30, 30, 5, ["GoblinBarrel", "Knight", "IceSpirits", "Log"], [],
                  "Win the continuation within 30 seconds. Infer the opponent's Log cycle from the visible pre-scenario history.",
                  overtime=True, own=(.30, .80), foe=(.12, 1), opponent_elixir=4, visible_history=history)
        row["scenario"]["opponent_order"] = enemy_order
        row["release_gate"] = "Both histories require winning reference traces and crossed-policy evidence that different commitments improve results."
    row = add(12, "comeback", "Plan a comeback", "hard", "xbow-cycle", "golem-beatdown", 32.7,
              50, 170, 8, ["Knight", "IceSpirits", "Skeletons", "Fireball"],
              [unit("Archer", 3.5, 12, team=0)],
              "Win from a 0-1 crown deficit, within 50 seconds of regulation plus up to 120 seconds of overtime. Xbow is out of hand.",
              own=(.45, 0), foe=(.30, 1))
    row["release_gate"] = "A winning reference continuation through the same action interface must demonstrate recovery."
    return rows
