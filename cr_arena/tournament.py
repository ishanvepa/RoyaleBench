"""Round robin: every pair of players, every seed, both sides. Every run is a named job in SQLite;
rerunning the same job name resumes it.

    uv run python -m cr_arena.tournament --job main-v1                 # full run (resumable)
    uv run python -m cr_arena.tournament --job bots-smoke --bots-only  # free smoke test
    uv run python -m cr_arena.tournament --job main-v1 --dry-run       # schedule + call estimate
    uv run python -m cr_arena.tournament --leaderboard [--job main-v1] # print standings
Watch it live: uv run python -m rb_server, then open http://127.0.0.1:8000/legacy/overview
"""

from __future__ import annotations

import argparse
import os
import itertools
import re
import json
import time
import tomllib
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

from .db import DB
from .decks import CLASSIC_DECKS, DEFAULT_DECK, POOL, pool_text
from .match import play_match
from .players import DeckBuild, InfraError, build_player
from .ratings import head_to_head, standings, standings_text


def schedule(players: list[dict], seeds: list[int], decks: list[list[str]], deck_names: list[str] | None = None,
             mode: str = "mirror") -> list[dict]:
    """mirror: every (pair, deck) is played from both sides, both players with that deck; the seed
    is the deck's index. build: every (pair, seed) from both sides; decks are built before each game."""
    jobs = []
    if mode == "mirror" and deck_names:
        seeds = list(range(1, len(decks) + 1))
    by_name = {p["name"]: p for p in players}
    for a, b in itertools.combinations([p["name"] for p in players], 2):
        for i, seed in enumerate(seeds):
            deck = decks[i % len(decks)]  # mirror match by default: both sides get the same deck
            tag = f"__{deck_names[i % len(deck_names)]}" if (mode == "mirror" and deck_names) else ""
            for blue, red in ((a, b), (b, a)):
                # A player with its own `deck` in the config always plays that deck instead.
                db_, dr = by_name[blue].get("deck", deck), by_name[red].get("deck", deck)
                jobs.append({"match_id": f"{blue}__vs__{red}__s{seed}{tag}", "blue": blue, "red": red,
                             "seed": seed, "deck": db_ if db_ == dr else {"blue": db_, "red": dr},
                             "deck_blue": db_, "deck_red": dr})
    # Play round by round (every pair's game 1, then every pair's game 2, ...) so that while a job is
    # still running every player has played about the same number of games.
    order = {}
    for j in jobs:
        pair = tuple(sorted((j["blue"], j["red"])))
        order.setdefault(pair, []).append(j)
    rounds = max((len(v) for v in order.values()), default=0)
    for v in order.values():
        for i, j in enumerate(v):
            j["round"] = i  # the pair's i-th game
    return [v[i] for i in range(rounds) for v in order.values() if i < len(v)]


def prune_replays(db: DB, job_id: int, jobs: list[dict], keep: int) -> int:
    """Delete saved replays beyond the first `keep` games of each pairing."""
    extra = {j["match_id"] for j in jobs if j["round"] >= keep}
    n = 0
    for r in db.query("SELECT match_id, replay_path FROM matches WHERE job_id = ? AND replay_path IS NOT NULL AND replay_path != ''",
                      (job_id,)):
        if r["match_id"] not in extra:
            continue
        for f in (Path(r["replay_path"]), Path(r["replay_path"]).with_suffix(".html")):
            if f.exists():
                f.unlink()
                n += 1
        db.execute("UPDATE matches SET replay_path = '' WHERE job_id = ? AND match_id = ?", (job_id, r["match_id"]))
    return n


