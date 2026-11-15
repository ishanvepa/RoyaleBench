"""Legacy arena pages: results, overview, jobs, matches, replays and models."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

from cr_arena import analytics
from cr_arena import site
from cr_arena.db import ROOT

from ..context import AppContext
from ..errors import ApiError, not_found
from ..processes import spawn
from ..schemas.legacy import (
    ArenaGame,
    ArenaPlayer,
    ArenaResults,
    ArenaRunOut,
    ArenaRuns,
    CommandStatus,
    DecisionDetail,
    JobReport,
    JobSummaries,
    JobSummary,
    MatchList,
    MatchReport,
    ModelRow,
    ModelsOut,
    Overview,
)
from .common import logo_url

MEMO_TTL_S = 5.0  # polling pages ask often, and the database may be a remote Postgres


def _memo(ctx: AppContext, key: tuple, make):
    return ctx.memo.get_or_set(("legacy", *key), MEMO_TTL_S, make)


def family_resolver(config_toml: str | None):
    """name, is_llm -> provider family. A player called "model-a" is still recognised by the model id in its job's config."""
    models: dict[str, str] = {}
    if config_toml:
        try:
            models = {p["name"]: p["model"] for p in tomllib.loads(config_toml).get("players", []) if p.get("model")}
        except tomllib.TOMLDecodeError:
            models = {}

    def resolve(name: str, llm: bool) -> str:
        family = site._family(models.get(name) or name, llm)
        return site._family(name, llm) if family == "other" and name in models else family

    return resolve


def _job(ctx: AppContext, name: str) -> dict:
    job = analytics.get_job(ctx.db(), name)
    if job is None:
        raise not_found(f"No job named {name!r}.")
    return job


# ---------------------------------------------------------------------- results
def arena_runs(ctx: AppContext) -> ArenaRuns:
    def make():
        return ArenaRuns(runs=[ArenaRunOut(name=r["name"], status=r["status"], format=r["format"], player_count=r["player_count"],
                                           deck_rules=r["deck_rules"], scored_games=r["scored_games"], created_at=r.get("created_at"))
                               for r in site.result_runs(ctx.db())])

    return _memo(ctx, ("runs",), make)


def arena_results(ctx: AppContext, name: str) -> ArenaResults:
    def make():
        db = ctx.db()
        run = next((r for r in site.result_runs(db) if r["name"] == name), None)
        if run is None:
            raise not_found(f"No results for {name!r}.")
        job = _job(ctx, name)
        track = site.track_data(db, [job])
        resolve = family_resolver(job.get("config_toml"))
        for p in track["players"]:
            p["family"] = resolve(p["name"], p["llm"])
        players = [ArenaPlayer(
            rank=p["rank"], name=p["name"], family=p["family"], logo_url=logo_url(p["family"]), llm=p["llm"], games=p["games"],
            wins=p["W"], losses=p["L"], draws=p["D"], win_rate=p["win_rate"], crowns=p["crowns"], conceded=p["conceded"],
            crown_diff=p["crown_diff"], three_crowns=p["three_crowns"], reliability=p["reliability"], think_s=p["think_s"],
            cost_per_game=p["cost_per_game"], deck_valid=p["deck_valid"], decisions=p["decisions"],
            as_blue=p["as_blue"], as_red=p["as_red"]) for p in track["players"]]
        games = [ArenaGame(
            id=g["id"], job=g["job"], blue=g["blue"], red=g["red"], winner=g["winner"], crowns=g["crowns"], ticks=g["ticks"],
            deck_name=g["deck_name"], deck_kind="built" if isinstance(g["deck"], dict) else "preset" if isinstance(g["deck"], list) else "unknown",
            finished_at=g["t"], replay=g["replay"]) for g in track["games"]]
        return ArenaResults(name=name, format=run["format"], deck_rules=run["deck_rules"], running=bool(track.get("running")),
                            updated_at=job.get("finished_at") or job.get("started_at") or job.get("created_at"), players=players, games=games)

    return _memo(ctx, ("results", name), make)


# ---------------------------------------------------------------------- overview and jobs
def overview(ctx: AppContext) -> Overview:
    return _memo(ctx, ("overview",), lambda: Overview(**analytics.overview(ctx.db())))


def job_summaries(ctx: AppContext) -> JobSummaries:
    def make():
        rows = ctx.db().query("SELECT name, status, created_at, total_matches FROM jobs ORDER BY created_at DESC")
        return JobSummaries(jobs=[JobSummary(name=r["name"], status=r["status"], created_at=r["created_at"], total_matches=int(r["total_matches"] or 0)) for r in rows])

    return _memo(ctx, ("jobs",), make)


def job_report(ctx: AppContext, name: str) -> JobReport:
    def make():
        job = _job(ctx, name)
        report = analytics.job_report(ctx.db(), job)
        llm = set(report["llm_players"])
        resolve = family_resolver(job.get("config_toml"))

        def family(player: str) -> dict:
            fam = resolve(player, player in llm)
            return {"family": fam, "logo_url": logo_url(fam)}

        report["standings"] = [{**family(s["player"]), "rank": s["rank"], "player": s["player"], "games": s["games"], "wins": s["W"], "draws": s["D"],
                                "losses": s["L"], "win_rate": s["win_rate"], "crowns_for": s["crowns_for"], "crowns_against": s["crowns_against"]}
                               for s in report["standings"]]
        report["win_table"] = [{**w, **family(w["player"])} for w in report["win_table"]]
        report["metrics"] = [{**m, **family(m["player"])} for m in report["metrics"]]
        return JobReport(**report)

    return _memo(ctx, ("job", name), make)


