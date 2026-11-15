"""Arena analytics: the numbers behind the Overview, Job, Match and Models pages.

Everything here takes a ``DB`` (and sometimes a config) and returns plain dicts and lists, so the API can
serve it and tests can check it without a UI. This is the logic that used to live inside the Streamlit
dashboard, minus pandas.
"""

from __future__ import annotations

import json
import os
import time
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

from .db import DB, ROOT
from .ratings import standings
from .site import _family

REG_TICKS, OT_TICKS = 3600, 2400  # 3:00 regulation and up to 2:00 overtime, in 50 ms ticks
TICK_S = 0.05
HUMAN = "human"
ACTIVE_JOB_STATUSES = ("running",)


def jl(value: Any, default: Any = None) -> Any:
    """json.loads for a DB cell that may be NULL or already decoded."""
    if isinstance(value, (list, dict)):
        return value
    return json.loads(value) if isinstance(value, str) and value else default


def num(value: Any) -> float | None:
    return None if value is None else float(value)


def integer(value: Any) -> int:
    return int(value or 0)


# ---------------------------------------------------------------------- config and prices
def config_path() -> Path:
    return Path(os.environ.get("CR_ARENA_CONFIG", ROOT / "config.toml"))


def load_arena_config(path: Path | None = None) -> dict:
    try:
        return tomllib.loads((path or config_path()).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {"players": []}


def load_arena_config_text(text: str) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {"players": []}


def prices(db: DB, config: dict | None = None) -> dict[str, tuple[float, float]]:
    """Model name -> (USD per 1M input tokens, per 1M output tokens), from the current config and every job's config."""
    out: dict[str, tuple[float, float]] = {}
    configs = [config if config is not None else load_arena_config()]
    for row in db.query("SELECT config_toml FROM jobs"):
        if row["config_toml"]:
            try:
                configs.append(tomllib.loads(row["config_toml"]))
            except tomllib.TOMLDecodeError:
                continue
    for cfg in configs:
        for p in cfg.get("players", []):
            if "price_in" in p and p["name"] not in out:
                out[p["name"]] = (float(p["price_in"]), float(p.get("price_out", 0)))
    return out


# ---------------------------------------------------------------------- per-model metrics
METRICS_SQL = """
    SELECT player,
           COUNT(*) AS decisions,
           SUM(asked) AS asked,
           SUM(CASE WHEN asked = 1 AND ok = 0 AND error NOT LIKE 'no MOVE%' AND error NOT LIKE 'illegal%' THEN 1 ELSE 0 END) AS api_errors,
           SUM(CASE WHEN asked = 1 AND ok = 0 AND (error LIKE 'no MOVE%' OR error LIKE 'illegal%') THEN 1 ELSE 0 END) AS bad_replies,
           SUM(CASE WHEN result LIKE 'played%' THEN 1 ELSE 0 END) AS plays,
           SUM(CASE WHEN result LIKE 'tried%' THEN 1 ELSE 0 END) AS refused,
           AVG(CASE WHEN asked = 1 THEN latency_s END) AS avg_latency_s,
           MAX(CASE WHEN asked = 1 THEN latency_s END) AS max_latency_s,
           SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out,
           SUM(cache_read) AS cache_read, SUM(cache_write) AS cache_write,
           SUM(COALESCE(cost_usd, 0)) AS reported_cost
    FROM decisions {where} GROUP BY player"""


def player_metrics(db: DB, job_id: int | None, price_table: dict[str, tuple[float, float]] | None = None) -> list[dict]:
    """Decision-level behaviour of every player: reliability, latency, tokens and cost. Bots have no API metrics."""
    where, params = ("WHERE job_id = ?", (job_id,)) if job_id is not None else ("", ())
    price_table = prices(db) if price_table is None else price_table
    out = []
    for r in db.query(METRICS_SQL.format(where=where), params):
        tokens_in, tokens_out = integer(r["tokens_in"]), integer(r["tokens_out"])
        cache_read, cache_write = integer(r["cache_read"]), integer(r["cache_write"])
        reported = float(r["reported_cost"] or 0)
        if reported > 0:  # provider-reported cost (the claude CLI) beats a price estimate
            cost = reported
        else:
            pin, pout = price_table.get(r["player"], (0.0, 0.0))
            cost = (tokens_in * pin + tokens_out * pout + cache_read * pin * 0.1 + cache_write * pin * 1.25) / 1e6
        asked = integer(r["asked"])
        max_latency = num(r["max_latency_s"])
        bot = tokens_in == 0 and (max_latency or 0) < 0.001  # no API calls: those columns do not apply
        out.append({
            "player": r["player"], "decisions": integer(r["decisions"]), "asked": asked,
            "api_errors": integer(r["api_errors"]), "bad_replies": integer(r["bad_replies"]),
            "plays": integer(r["plays"]), "refused": integer(r["refused"]),
            "error_rate": None if bot or not asked else integer(r["api_errors"]) / asked,
            "bad_reply_rate": None if bot or not asked else integer(r["bad_replies"]) / asked,
            "avg_latency_s": None if bot else num(r["avg_latency_s"]), "max_latency_s": None if bot else max_latency,
            "tokens_in": None if bot else tokens_in, "tokens_out": None if bot else tokens_out,
            "cache_read": None if bot else cache_read, "est_cost_usd": cost,
        })
    return sorted(out, key=lambda m: m["player"])


# ---------------------------------------------------------------------- results: win table, endings, head to head
def ending(match: dict) -> str:
    """How a finished match ended, from its crowns and length."""
    crowns = jl(match.get("crowns")) or [0, 0]
    ticks = match.get("ticks")
    if max(crowns) >= 3:
        return "3-crown knockout"
    if ticks is not None and ticks <= REG_TICKS:
        return "more crowns at full time" if crowns[0] != crowns[1] else "draw"
    if ticks is not None and ticks < REG_TICKS + OT_TICKS:
        return "overtime crown"
    return "tower-HP tiebreak" if match.get("winner") in (0, 1) else "draw"


ENDING_ORDER = ["3-crown knockout", "more crowns at full time", "overtime crown", "tower-HP tiebreak", "draw"]
_WIN_KEY = {"3-crown knockout": "three_crown_wins", "more crowns at full time": "won_at_full_time",
            "overtime crown": "won_in_overtime", "tower-HP tiebreak": "won_on_tiebreak"}


def win_table(results: list[dict]) -> list[dict]:
    """Per player: record, crowns, how the wins came, and wins by side. Best win rate first."""
    rows: dict[str, dict] = {}
    for r in results:
        crowns = jl(r.get("crowns")) or [0, 0]
        how = ending(r)
        for team, name in ((0, r["blue"]), (1, r["red"])):
            t = rows.setdefault(name, {"player": name, "games": 0, "wins": 0, "draws": 0, "losses": 0, "crowns_for": 0, "crowns_against": 0,
                                       "three_crown_wins": 0, "won_at_full_time": 0, "won_in_overtime": 0, "won_on_tiebreak": 0,
                                       "wins_as_blue": 0, "wins_as_red": 0})
            t["games"] += 1
            t["crowns_for"] += crowns[team]
            t["crowns_against"] += crowns[1 - team]
            if r["winner"] == 2:
                t["draws"] += 1
            elif r["winner"] == team:
                t["wins"] += 1
                t["wins_as_blue" if team == 0 else "wins_as_red"] += 1
                if how in _WIN_KEY:
                    t[_WIN_KEY[how]] += 1
            else:
                t["losses"] += 1
    out = list(rows.values())
    for t in out:
        t["win_rate"] = t["wins"] / t["games"]
        t["avg_crowns"] = round(t["crowns_for"] / t["games"], 2)
        t["avg_conceded"] = round(t["crowns_against"] / t["games"], 2)
    return sorted(out, key=lambda t: (-t["win_rate"], -t["avg_crowns"], t["player"]))


def ending_counts(results: list[dict]) -> list[dict]:
    counts = {k: 0 for k in ENDING_ORDER}
    for r in results:
        counts[ending(r)] += 1
    return [{"ending": k, "matches": counts[k]} for k in ENDING_ORDER]


def head_to_head(results: list[dict]) -> list[dict]:
    """One cell per (player, opponent): the player's points (win 1, draw 0.5) over games."""
    cells: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0])
    for r in results:
        s = {0: 1.0, 1: 0.0, 2: 0.5}[r["winner"]]
        for a, b, v in ((r["blue"], r["red"], s), (r["red"], r["blue"], 1 - s)):
            cells[(a, b)][0] += v
            cells[(a, b)][1] += 1
    return [{"player": a, "opponent": b, "points": p, "games": int(n), "score": p / n} for (a, b), (p, n) in sorted(cells.items())]