def equalize_plan(players: list[str], done: list[dict], remaining: list[dict]) -> list[dict]:
    """Fewest remaining scheduled games that bring every player to the same number of finished games
    (the current maximum, or the next reachable count). Earliest scheduled games of a pair are used first."""
    from collections import Counter

    g = Counter()
    for m in done:
        g[m["blue"]] += 1
        g[m["red"]] += 1
    by_pair: dict[tuple, list[dict]] = {}
    for j in remaining:
        by_pair.setdefault(tuple(sorted((j["blue"], j["red"]))), []).append(j)
    pairs = sorted(by_pair)
    top = max((g[p] for p in players), default=0)
    for target in range(top, top + 6):
        need = {p: target - g[p] for p in players}
        if sum(need.values()) % 2:
            continue
        used = Counter()

        def dfs() -> bool:
            p = max(need, key=lambda x: need[x])
            if need[p] == 0:
                return True
            for q in sorted(need, key=lambda x: -need[x]):
                pr = tuple(sorted((p, q)))
                if q != p and need[q] > 0 and used[pr] < len(by_pair.get(pr, [])):
                    need[p] -= 1; need[q] -= 1; used[pr] += 1
                    if dfs():
                        return True
                    need[p] += 1; need[q] += 1; used[pr] -= 1
            return False

        if dfs():
            return [j for pr in pairs for j in by_pair[pr][:used[pr]]]
    raise RuntimeError("cannot equalize with the remaining schedule")


