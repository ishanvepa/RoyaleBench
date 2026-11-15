"""Small helpers shared by the services."""

from __future__ import annotations

from cr_arena.site import LOGOS, _family


def family_of(model: str) -> str:
    """claude | gpt | gemini | ... | other, from a model key such as anthropic/claude-sonnet-4-6."""
    return _family(model or "", True)


def logo_url(family: str) -> str | None:
    """URL of the provider logo, or None for families without one (the UI falls back to initials)."""
    return f"/api/assets/logos/{family}" if family in LOGOS else None


def secret_name(reference: str) -> str:
    """Valkyrie stores secret references as ``valkyrie/tenants/<org id>/<name>``; only the name is shown."""
    return reference.rsplit("/", 1)[-1]