# ---------------------------------------------------------------------- jobs
def _status_counts(db: DB, job_id: int | None = None) -> dict[int, dict[str, int]]:
    where, params = ("WHERE job_id = ?", (job_id,)) if job_id is not None else ("", ())
    out: dict[int, dict[str, int]] = defaultdict(dict)
    for r in db.query(f"SELECT job_id, status, COUNT(*) AS n FROM matches {where} GROUP BY job_id, status", params):
        out[r["job_id"]][r["status"]] = int(r["n"])
    return out


def job_progress(job: dict, counts: dict[str, int], now: float | None = None) -> dict:
    """Progress fields shared by the Overview rows and the Job header."""
    now = time.time() if now is None else now
    done, total = counts.get("done", 0), int(job.get("total_matches") or 0)
    started = job.get("started_at")
    end = job["finished_at"] if job["status"] in ("done", "stopped") and job.get("finished_at") else now
    elapsed = (end - started) if started else None
    eta = (now - started) / done * (total - done) if started and done and job["status"] == "running" and total > done else None
    return {"done": done, "total": total, "running": counts.get("running", 0), "queued": counts.get("queued", 0),
            "crashed": counts.get("crashed", 0), "elapsed_s": elapsed, "eta_s": eta,
            "progress": (done / total) if total else 0.0}


