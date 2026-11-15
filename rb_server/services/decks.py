"""Decks: the presets and the decks people save."""

from __future__ import annotations

from functools import lru_cache

from cr_arena.decks import card_catalog, deck_catalog

from ..context import AppContext
from ..errors import ApiError, not_found
from ..schemas.legacy import CardInfo, DeckIn, DeckList, DeckOut


@lru_cache(maxsize=1)
def cards() -> tuple[CardInfo, ...]:
    """The card pool from the engine. It never changes while the server runs, so it is read once."""
    return tuple(CardInfo(**c) for c in card_catalog())


def _deck_out(deck: dict) -> DeckOut:
    cost = {c.name: c.elixir for c in cards()}
    avg = sum(cost.get(name, 0) for name in deck["cards"]) / max(1, len(deck["cards"]))
    return DeckOut(**deck, avg_elixir=round(avg, 2))


def list_decks(ctx: AppContext) -> DeckList:
    return DeckList(decks=[_deck_out(d) for d in deck_catalog(ctx.db())], cards=list(cards()))


def _invalid(exc: ValueError) -> ApiError:
    text = str(exc)
    field = "name" if "name" in text.lower() else "cards"
    return ApiError(422, "validation_error", text, [{"field": field, "message": text}])


def _find(ctx: AppContext, deck_id: str) -> DeckOut:
    for deck in deck_catalog(ctx.db()):
        if deck["id"] == deck_id:
            return _deck_out(deck)
    raise not_found("This deck no longer exists.")


def create_deck(ctx: AppContext, body: DeckIn) -> DeckOut:
    try:
        deck_id = ctx.db().save_custom_deck(body.name, body.cards)
    except ValueError as exc:
        raise _invalid(exc) from exc
    return _find(ctx, deck_id)


def update_deck(ctx: AppContext, deck_id: str, body: DeckIn) -> DeckOut:
    _find(ctx, deck_id)
    try:
        ctx.db().save_custom_deck(body.name, body.cards, deck_id)
    except ValueError as exc:
        raise _invalid(exc) from exc
    return _find(ctx, deck_id)


def delete_deck(ctx: AppContext, deck_id: str) -> None:
    _find(ctx, deck_id)
    ctx.db().delete_custom_deck(deck_id)
