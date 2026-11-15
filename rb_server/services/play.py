"""Turn-based play: one human against a bot or a model."""

from __future__ import annotations

import logging
import uuid

from cr_arena.db import ROOT
from cr_arena.decks import resolve_deck
from cr_arena.play_session import TICK_CHOICES, PlaySession, opponents
from cr_arena.players import InfraError
from cr_arena.site import _family

from ..context import AppContext
from ..errors import ApiError
from ..schemas.legacy import PlayOpponent, PlayOptions, PlayStart, PlayState
from .common import logo_url
from .decks import list_decks

log = logging.getLogger("rb_server")


def opponent_row(name: str, spec: dict) -> PlayOpponent:
    kind = "llm" if spec.get("type", "llm") == "llm" else "bot"
    family = _family(spec.get("model") or name, kind == "llm")
    if kind == "llm" and family == "other":
        family = _family(name, True)
    return PlayOpponent(name=name, family=family, logo_url=logo_url(family), kind=kind, provider=spec.get("provider", ""), model=spec.get("model", ""))


def options(ctx: AppContext) -> PlayOptions:
    return PlayOptions(opponents=[opponent_row(n, s) for n, s in opponents(ROOT).items()], decks=list_decks(ctx).decks, tick_choices=list(TICK_CHOICES))


def _deck(ctx: AppContext, key: str, field: str) -> list[str]:
    try:
        return resolve_deck(ctx.db(), key)
    except ValueError as exc:
        raise ApiError(422, "validation_error", str(exc), [{"field": field, "message": str(exc)}]) from exc


def _state(session: PlaySession) -> PlayState:
    return PlayState(**session.snapshot())


def start(ctx: AppContext, body: PlayStart) -> PlayState:
    spec = opponents(ROOT).get(body.opponent)
    if spec is None:
        raise ApiError(422, "validation_error", f"Unknown opponent {body.opponent!r}.", [{"field": "opponent", "message": "Choose an opponent from the list."}])
    if body.ticks not in TICK_CHOICES:
        raise ApiError(422, "validation_error", f"Decision interval must be one of {list(TICK_CHOICES)} ticks.", [{"field": "ticks", "message": "Unsupported interval."}])
    mine = _deck(ctx, body.deck, "deck")
    theirs = _deck(ctx, body.opponent_deck, "opponent_deck") if body.opponent_deck else mine
    try:
        session = PlaySession(uuid.uuid4().hex[:16], spec, mine, theirs, body.seed, body.ticks)
    except InfraError as exc:
        raise ApiError(502, "bad_gateway", f"Opponent model unreachable: {exc}") from exc
    except RuntimeError as exc:  # a missing API key surfaces here
        raise ApiError(422, "validation_error", str(exc), [{"field": "opponent", "message": str(exc)}]) from exc
    ctx.plays.add(session)
    return _state(session)


def get(ctx: AppContext, game_id: str) -> PlayState:
    session = ctx.plays.get(game_id)
    with session.lock:
        return _state(session)


def move(ctx: AppContext, game_id: str, index: int) -> PlayState:
    """Apply your move and the opponent's reply. Blocks while a model opponent thinks."""
    session = ctx.plays.get(game_id)
    with session.lock:
        if session.game.over:
            raise ApiError(409, "conflict", "This game is over.")
        try:
            session.play(index)
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc)) from exc
        except InfraError as exc:
            raise ApiError(502, "bad_gateway", f"Opponent model unreachable: {exc}") from exc
        save_error = None
        if session.game.over and not session.saved:
            try:
                session.save(ctx.db())
            except Exception as exc:  # noqa: BLE001 - the game itself is over either way; say why it was not stored
                log.exception("could not save human game")
                save_error = f"{type(exc).__name__}: {exc}"
        state = _state(session)
        state.save_error = save_error
        ctx.memo.clear()  # the new match changes the Overview and Job pages
        return state


def abandon(ctx: AppContext, game_id: str) -> None:
    ctx.plays.remove(game_id)