def get_job(db: DB, name: str) -> dict | None:
    rows = db.query("SELECT * FROM jobs WHERE name = ?", (name,))
    return rows[0] if rows else None


def overview(db: DB, now: float | None = None) -> dict:
    """The Overview page: totals and one row per job, newest first."""
    jobs = db.query("SELECT * FROM jobs ORDER BY created_at DESC")
    counts = _status_counts(db)
    decisions = db.query("SELECT COUNT(*) AS n FROM decisions WHERE asked = 1 AND state != ''")[0]["n"]
    spend = sum(m["est_cost_usd"] for m in player_metrics(db, None))
    rows = []
    for j in jobs:
        rows.append({"name": j["name"], "status": j["status"], "notes": j["notes"] or "", "created_at": j["created_at"],
                     "started_at": j["started_at"], "players": jl(j["players"], []),
                     **job_progress(j, counts.get(j["id"], {}), now)})
    all_counts = [c for per_job in counts.values() for c in per_job.items()]
    return {"jobs": rows, "totals": {
        "jobs": len(jobs), "running_jobs": sum(1 for j in jobs if j["status"] == "running"),
        "matches_done": sum(n for s, n in all_counts if s == "done"), "matches_total": sum(n for _, n in all_counts),
        "decisions": int(decisions), "est_spend_usd": spend}}


def job_report(db: DB, job: dict, now: float | None = None) -> dict:
    """The Job page: header numbers, standings, head to head, win table, endings, per-model metrics and the config."""
    counts = _status_counts(db, job["id"]).get(job["id"], {})
    results = db.query("SELECT * FROM matches WHERE job_id = ? AND status = 'done'", (job["id"],))
    cfg = {}
    if job.get("config_toml"):
        try:
            cfg = tomllib.loads(job["config_toml"])
        except tomllib.TOMLDecodeError:
            cfg = {}
    llm = {p["name"] for p in cfg.get("players", []) if p.get("type", "llm") in ("llm", "mock")}
    model_ids = {p["name"]: p["model"] for p in cfg.get("players", []) if p.get("model")}
    metrics = player_metrics(db, job["id"])
    return {
        "name": job["name"], "status": job["status"], "notes": job.get("notes") or "", "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"), "config_toml": job.get("config_toml") or "", "anchor": cfg.get("tournament", {}).get("anchor"),
        **job_progress(job, counts, now), "est_spend_usd": sum(m["est_cost_usd"] for m in metrics),
        "standings": standings(results), "head_to_head": head_to_head(results), "win_table": win_table(results),
        "endings": ending_counts(results), "metrics": metrics, "llm_players": sorted(llm), "model_ids": model_ids,
        "decision_ticks": int(job.get("decision_ticks") or cfg.get("tournament", {}).get("decision_ticks", 40)),
    }


