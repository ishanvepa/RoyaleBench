"""/api/assets: provider logos, served from cr_arena/assets (the single copy)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from cr_arena.site import LOGOS

from ..errors import not_found

router = APIRouter(tags=["assets"])
LOGO_DIR = Path(__file__).resolve().parents[2] / "cr_arena" / "assets" / "logos"


@router.get("/logos/{family}", response_class=FileResponse, responses={200: {"content": {"image/svg+xml": {}}}})
def get_logo(family: str):
    entry = LOGOS.get(family)
    if entry is None:
        raise not_found(f"No logo for {family!r}")
    return FileResponse(LOGO_DIR / f"{entry[1]}.svg", media_type="image/svg+xml",
                        headers={"Cache-Control": "public, max-age=86400"})