def job_matches(ctx: AppContext, name: str, *, status: list[str] | None, player: str | None, page: int, page_size: int) -> MatchList:
    key = ("matches", name, tuple(status or ()), player, page, page_size)
    return _memo(ctx, key, lambda: MatchList(**analytics.job_matches(ctx.db(), _job(ctx, name), status=status, player=player, page=page, page_size=page_size)))


def match_report(ctx: AppContext, name: str, match_id: str) -> MatchReport:
    report = analytics.match_report(ctx.db(), _job(ctx, name), match_id)
    if report is None:
        raise not_found(f"No match {match_id!r} in job {name!r}.")
    return MatchReport(**report)


def decision_detail(ctx: AppContext, name: str, match_id: str, step: int, team: int) -> DecisionDetail:
    detail = analytics.decision_detail(ctx.db(), _job(ctx, name), match_id, step, team)
    if detail is None:
        raise not_found("No such decision.")
    return DecisionDetail(**detail)


# ---------------------------------------------------------------------- replay
REPLAY_CACHE = ROOT / "runs" / "replay-cache"


def replay_html(ctx: AppContext, name: str, match_id: str) -> str:
    """The saved game as a self-contained HTML viewer, cached by trace and viewer content."""
    job = _job(ctx, name)
    rows = ctx.db().query("SELECT replay_path, status FROM matches WHERE job_id = ? AND match_id = ?", (job["id"], match_id))
    if not rows:
        raise not_found(f"No match {match_id!r} in job {name!r}.")
    path = ctx.db().replay_file(job["id"], match_id, rows[0]["replay_path"])
    if path is None or not Path(path).exists():
        detail = "Replays are saved when a match finishes." if rows[0]["status"] != "done" else \
            "No replay was saved for this game: only the first few games of each pairing keep one (replays_per_pair)."
        raise not_found(detail)
    decision_rows = ctx.db().query(
        """SELECT step, team, player, raw, result, error FROM decisions
           WHERE job_id = ? AND match_id = ? AND asked = 1 ORDER BY step, team""", (job["id"], match_id))
    decisions = [{"tick": int(d["step"]) * int(job.get("decision_ticks") or 40), "team": int(d["team"]),
                  "label": d["player"], "steps": [
                      {"kind": "text", "title": "Agent", "text": d["raw"] or d["error"] or "No agent response recorded."},
                      {"kind": "tool_result", "title": "Action result", "text": d["result"] or "(not recorded)"}]}
                 for d in decision_rows]
    viewer_hash = hashlib.sha256(Path(path).read_bytes())
    viewer_hash.update(json.dumps(decisions, sort_keys=True).encode("utf-8"))
    for source in ("replay.html", "battle_renderer.js"):
        viewer_hash.update((ROOT / "cr_arena" / source).read_bytes())
    digest = viewer_hash.hexdigest()[:24]
    cached = REPLAY_CACHE / f"{digest}.html"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    from cr_arena.replay import patched_html

    try:
        html = patched_html(path, title=match_id, stride=2, decisions=decisions,
                            decisions_note="Recorded agent responses at each decision tick.")
    except Exception as exc:  # noqa: BLE001 - royalegym changed, or the trace is damaged
        raise ApiError(502, "bad_gateway", f"Could not render this replay: {type(exc).__name__}: {exc}") from exc
    REPLAY_CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(html, encoding="utf-8")
    return html


# ---------------------------------------------------------------------- models
CHECK = "model-check"


def models(ctx: AppContext) -> ModelsOut:
    def make():
        rows = []
        for m in analytics.models_overview(ctx.db()):
            rows.append(ModelRow(**m, logo_url=logo_url(m["family"])))
        return ModelsOut(models=rows, config_name=analytics.config_path().name)

    return _memo(ctx, ("models",), make)


def check_status(ctx: AppContext) -> CommandStatus:
    proc = ctx.processes.get(CHECK)
    if proc is None:
        return CommandStatus(name=CHECK, state="idle")
    state = "running" if proc.running else ("done" if proc.exit_code == 0 else "failed")
    return CommandStatus(name=CHECK, state=state, exit_code=proc.exit_code, output=proc.log_tail())


def start_check(ctx: AppContext) -> CommandStatus:
    """One cheap call per configured model, in the background (it can take a minute). Refuses to run two at once."""
    if ctx.processes.running(CHECK):
        raise ApiError(409, "conflict", "A model check is already running.")
    args = ["-m", "cr_arena.check_models", "--config", str(analytics.config_path())]
    if ctx.settings.arena_db and not ctx.settings.arena_db.startswith(("postgres://", "postgresql://")):
        args += ["--db", ctx.settings.arena_db]  # a Postgres URL stays in the environment (.env), never on a command line
    ctx.processes.add(spawn(CHECK, args, cwd=ROOT, log_path=ROOT / "runs" / "dashboard" / "model-check.log"))
    ctx.memo.clear()
    return check_status(ctx)
