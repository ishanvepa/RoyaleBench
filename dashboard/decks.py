"""Build and manage eight-card decks shared by the dashboard's play modes."""

import streamlit as st
from royalegym import RustEngine
from royalegym.protocol import Placement, card_is_spell

from cr_arena.decks import CLASSIC_DECKS, POOL


@st.cache_data
def card_details() -> dict:
    return {card.name: {
        "elixir": card.elixir,
        "kind": "Spell" if card_is_spell(card) else "Building" if card.placement == Placement.BUILDING else "Troop",
    } for card in RustEngine().cards() if card.name in POOL}


def _load_editor(deck):
    st.session_state.deck_name = deck["name"] if deck else ""
    st.session_state.deck_cards = list(deck["cards"]) if deck else []
    st.session_state.deck_preset = None


def _load_preset():
    preset = st.session_state.deck_preset
    if preset is not None:
        st.session_state.deck_cards = list(CLASSIC_DECKS[preset])


def page_decks(get_db):
    st.title("Decks")
    st.caption("Build an eight-card deck, save it, and choose it in Play. Saved decks are shared across this arena.")
    db = get_db()
    saved = {deck["id"]: deck for deck in db.custom_decks()}
    if pending := st.session_state.pop("deck_pending_edit", None):
        st.session_state.deck_editor = pending
        _load_editor(saved.get(pending))
    if st.session_state.get("deck_editor") not in [None, *saved]:
        st.session_state.deck_editor = None
        _load_editor(None)
    if "deck_cards" not in st.session_state:
        _load_editor(None)
    if message := st.session_state.pop("deck_notice", None):
        st.success(message)

    selected = st.selectbox("Edit a deck", [None, *saved], key="deck_editor",
                            format_func=lambda key: "Create a new deck" if key is None else saved[key]["name"],
                            on_change=lambda: _load_editor(saved.get(st.session_state.deck_editor)))
    editor, preview = st.columns([1.5, 1])
    details = card_details()
    with editor:
        st.subheader("Deck builder")
        st.selectbox("Start from a preset", list(CLASSIC_DECKS), index=None,
                     placeholder="Choose a preset", key="deck_preset", on_change=_load_preset)
        st.text_input("Deck name", key="deck_name", max_chars=80, placeholder="e.g. My hog cycle")
        cards = st.multiselect("Cards", sorted(POOL), key="deck_cards", max_selections=8,
                               format_func=lambda name: f"{name} · {details[name]['elixir']} elixir · {details[name]['kind']}",
                               placeholder="Search for a card", help="Select exactly eight different cards.")
        st.caption(f"{len(cards)} / 8 cards selected")
        if st.button("Save changes" if selected else "Save deck", type="primary",
                     disabled=len(cards) != 8 or not st.session_state.deck_name.strip(), key="save_deck"):
            try:
                deck_id = db.save_custom_deck(st.session_state.deck_name, cards, selected)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.deck_notice = "Deck saved. Choose it from the deck selectors in Play."
                st.session_state.deck_pending_edit = deck_id
                st.rerun()
        if selected:
            with st.expander("Delete this deck"):
                st.caption("Existing matches and replays keep their original cards.")
                if st.button("Delete deck", key="delete_deck"):
                    db.delete_custom_deck(selected)
                    st.session_state.deck_notice = "Deck deleted."
                    st.rerun()
    with preview:
        st.subheader("Deck preview")
        if cards:
            st.metric("Average elixir", f"{sum(details[c]['elixir'] for c in cards) / len(cards):.1f}")
            for card in cards:
                with st.container(border=True):
                    st.write(card)
                    st.caption(f"{details[card]['kind']} · {details[card]['elixir']} elixir")
        else:
            st.info("Choose cards to preview your deck and average elixir cost.")

    st.subheader("Saved decks")
    if not saved:
        st.info("No custom decks yet. Build your first deck above.")
    for deck in saved.values():
        with st.expander(deck["name"]):
            st.write(", ".join(deck["cards"]))
            st.caption(f"Average elixir: {sum(details[c]['elixir'] for c in deck['cards']) / 8:.1f}")
