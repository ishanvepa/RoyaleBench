"""Embed the same renderer in served pages and portable, offline replay files."""

from pathlib import Path

_ROOT = Path(__file__).parent


def embed_renderer(page: str) -> str:
    marker = "<!-- __BATTLE_RENDERER__ -->"
    if page.count(marker) != 1:
        raise ValueError("page must have exactly one battle renderer marker")
    script = (_ROOT / "battle_renderer.js").read_text(encoding="utf-8")
    return page.replace(marker, f"<script>\n{script}\n</script>")
