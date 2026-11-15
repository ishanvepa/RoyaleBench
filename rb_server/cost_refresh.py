"""Fetch missing costs as soon as runs finish, including while the browser is closed."""

from __future__ import annotations

import threading

from rb_evals import results as R

from .context import AppContext

COST_CHECK_SECONDS = 10


class CostRefresher:
    def __init__(self, ctx: AppContext, interval: float = COST_CHECK_SECONDS):
        self.ctx = ctx
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="rb-cost-refresh", daemon=True)

    def refresh(self, progress) -> None:
        runs = self.ctx.valkyrie.list_runs(self.ctx.cfg.benchmark)
        pending = [r for r in runs if R.uncached_task_count(self.ctx.cache, [r]) > 0]
        if pending:
            R.load_records(self.ctx.valkyrie, self.ctx.cache, pending, fetch_costs=True, on_progress=progress)

    def _run(self) -> None:
        while not self._stop.is_set():
            # CostsJob serializes automatic and manual downloads and records errors for the UI.
            self.ctx.costs.start(self.refresh)
            if self._stop.wait(self.interval):
                break

    def start(self) -> CostRefresher:
        self._thread.start()
        return self

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