def leaderboard(db: DB, job_id: int | None, anchor: str | None) -> str:
    results = db.results(job_id)
    return "STANDINGS (ranked by games won)\n" + standings_text(standings(results)) + "\n\nHEAD TO HEAD (row player's score / games)\n" + head_to_head(results)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--job", help="job name (default: timestamp). Same name = resume.")
    ap.add_argument("--notes", default="", help="free-text note shown on the dashboard")
    ap.add_argument("--db", help="SQLite database path (default: CR_ARENA_DB or runs/arena.db)")
    ap.add_argument("--bots-only", action="store_true", help="only non-LLM players (no API cost)")
    ap.add_argument("--players", help="comma-separated subset of player names")
    ap.add_argument("--parallel", type=int, help="matches at once (overrides config)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--leaderboard", action="store_true", help="only print standings (ranked by wins)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--deck-mode", choices=["mirror", "build"], help="override [tournament] deck_mode")
    ap.add_argument("--equalize", action="store_true",
                    help="play only the fewest games that give every player the same number of finished games; "
                         "the rest of the schedule is marked skipped")
    ap.add_argument("--prune-replays", action="store_true",
                    help="delete saved replays beyond [tournament] replays_per_pair for this job, then exit")
    args = ap.parse_args()

    load_dotenv()
    config_text = Path(args.config).read_text()
    cfg = tomllib.loads(config_text)
    t = cfg["tournament"]
    out_dir = Path(t.get("out_dir", "runs/round_robin"))
    anchor = t.get("anchor", "random-bot")
    db = DB(args.db)

    if args.leaderboard:
        job_id = None
        if args.job:
            row = db.query("SELECT id FROM jobs WHERE name = ?", (args.job,))
            job_id = row[0]["id"] if row else -1
        print(leaderboard(db, job_id, anchor))
        return

    specs = [p for p in cfg["players"] if p.get("enabled", True)]
    if args.bots_only:
        specs = [p for p in specs if p.get("type", "llm") != "llm"]
    if args.players:
        keep = set(args.players.split(","))
        specs = [p for p in specs if p["name"] in keep]
    by_name = {p["name"]: p for p in specs}
    seeds = t.get("seeds", [1, 2, 3])
    deck_mode = args.deck_mode or t.get("deck_mode", "mirror")
    # [decks] classic = ["giant-beatdown", ...] (names from cr_arena/decks.py) or list = [[8 cards], ...]
    deck_names = cfg.get("decks", {}).get("classic")
    if deck_names:
        decks = [CLASSIC_DECKS[n] for n in deck_names]
    else:
        decks = cfg.get("decks", {}).get("list") or [DEFAULT_DECK]
    decision_ticks = t.get("decision_ticks", 40)
    jobs = schedule(specs, seeds, decks, deck_names, deck_mode)

    job_name = args.job or time.strftime("job-%Y%m%d-%H%M%S")
    llm_names = {p["name"] for p in specs if p.get("type", "llm") == "llm"}
    # ~105 decision points per side at 2 s; about half are forced waits (no elixir) that skip the API.
    est_decisions = int((180 + 30) / (decision_ticks * 0.05) * 0.55)
    if args.dry_run:
        calls = sum((j["blue"] in llm_names) + (j["red"] in llm_names) for j in jobs) * est_decisions
        print(f"job {job_name} ({deck_mode}): {len(specs)} players, {len(jobs)} matches, ~{calls:,} LLM calls")
        for j in jobs[:20]:
            print("  ", j["match_id"])
        if len(jobs) > 20:
            print(f"   ... and {len(jobs) - 20} more")
        return

    if args.deck_mode:  # make the stored config say what actually ran
        if re.search(r"(?m)^deck_mode\s*=", config_text):
            config_text = re.sub(r'(?m)^deck_mode\s*=.*$', f'deck_mode = "{deck_mode}"  # set by --deck-mode', config_text, count=1)
        else:
            config_text = config_text.replace("[tournament]", f'[tournament]\ndeck_mode = "{deck_mode}"  # set by --deck-mode', 1)
    keep = t.get("replays_per_pair", 3)
    if args.prune_replays:
        row = db.query("SELECT id FROM jobs WHERE name = ?", (job_name,))
        print(f"deleted {prune_replays(db, row[0]['id'], jobs, keep) if row else 0} replay files (kept {keep} per pairing)")
        return
    job_id = db.get_or_create_job(job_name, config_text, [p["name"] for p in specs], seeds, decision_ticks,
                                  len(jobs), args.notes)
    db.queue_matches(job_id, jobs)
    done = db.done_match_ids(job_id)
    todo = [j for j in jobs if j["match_id"] not in done]
    if args.equalize:
        done_rows = db.query("SELECT blue, red FROM matches WHERE job_id = ? AND status = 'done'", (job_id,))
        todo = equalize_plan([p["name"] for p in specs], done_rows, todo)
        keep_ids = {j["match_id"] for j in todo}
        db.execute("UPDATE matches SET status = 'queued' WHERE job_id = ? AND status = 'skipped'", (job_id,))
        db.executemany("UPDATE matches SET status = 'skipped' WHERE job_id = ? AND match_id = ? AND status != 'done'",
                       [(job_id, j["match_id"]) for j in jobs if j["match_id"] not in done and j["match_id"] not in keep_ids])
        db.execute("UPDATE jobs SET total_matches = ? WHERE id = ?", (len(done) + len(todo), job_id))
        print(f"equalize: playing {len(todo)} games: " + ", ".join(j["match_id"] for j in todo))
    calls = sum((j["blue"] in llm_names) + (j["red"] in llm_names) for j in todo) * est_decisions
    print(f"job '{job_name}' (id {job_id}): {len(specs)} players, {len(jobs)} matches, {len(done)} done, "
          f"{len(todo)} to play, ~{calls:,} LLM calls")
    job_dir = out_dir / job_name
    from .telemetry import atomic_json, digest, public_settings, utc
    run_manifest = {"run_id": f"local-{job_id}", "job": job_name, "created_at": utc(),
                    "planned_tasks": jobs, "settings": public_settings(cfg),
                    "cohort_id": digest(public_settings(cfg)), "decision_ticks": decision_ticks}
    atomic_json(job_dir / "run_manifests" / f"{digest(run_manifest)}.json", run_manifest)
    atomic_json(job_dir / "run_manifest.json", run_manifest)
    db.set_job_status(job_id, "running")

    def run(job):
        mid = job["match_id"]
        record = job["round"] < keep  # only the first few games of each pairing save a replay
        db.match_started(job_id, mid, str(job_dir / "logs" / f"{mid}.jsonl"),
                         str(job_dir / "replays" / f"{mid}.msgpack") if record else "")

        def on_step(rows):
            db.add_decisions([(job_id, mid, r["step"], r["team"], r["player"], r["time_left"], r["elixir"],
                               r["my_towers"], r["enemy_towers"], r["n_moves"], r["asked"], r["move"], r["result"],
                               r["ok"], r["error"], r["latency_s"], r["tokens_in"], r["tokens_out"], r["cache_read"],
                               r["cache_write"], r["raw"], r["state"], r["cost_usd"]) for r in rows])

        # Fresh player objects per match: each match has its own deck / prompt / RNG.
        blue = build_player(by_name[job["blue"]])
        red = build_player(by_name[job["red"]])
        deck_blue, deck_red = job["deck_blue"], job["deck_red"]
        builds = [None, None]
        if deck_mode == "build":
            # Both sides build blind, at the same time. Bots (no opinion) play their fixed/default deck.
            with ThreadPoolExecutor(max_workers=2) as bp:
                futs = [bp.submit(p.build_deck, POOL, POOL_TEXT, decision_ticks * 0.05) for p in (blue, red)]
                builds = [f.result() for f in futs]
            decks_now = []
            for p, b, fixed in ((blue, builds[0], deck_blue), (red, builds[1], deck_red)):
                decks_now.append(b.deck if (b and b.ok) else (fixed if b is None else DEFAULT_DECK))
            deck_blue, deck_red = decks_now
        db.set_match_decks(job_id, mid, deck_blue, deck_red)
        res = play_match(blue, red, deck_blue, deck_red, job["seed"], mid, job_dir,
                         decision_ticks=decision_ticks, verbose=args.verbose, on_step=on_step, record=record,
                         run_context=run_manifest)
        for key, b in (("stats_blue", builds[0]), ("stats_red", builds[1])):
            if b is not None:
                res[key]["deck_build"] = {"deck": b.deck, "ok": b.ok, "error": b.error, "raw": b.raw,
                                          "latency_s": round(b.latency_s, 1), "usage": b.usage}
                res[key]["cost_usd"] = round(res[key].get("cost_usd", 0.0) + b.usage.get("cost", 0.0), 6)
        return res

    from .game import Game

    POOL_TEXT = pool_text(Game(DEFAULT_DECK, DEFAULT_DECK, seed=0, record=False).cards)
    parallel = args.parallel or t.get("parallel", 4)
    crashed = 0
    pool = ThreadPoolExecutor(max_workers=parallel)
    try:
        futs = {pool.submit(run, j): j for j in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            job = futs[fut]
            try:
                res = fut.result()
            except InfraError as exc:
                crashed += 1
                db.match_crashed(job_id, job["match_id"], f"InfraError (not scored, rerun the job to retry): {exc}")
                print(f"[{n}/{len(todo)}] {job['match_id']} ABORTED, model unreachable: {exc}")
                continue
            except Exception:
                crashed += 1
                db.match_crashed(job_id, job["match_id"], traceback.format_exc())
                print(f"[{n}/{len(todo)}] {job['match_id']} CRASHED (rerun the job to retry)\n{traceback.format_exc()}")
                continue
            db.match_finished(job_id, res)
            w = {0: res["blue"], 1: res["red"], 2: "draw"}[res["winner"]]
            print(f"[{n}/{len(todo)}] {job['match_id']}: winner {w}, crowns {res['crowns']}, {res['wall_s']}s "
                  f"(errors blue {res['stats_blue']['errors']}/red {res['stats_red']['errors']})")
    except KeyboardInterrupt:
        # Don't wait for in-flight matches: they stay 'running' in the DB and are re-queued on resume.
        db.set_job_status(job_id, "stopped")
        print("\nstopped; rerun with the same --job to resume")
        pool.shutdown(wait=False, cancel_futures=True)
        os._exit(130)
    pool.shutdown()
    db.set_job_status(job_id, "done" if crashed == 0 else "stopped")
    print()
    print(leaderboard(db, job_id, anchor))


if __name__ == "__main__":
    main()
