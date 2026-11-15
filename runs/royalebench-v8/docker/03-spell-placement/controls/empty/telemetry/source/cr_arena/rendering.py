"""Embed the same renderer in served pages and portable, offline replay files."""

from pathlib import Path

_ROOT = Path(__file__).parent


def embed_renderer(page: str) -> str:
    marker = "<!-- __BATTLE_RENDERER__ -->"
    if page.count(marker) != 1:
        raise ValueError("page must have exactly one battle renderer marker")
    script = (_ROOT / "battle_renderer.js").read_text(encoding="utf-8")
    page = page.replace(marker, f"<script>\n{script}\n</script>")
    # Live hand portraits are inlined too, so no asset requests can race a new hand.
    art_marker = "<!-- __CARD_ART__ -->"
    if art_marker in page:
        art = (_ROOT / "card_art.js").read_text(encoding="utf-8")
        page = page.replace(art_marker, f"<script>\n{art}\n</script>")
    lobby_marker = "<!-- __LOBBY_ARENA__ -->"
    if lobby_marker in page:
        page = page.replace(lobby_marker, (_ROOT / "lobby_arena.svg").read_text(encoding="utf-8"))
    return page
