"""The environment strip: who is signed in, is Modal connected, what can a job use."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from rb_evals.valkyrie import ValkyrieError

from ..context import AppContext
from ..schemas.evals import EnvironmentOut, EvalsSettingsOut, Identity, ModelPresetOut, QueueSummary
from .common import family_of, logo_url


def _preset_out(model_id: str, secret_env: str) -> ModelPresetOut:
    family = family_of(model_id)
    return ModelPresetOut(id=model_id, secret_env=secret_env, family=family, logo_url=logo_url(family))


def settings_out(ctx: AppContext) -> EvalsSettingsOut:
    c = ctx.cfg
    return EvalsSettingsOut(
        benchmark=c.benchmark, provider=c.provider, default_agent=c.default_agent, default_dataset=c.default_dataset,
        default_concurrency=c.default_concurrency, max_concurrency=c.max_concurrency,
        confirm_over_tasks=c.confirm_over_tasks, models=[_preset_out(m.id, m.secret_env) for m in c.models])


def environment(ctx: AppContext) -> EnvironmentOut:
    """Never raises for a Valkyrie problem: the UI shows the problem and disables what depends on it."""
    v = ctx.valkyrie
    calls = {"identity": v.identity, "providers": v.providers, "secrets": v.secret_names, "agents": v.agent_names,
             "queue": v.queue}

    def safe(fn):
        try:
            return fn(), None
        except ValkyrieError as exc:
            return None, exc

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = {name: pool.submit(safe, fn) for name, fn in calls.items()}
        results = {name: f.result() for name, f in futures.items()}

    identity, identity_error = results["identity"]
    error = identity_error or next((e for _, e in results.values() if e), None)
    providers = results["providers"][0] or {}
    queue = results["queue"][0]
    return EnvironmentOut(
        valkyrie_ok=identity is not None, valkyrie_error=str(error) if error else None,
        valkyrie_error_kind=error.kind if error else None,
        identity=Identity(**identity) if identity else None,
        modal_configured=ctx.cfg.provider in providers, providers=providers,
        secrets=results["secrets"][0] or [], agents=results["agents"][0] or [],
        queue=QueueSummary(**queue["summary"]) if queue else None,
        read_only=ctx.cfg.read_only, fake=ctx.fake, settings=settings_out(ctx))
