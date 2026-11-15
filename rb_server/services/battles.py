"""Model-vs-model battles, run by the same tournament runner as the command line."""

from __future__ import annotations

from cr_arena import analytics
from cr_arena.battles import MAX_PARALLEL, battle_plan, eligible_players, launch_battle, with_custom_deck
from cr_arena.db import ROOT
from cr_arena.decks import resolve_deck

from ..context import AppContext
from ..errors import ApiError, not_found
from ..schemas.legacy import BattleList, BattleOptions, BattlePreview, BattleRequest, BattleStatus
from .decks import list_decks
from .play import opponent_row

PREFIX = "battle-"


def _config_text() -> str:
    path = analytics.config_path()
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ApiError(409, "conflict", f"Cannot read the battle configuration {path.name}: {exc}") from exc


def options(ctx: AppContext) -> BattleOptions:
    players = [opponent_row(n, s) for n, s in eligible_players(_config_text()).items()]
    return BattleOptions(players=players, decks=list_decks(ctx).decks, max_parallel=MAX_PARALLEL, config_name=analytics.config_path().name)


def _config_for(ctx: AppContext, body: BattleRequest) -> str:
    text = _config_text()
    if body.deck and body.mode == "mirror":
        try:
            text = with_custom_deck(text, resolve_deck(ctx.db(), body.deck))
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc), [{"field": "deck", "message": str(exc)}]) from exc
    return text


def preview(ctx: AppContext, body: BattleRequest) -> BattlePreview:
    try:
        return BattlePreview(valid=True, games=len(battle_plan(_config_for(ctx, body), body.players, body.mode)))
    except ValueError as exc:
        return BattlePreview(valid=False, error=str(exc))


def _status(ctx: AppContext, name: str, *, with_output: bool = True) -> BattleStatus | None:
    proc = ctx.processes.get(name)
    if proc is None:
        return None
    state = "running" if proc.running else ("done" if proc.exit_code == 0 else "failed")
    exists = bool(ctx.db().query("SELECT id FROM jobs WHERE name = ?", (name,)))
    return BattleStatus(name=name, state=state, exit_code=proc.exit_code, output=proc.log_tail() if with_output else "", job_exists=exists)


def start(ctx: AppContext, body: BattleRequest) -> BattleStatus:
    text = _config_for(ctx, body)
    try:
        battle_plan(text, body.players, body.mode)  # refuse a bad request here; the launcher checks again
        run = launch_battle(ROOT, text, body.players, body.mode, body.parallel, ctx.db().target)
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc)) from exc
    except OSError as exc:
        raise ApiError(502, "bad_gateway", f"Could not start the battle runner: {exc}") from exc
    ctx.processes.add(run)
    status = _status(ctx, run.name)
    assert status is not None
    return status.model_copy(update={"players": list(body.players)})


def get(ctx: AppContext, name: str) -> BattleStatus:
    status = _status(ctx, name)
    if status is None:
        raise not_found("This server has no record of that battle (it may have been started before the server restarted). Look for it under Jobs.")
    return status


def list_recent(ctx: AppContext) -> BattleList:
    names = [n for n in ctx.processes._items if n.startswith(PREFIX)]  # noqa: SLF001 - the registry is ours
    out = [s for n in reversed(names) if (s := _status(ctx, n, with_output=False)) is not None]
    return BattleList(battles=out)