def job_matches(db: DB, job: dict, *, status: list[str] | None = None, player: str | None = None,
                page: int = 1, page_size: int = 50) -> dict:
    """The Matches tab: newest first, with live time-left for running matches, filtered and paginated."""
    rows = db.query("SELECT * FROM matches WHERE job_id = ? ORDER BY COALESCE(started_at, 9e18) DESC, match_id", (job["id"],))
    live = {r["match_id"]: r["time_left"] for r in db.query(
        """SELECT match_id, MIN(time_left) AS time_left FROM decisions WHERE job_id = ?
           AND match_id IN (SELECT match_id FROM matches WHERE job_id = ? AND status = 'running') GROUP BY match_id""",
        (job["id"], job["id"]))}
    players = sorted({p for r in rows for p in (r["blue"], r["red"]) if p})
    shown = [r for r in rows if (not status or r["status"] in status) and (not player or player in (r["blue"], r["red"]))]
    page_rows = shown[(page - 1) * page_size: page * page_size]
    out = []
    for r in page_rows:
        sb, sr = jl(r["stats_blue"], {}), jl(r["stats_red"], {})
        crowns = jl(r["crowns"])
        out.append({
            "match_id": r["match_id"], "status": r["status"], "blue": r["blue"], "red": r["red"], "seed": r["seed"],
            "winner": {0: r["blue"], 1: r["red"], 2: "draw"}.get(r["winner"]) if r["status"] == "done" else None,
            "crowns": crowns, "ending": ending(r) if r["status"] == "done" else None,
            "time_left_s": num(live.get(r["match_id"])), "length_s": r["ticks"] * TICK_S if r["ticks"] else None,
            "errors_blue": integer(sb.get("errors")) + integer(sb.get("illegal_or_unparsed")) if sb else None,
            "errors_red": integer(sr.get("errors")) + integer(sr.get("illegal_or_unparsed")) if sr else None,
            "wall_s": num(r["wall_s"]), "has_replay": bool(r["replay_path"]),
            "error": r["error"] if r["status"] == "crashed" else None,
        })
    return {"matches": out, "total": len(shown), "players": players, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------- one match
def match_report(db: DB, job: dict, match_id: str) -> dict | None:
    rows = db.query("SELECT * FROM matches WHERE job_id = ? AND match_id = ?", (job["id"], match_id))
    if not rows:
        return None
    m = rows[0]
    ticks = int(job.get("decision_ticks") or 40)
    decisions = db.query(
        """SELECT step, team, player, time_left, elixir, my_towers, enemy_towers, n_moves, asked, move, result, ok, error,
                  latency_s, tokens_in, tokens_out FROM decisions WHERE job_id = ? AND match_id = ? ORDER BY step, team""",
        (job["id"], match_id))
    deck = jl(m["deck"])
    crowns = jl(m["crowns"])
    return {
        "match_id": match_id, "job": job["name"], "status": m["status"], "blue": m["blue"], "red": m["red"], "seed": m["seed"],
        "winner": {0: m["blue"], 1: m["red"], 2: "draw"}.get(m["winner"]) if m["status"] == "done" else None,
        "crowns": crowns, "wall_s": num(m["wall_s"]), "error": m["error"], "has_replay": bool(m["replay_path"]),
        "decks": {"blue": deck["blue"], "red": deck["red"]} if isinstance(deck, dict) else None,
        "deck": deck if isinstance(deck, list) else None, "decision_seconds": ticks * TICK_S,
        "decisions": [{
            "step": d["step"], "team": int(d["team"]), "player": d["player"], "time_elapsed_s": d["step"] * ticks * TICK_S,
            "time_left_s": num(d["time_left"]), "elixir": num(d["elixir"]), "my_towers": d["my_towers"], "enemy_towers": d["enemy_towers"],
            "asked": bool(d["asked"]), "move": d["move"], "result": d["result"], "ok": bool(d["ok"]), "error": d["error"] or "",
            "latency_s": num(d["latency_s"]), "tokens_in": integer(d["tokens_in"]), "tokens_out": integer(d["tokens_out"]),
        } for d in decisions],
    }


def decision_detail(db: DB, job: dict, match_id: str, step: int, team: int) -> dict | None:
    rows = db.query("SELECT state, raw FROM decisions WHERE job_id = ? AND match_id = ? AND step = ? AND team = ?",
                    (job["id"], match_id, step, team))
    return {"state": rows[0]["state"] or "", "raw": rows[0]["raw"] or ""} if rows else None


# ---------------------------------------------------------------------- models
def dotenv_has(name: str, root: Path = ROOT) -> bool:
    f = root / ".env"
    if not f.exists():
        return False
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{name}=") and line.split("=", 1)[1].strip():
            return True
    return False


KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "openai_compat": "OPENROUTER_API_KEY"}


def models_overview(db: DB, config: dict | None = None) -> list[dict]:
    """Every configured player with its credentials status, last connectivity check and record across all jobs."""
    config = load_arena_config() if config is None else config
    checks: dict[str, dict] = {}
    for c in db.query("SELECT * FROM model_checks ORDER BY checked_at DESC"):
        checks.setdefault(c["name"], c)
    record = {r["player"]: r for r in standings(db.results(None))}
    out = []
    for p in config.get("players", []):
        kind = p.get("type", "llm")
        provider = p.get("provider", "-")
        env = p.get("api_key_env") or KEY_ENV.get(provider)
        key_ok = (bool(os.environ.get(env)) or dotenv_has(env)) if env else None
        family = _family(p.get("model") or p["name"], kind in ("llm", "mock"))
        if family == "other":
            family = _family(p["name"], True)
        chk = checks.get(p["name"])
        rec = record.get(p["name"], {})
        out.append({
            "name": p["name"], "family": family, "type": kind, "provider": provider, "model": p.get("model", ""),
            "effort": p.get("effort", ""), "enabled": bool(p.get("enabled", True)), "key_env": env, "key_ok": key_ok,
            "check_ok": None if chk is None else bool(chk["ok"]), "check_detail": "" if chk is None else chk["detail"],
            "checked_at": None if chk is None else chk["checked_at"],
            "price_in": p.get("price_in"), "price_out": p.get("price_out"),
            "games": int(rec.get("games", 0)), "wins": int(rec.get("W", 0)),
        })
    return out
