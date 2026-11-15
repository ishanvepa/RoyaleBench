"""Model players and the unified factory; bot implementations live in cr_arena.bots."""

from __future__ import annotations

import os
import random
import re
import time

from .game import Game
from .player_types import Decision, DeckBuild, InfraError, Player
from .bots.baselines import HeuristicBot, RandomBot  # compatibility exports

SYSTEM_PROMPT = """You are playing a real-time lane-battle card game (Clash Royale rules) as one of two players.

RULES IN BRIEF
- Each side has a king tower and two princess towers (left and right). Destroying a princess tower = 1 crown, the king tower = 3 crowns (instant win).
- Most crowns when time runs out wins. If tied, overtime starts and the next crown wins. If crowns are still tied when
  overtime ends, the match ends there and the side with more tower HP left, all its towers added up, wins (if even that
  is exactly equal, a fixed coin flip decides). There are no draws. So tower damage matters even when it takes no crown.
- You spend elixir (max 10, regenerates over time; faster in the last minute and overtime) to play cards from a 4-card hand. A played card goes to the back of your 8-card deck queue.
- Troops walk down their lane toward enemy buildings and fight what they meet. Buildings stay put and defend. Spells hit an area once.
- Good play: defend efficiently (spend less elixir than the enemy push costs), counter-attack with surviving troops, don't sit at full elixir (wasted regeneration), punish the lane where the enemy just spent elixir.

COORDINATES
Positions are in tiles from YOUR point of view: x from 0 (left) to 17 (right), y from 0 (your back edge) to 31 (enemy back edge). The river is at y ~15-16. Your princess towers are near y 6.5, the enemy's near y 25.5.

YOUR DECK (8 cards)
{deck}

HOW TO ANSWER
You get the current state and a numbered list of LEGAL MOVES. A decision happens every {interval:.1f} seconds of game time.
Think briefly, then end your reply with exactly one line of the form:
MOVE: <number>
Anything that is not a legal move number counts as waiting."""

MOVE_RE = re.compile(r"MOVE:\s*(\d+)", re.IGNORECASE)

RULES = SYSTEM_PROMPT.split("COORDINATES")[0].split("RULES IN BRIEF")[1].strip()

DECK_PROMPT = """You are about to play a real-time lane-battle card game (Clash Royale rules) against another player.
First you build your deck. The opponent builds theirs at the same time; you will not see it before the game.

RULES IN BRIEF
""" + RULES + """

HOW THE GAME IS PLAYED
Every {interval:.1f} seconds of game time you pick one move from a numbered list of legal moves: wait, or play a card
from your hand. Troops and buildings go to fixed zones on your side (left/right bridge, in front of / behind
your left/right tower, center, behind your king tower; once an enemy princess tower falls, also the enemy side of
that lane). Spells can be aimed at visible units (yours or the enemy's), at enemy towers, or at those fixed
zones and the enemy side of either lane.

CARD POOL (name: elixir cost, type, count, hitpoints, flying)
{pool}

HOW TO ANSWER
Pick exactly 8 different cards from the pool. Think briefly about win condition, defense, air defense, spells
and average elixir cost, then end your reply with exactly one line:
DECK: card1, card2, card3, card4, card5, card6, card7, card8
using the card names exactly as written in the pool. An invalid deck is replaced by a default deck and counted as an error."""


