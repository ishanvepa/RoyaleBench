"""One construction registry and one catalog shared by human-play surfaces.

Run configs still provide explicit player settings, preserving experiment provenance.
The human catalog may reference a named player in one of those files.
"""
from pathlib import Path
import tomllib

CATALOG = Path(__file__).resolve().parents[2] / "configs/bots.toml"
_MODES = {"live", "turn-based"}
_METADATA = {"modes", "preset", "preset_player"}


def human_bot_specs(mode: str, catalog: Path = CATALOG) -> dict[str, dict]:
    """Return fresh specs keyed by stable catalog IDs, in display order."""
    if mode not in _MODES:
        raise ValueError(f"unknown human-play mode: {mode}")
    catalog = Path(catalog)
    entries = tomllib.loads(catalog.read_text())["bots"]
    specs = {}
    names = set()
    for key, entry in entries.items():
        if not set(entry.get("modes", ())) <= _MODES:
            raise ValueError(f"{key}: unknown human-play mode")
        if mode not in entry.get("modes", ()):
            continue
        spec = {}
        if "preset" in entry:
            path = catalog.parent / entry["preset"]
            matches = [p for p in tomllib.loads(path.read_text())["players"]
                       if p["name"] == entry["preset_player"]]
            if len(matches) != 1:
                raise ValueError(f"{key}: preset must identify exactly one player")
            spec.update(matches[0])
        spec.update({k: v for k, v in entry.items() if k not in _METADATA})
        if "name" not in spec or "type" not in spec:
            raise ValueError(f"{key}: bot needs a name and type")
        if spec["name"] in names:
            raise ValueError(f"duplicate human-play bot name: {spec['name']}")
        if mode == "turn-based" and spec["type"] == "planner":
            raise ValueError("planner currently supports live play only")
        names.add(spec["name"])
        specs[key] = spec
    return specs


def frozen_search_v2_spec() -> dict:
    """Compatibility helper for the historical search_v2 module."""
    return human_bot_specs("turn-based")["search-v2"]


def build_bot(spec: dict):
    """Construct a numbered-move player. The live planner, with its own placements, lives in bots.live."""
    kind = spec.get("type")
    if kind == "mock":
        from ..players import MockLLM

        return MockLLM(spec["name"], latency_s=spec.get("latency_s", 0.05), error_rate=spec.get("error_rate", 0.03),
                       junk_rate=spec.get("junk_rate", 0.05), seed=spec.get("seed", 0))
    if kind == "random":
        from .baselines import RandomBot

        return RandomBot(spec["name"], seed=spec.get("seed", 0))
    if kind == "heuristic":
        from .baselines import HeuristicBot

        return HeuristicBot(spec["name"], attack_elixir=spec.get("attack_elixir", 8.0))
    if kind == "search":
        from .search import SearchBot

        return SearchBot(spec["name"], rollouts=spec.get("rollouts", 4), horizon_s=spec.get("horizon_s", 12.0),
                         seed=spec.get("seed", 0))
    if kind == "search-v2":
        from .search_v2 import SearchV2

        return SearchV2(**{k: v for k, v in spec.items() if k not in ("type", "enabled", "deck")})
    if kind == "planner":
        from .planner import PlannerPlayer

        return PlannerPlayer(spec["name"], **{k: v for k, v in spec.items() if k not in ("name", "type", "enabled", "deck")})
    raise ValueError(f"unknown bot type: {kind!r}")
