"""/api/legacy: decks, turn-based play against a bot or model, and model-vs-model battles."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Response

from ..deps import Ctx, Writable
from ..errors import COMMON_ERRORS
from ..schemas.legacy import (
    BattleList,
    BattleOptions,
    BattlePreview,
    BattleRequest,
    BattleStatus,
    DeckIn,
    DeckList,
    DeckOut,
    PlayMoveIn,
    PlayOptions,
    PlayStart,
    PlayState,
)
from ..services import battles as battles_service
from ..services import decks as decks_service
from ..services import play as play_service

router = APIRouter(tags=["legacy: play"], responses=COMMON_ERRORS)

DeckId = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,64}$")]
GameId = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,64}$")]
BattleName = Annotated[str, Path(pattern=r"^battle-[A-Za-z0-9-]{1,100}$")]


# ---------------------------------------------------------------------- decks
@router.get("/decks", response_model=DeckList, summary="Preset and saved decks, and the card pool")
def list_decks(ctx: Ctx):
    return decks_service.list_decks(ctx)


@router.post("/decks", response_model=DeckOut, status_code=201, dependencies=[Writable])
def create_deck(body: DeckIn, ctx: Ctx):
    return decks_service.create_deck(ctx, body)


@router.put("/decks/{deck_id}", response_model=DeckOut, dependencies=[Writable])
def update_deck(deck_id: DeckId, body: DeckIn, ctx: Ctx):
    return decks_service.update_deck(ctx, deck_id, body)


@router.delete("/decks/{deck_id}", status_code=204, dependencies=[Writable], summary="Delete a saved deck (matches already played keep their cards)")
def delete_deck(deck_id: DeckId, ctx: Ctx):
    decks_service.delete_deck(ctx, deck_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------- play
@router.get("/play/options", response_model=PlayOptions)
def play_options(ctx: Ctx):
    return play_service.options(ctx)


@router.post("/play/games", response_model=PlayState, status_code=201, dependencies=[Writable], summary="Start a game")
def start_game(body: PlayStart, ctx: Ctx):
    return play_service.start(ctx, body)


@router.get("/play/games/{game_id}", response_model=PlayState)
def get_game(game_id: GameId, ctx: Ctx):
    return play_service.get(ctx, game_id)


@router.post("/play/games/{game_id}/move", response_model=PlayState, dependencies=[Writable],
             summary="Play a move; returns the board after the opponent has replied")
def play_move(game_id: GameId, body: PlayMoveIn, ctx: Ctx):
    return play_service.move(ctx, game_id, body.index)


@router.delete("/play/games/{game_id}", status_code=204, summary="Abandon a game")
def abandon_game(game_id: GameId, ctx: Ctx):
    play_service.abandon(ctx, game_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------- battles
@router.get("/battles/options", response_model=BattleOptions)
def battle_options(ctx: Ctx):
    return battles_service.options(ctx)


@router.post("/battles/preview", response_model=BattlePreview, summary="How many games a battle would play, without starting it")
def preview_battle(body: BattleRequest, ctx: Ctx):
    return battles_service.preview(ctx, body)


@router.get("/battles", response_model=BattleList, summary="Battles started by this server, newest first")
def list_battles(ctx: Ctx):
    return battles_service.list_recent(ctx)


@router.post("/battles", response_model=BattleStatus, status_code=201, dependencies=[Writable], summary="Start a battle in the background")
def start_battle(body: BattleRequest, ctx: Ctx):
    return battles_service.start(ctx, body)


@router.get("/battles/{name}", response_model=BattleStatus)
def get_battle(name: BattleName, ctx: Ctx):
    return battles_service.get(ctx, name)