# ---------------------------------------------------------------------------------- LLMs
class LLMPlayer(Player):
    """One model + settings = one rated player. Stateless per decision (state carries the recent history)."""

    def __init__(self, name: str, provider: str, model: str, effort: str | None = None,
                 max_tokens: int = 4000, timeout_s: float = 90.0, base_url: str | None = None,
                 api_key_env: str | None = None, extra: dict | None = None):
        self.name = name
        self.provider = provider
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.extra = extra or {}
        self.system = ""
        if provider == "anthropic":
            import anthropic

            self.client = anthropic.Anthropic(timeout=timeout_s, max_retries=2)
        elif provider in ("openai", "openai_compat"):
            from openai import OpenAI

            key_env = api_key_env or ("OPENAI_API_KEY" if provider == "openai" else "OPENROUTER_API_KEY")
            key = os.environ.get(key_env)
            if not key:
                raise RuntimeError(f"{name}: env var {key_env} is not set")
            default_url = "https://api.openai.com/v1" if provider == "openai" else "https://openrouter.ai/api/v1"
            self.client = OpenAI(base_url=base_url or default_url, api_key=key,
                                 timeout=timeout_s, max_retries=2)
        elif provider == "claude_cli":
            # Uses the logged-in Claude Code CLI (`claude -p`), so no API key is needed.
            import shutil
            import tempfile

            # Not raising if `claude` is missing right now: Claude Code auto-updates replace the binary
            # for a moment, and calls retry (then abort the game as InfraError) instead.
            if not shutil.which("claude"):
                print(f"warning: {name}: `claude` CLI not on PATH yet; calls will retry")
            self.cwd = tempfile.mkdtemp(prefix="cr_arena_cli_")  # empty dir: no CLAUDE.md / project context
            # Thousands of short CLI runs must not trigger a self-update mid-tournament (that replaced the
            # binary under a running job once and broke every call for a moment).
            self.env = {**os.environ, "DISABLE_AUTOUPDATER": "1"}
        else:
            raise ValueError(f"unknown provider {provider!r}")

    def start(self, game, team):
        self.system = SYSTEM_PROMPT.format(deck=game.deck_summary(team), interval=game.decision_ticks * 0.05)

    def build_deck(self, pool, pool_text, interval):
        from .decks import parse_deck

        t0 = time.time()
        system = DECK_PROMPT.format(pool=pool_text, interval=interval)
        try:
            raw, usage = self._call("Build your deck now.", system=system)
        except InfraError:
            raise
        except Exception as exc:  # refusal etc. -> default deck, counted as a deck error
            return DeckBuild([], ok=False, error=f"{type(exc).__name__}: {exc}"[:500], latency_s=time.time() - t0)
        deck, err = parse_deck(raw, pool)
        return DeckBuild(deck or [], raw=raw, ok=deck is not None, error=err or "", latency_s=time.time() - t0, usage=usage)

    def decide(self, game, team, text, moves):
        t0 = time.time()
        try:
            raw, usage = self._call(text)
        except InfraError:
            raise
        except Exception as exc:  # refusal / unexpected reply -> wait, counted against the model
            return Decision(0, ok=False, error=f"{type(exc).__name__}: {exc}"[:500], latency_s=time.time() - t0)
        dt = time.time() - t0
        found = MOVE_RE.findall(raw or "")
        if not found:
            return Decision(0, raw=raw, ok=False, error="no MOVE line", latency_s=dt, usage=usage)
        idx = int(found[-1])
        if not 0 <= idx < len(moves):
            return Decision(0, raw=raw, ok=False, error=f"illegal move {idx}", latency_s=dt, usage=usage)
        return Decision(idx, raw=raw, latency_s=dt, usage=usage)

    def _call(self, text: str, system: str | None = None) -> tuple[str, dict]:
        from .telemetry import public_settings, utc, usage_metrics
        ctx = getattr(self, "telemetry_context", None)
        self._last_response = None
        self._last_request = None
        started, mono = utc(), time.monotonic_ns()
        import uuid
        call_id = uuid.uuid4().hex
        if ctx:
            ctx["capture"].emit("events", {"event": "model_call_started", "model_call_id": call_id,
                "decision_id": ctx["decision_id"], "observation_id": ctx["observation_id"], "team": ctx["team"],
                "model": self.model, "provider": self.provider, "system": system or self.system, "text": text})
        raw, usage, error = None, {}, None
        try:
            raw, usage = self._call_impl(text, system)
            return raw, usage
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if not isinstance(self._last_response, dict):
                self._last_response = None
            response = self._last_response or {}
            evidence = {
                    "model_call_id": call_id,
                    "decision_id": ctx["decision_id"] if ctx else None,
                    "observation_id": ctx["observation_id"] if ctx else None,
                    "team": ctx["team"] if ctx else None, "provider": self.provider, "requested_model": self.model,
                    "resolved_model": response.get("model"), "request_id": response.get("id"),
                    "started_at": started, "duration_s": (time.monotonic_ns() - mono) / 1e9,
                    "status": "error" if error else "success", "error": error,
                    "settings": {"effort": self.effort, "max_tokens": self.max_tokens,
                                 "timeout_s": self.timeout_s, "effective": None},
                    "request": public_settings(self._last_request or {"system": system or self.system, "text": text}),
                    "response": response or raw, "usage": usage_metrics(response.get("usage") or usage,
                                                                          provider=self.provider),
                    "raw_usage": usage, "reported_cost_usd": usage.get("cost"),
                    "stop_reason": response.get("stop_reason", response.get("choices", [{}])[0].get("finish_reason")
                                                if response.get("choices") else None),
                    "retry_visibility": "CLI attempt events" if self.provider == "claude_cli" else "SDK retries internal"}
            if ctx:
                ctx["capture"].emit("model_calls", evidence)
            else:
                if not hasattr(self, "pending_evidence"):
                    self.pending_evidence = []
                self.pending_evidence.append(evidence)

    def _call_impl(self, text: str, system: str | None = None) -> tuple[str, dict]:
        system = system or self.system
        if self.provider == "claude_cli":
            return self._call_cli(text, system)
        try:
            return self._call_sdk(text, system)
        except RuntimeError as exc:
            if str(exc).startswith("refusal"):
                raise
            raise InfraError(f"{type(exc).__name__}: {exc}") from exc
        except Exception as exc:  # SDK already retried twice: rate limit / overload / network
            raise InfraError(f"{type(exc).__name__}: {exc}"[:500]) from exc

    def _call_sdk(self, text: str, system: str) -> tuple[str, dict]:
        if self.provider == "anthropic":
            kwargs = dict(
                model=self.model,
                max_tokens=self.max_tokens,
                # Stable system prompt is cached across the ~100 decisions of a match.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": text}],
            )
            if self.effort:
                kwargs["output_config"] = {"effort": self.effort}
            kwargs.update(self.extra)
            self._last_request = kwargs
            r = self.client.messages.create(**kwargs)
            if hasattr(r, "model_dump"):
                self._last_response = r.model_dump(mode="json")
            if r.stop_reason == "refusal":
                raise RuntimeError(f"refusal: {getattr(r.stop_details, 'category', None)}")
            out = "".join(b.text for b in r.content if b.type == "text")
            u = r.usage
            return out, {"in": u.input_tokens, "out": u.output_tokens,
                         "cache_read": u.cache_read_input_tokens or 0,
                         "cache_write": u.cache_creation_input_tokens or 0}
        kwargs = dict(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
        )
        if self.provider == "openai":
            kwargs["max_completion_tokens"] = self.max_tokens
            if self.effort:
                kwargs["reasoning_effort"] = self.effort
            kwargs.update(self.extra)
        else:
            kwargs["max_tokens"] = self.max_tokens
            if self.effort:
                kwargs["extra_body"] = {"reasoning": {"effort": self.effort}}
            if self.extra:
                kwargs.setdefault("extra_body", {}).update(self.extra)
        self._last_request = kwargs
        r = self.client.chat.completions.create(**kwargs)
        if hasattr(r, "model_dump"):
            self._last_response = r.model_dump(mode="json")
        message = r.choices[0].message
        if getattr(message, "refusal", None):
            raise RuntimeError(f"refusal: {message.refusal}")
        out = message.content or ""
        u = r.usage
        return out, ({"in": u.prompt_tokens, "out": u.completion_tokens} if u else {})


    def _call_cli(self, text: str, system: str) -> tuple[str, dict]:
        import json
        import subprocess

        cmd = ["claude", "-p", "--model", self.model, "--output-format", "json", "--tools", "",
               "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
               "--system-prompt", system]
        if self.effort:
            cmd += ["--effort", self.effort]
        last = "?"
        # Rate limits / CLI hiccups: back off and retry for ~4 minutes, then abort the match (InfraError).
        for attempt, wait in enumerate((0, 5, 15, 30, 60, 120)):
            time.sleep(wait)
            ctx = getattr(self, "telemetry_context", None)
            if ctx:
                ctx["capture"].emit("events", {"event": "provider_attempt", "provider": self.provider,
                    "decision_id": ctx["decision_id"], "team": ctx["team"], "attempt": attempt,
                    "backoff_s": wait, "previous_error": last if attempt else None})
            try:
                p = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=self.timeout_s, cwd=self.cwd,
                                   env=self.env)
            except subprocess.TimeoutExpired:
                last = f"timeout after {self.timeout_s:.0f}s"
                continue
            except OSError as exc:  # binary missing / being replaced (CLI auto-update): infrastructure, retry
                last = f"claude CLI unavailable: {type(exc).__name__}: {exc}"
                continue
            try:
                d = json.loads(p.stdout)
            except json.JSONDecodeError:
                last = f"claude CLI exit {p.returncode}: {(p.stderr or p.stdout)[:300]}"
                if ctx:
                    ctx["capture"].emit("events", {"event": "provider_invalid_response", "attempt": attempt,
                        "stdout": p.stdout, "stderr": p.stderr, "decision_id": ctx["decision_id"]})
                continue
            self._last_response = d
            if ctx:
                ctx["capture"].emit("events", {"event": "provider_attempt_response", "attempt": attempt,
                    "decision_id": ctx["decision_id"], "team": ctx["team"], "response": d})
            if d.get("is_error"):
                last = f"claude CLI error: {str(d.get('result'))[:300]}"
                continue
            u = d.get("usage", {})
            return d.get("result") or "", {"in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0),
                                           "cache_read": u.get("cache_read_input_tokens", 0),
                                           "cache_write": u.get("cache_creation_input_tokens", 0),
                                           "cost": d.get("total_cost_usd", 0.0)}
        raise InfraError(last)


class MockLLM(Player):
    """Stand-in for an LLM, for testing the pipeline/dashboard without API keys: heuristic moves,
    fake latency and token counts, and a configurable rate of errors and unparseable replies."""

    def __init__(self, name: str, latency_s: float = 0.05, error_rate: float = 0.03, junk_rate: float = 0.05, seed: int = 0):
        self.name = name
        self.latency_s = latency_s
        self.error_rate = error_rate
        self.junk_rate = junk_rate
        self.rng = random.Random(seed)
        self.inner = HeuristicBot(name)

    def build_deck(self, pool, pool_text, interval):
        if self.rng.random() < self.junk_rate:
            return DeckBuild([], raw="DECK: Knight, Knight", ok=False, error="need 8 distinct cards, got 1")
        return DeckBuild(self.rng.sample(pool, 8), raw="(mock deck)", usage={"in": 1500, "out": 200})

    def decide(self, game, team, text, moves):
        lat = self.latency_s * (0.5 + self.rng.random())
        time.sleep(lat)
        usage = {"in": len(text) // 4 + 600, "out": self.rng.randint(40, 400)}
        r = self.rng.random()
        if r < self.error_rate:
            return Decision(0, ok=False, error="MockError: simulated API timeout", latency_s=lat)
        if r < self.error_rate + self.junk_rate:
            return Decision(0, raw="I would play the Giant.", ok=False, error="no MOVE line", latency_s=lat, usage=usage)
        idx = self.inner.decide(game, team, text, moves).index if self.rng.random() < 0.8 else self.rng.randrange(len(moves))
        return Decision(idx, raw=f"(mock reasoning)\nMOVE: {idx}", latency_s=lat, usage=usage)



def build_player(spec: dict) -> Player:
    kind = spec.get("type", "llm")
    if kind != "llm":
        from .bots.registry import build_bot

        return build_bot(spec)
    return LLMPlayer(
        name=spec["name"], provider=spec["provider"], model=spec["model"], effort=spec.get("effort"),
        max_tokens=spec.get("max_tokens", 4000), timeout_s=spec.get("timeout_s", 90.0),
        base_url=spec.get("base_url"), api_key_env=spec.get("api_key_env"), extra=spec.get("extra"),
    )
