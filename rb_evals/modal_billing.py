"""Persist Modal's metered endpoint charges, separately from harness API costs.

Reports cover complete UTC hours, including idle serving compute. They are never
apportioned to tasks/runs: multiple evaluations can share an endpoint.
"""
from __future__ import annotations

import dataclasses
import json
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


class ModalBilling:
    def __init__(self, root: Path, models=(), *, fetch=None, now=None):
        self.root = Path(root)
        self.models = tuple(m for m in models if m.modal_app)
        self.fetch = fetch or self._fetch
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def _read(self, name: str) -> dict:
        try:
            return json.loads((self.root / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self, name: str, data: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root, delete=False) as f:
            tmp = Path(f.name)
            json.dump(data, f, allow_nan=False)
        try:
            os.replace(tmp, self.root / name)
        finally:
            tmp.unlink(missing_ok=True)

    @staticmethod
    def _fetch(start, end, models):
        import modal

        workspace = modal.Workspace.from_context()
        workspace.hydrate()
        # Resolve exact App identity; never match a model substring in a bill.
        identities = {}
        for model in models:
            try:
                identities[model.id] = modal.App.lookup(model.modal_app, create_if_missing=False).app_id
            except modal.exception.NotFoundError:
                # One missing/deleted endpoint must not hide the other models' bills.
                identities[model.id] = None
        # Modal rejects hourly ranges longer than seven days. Fetch the month in
        # bounded windows, then persist only after every window succeeds.
        rows = []
        cursor = start
        while cursor < end:
            window_end = min(cursor + timedelta(days=7), end)
            rows.extend(workspace.billing.report(start=cursor, end=window_end, resolution="h", tag_names=["*"]))
            cursor = window_end
        return workspace.name, identities, [dataclasses.asdict(row) for row in rows]

    def sync(self) -> bool:
        if not self.models or not self._lock.acquire(blocking=False):
            return False
        try:
            now = self.now().astimezone(timezone.utc)
            # Include every completed hour. Reports are provisional: requerying
            # the window picks up ingestion delays without hiding available bills.
            end = now.replace(minute=0, second=0, microsecond=0)
            start = (end - timedelta(microseconds=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            workspace, identities, rows = self.fetch(start, end, self.models)
            snapshots = [self._snapshot(workspace, start, end, now, identities, rows)]
            # Finish and reconcile a recorded previous month after rollover,
            # including its last hour and any late-posted corrections.
            previous = (start - timedelta(microseconds=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if self._read(f"{workspace}-{previous:%Y-%m}.json"):
                old_workspace, old_ids, old_rows = self.fetch(previous, start, self.models)
                if old_workspace != workspace:
                    raise ValueError("Modal workspace changed during sync")
                snapshots.insert(0, self._snapshot(workspace, previous, start, now, old_ids, old_rows))
            # Whole-window replacement is idempotent and picks up corrected bills.
            # Fetch every window before replacing any previously complete snapshot.
            for snapshot in snapshots:
                month = snapshot["start"][:7]
                self._save(f"{workspace}-{month}.json", snapshot)
            self._save("latest.json", snapshots[-1])
            self._save("status.json", {"error": None, "attempted_at": now.isoformat()})
            return True
        except Exception as exc:
            # SDK exceptions can contain headers. Show a useful safe status instead.
            error = ("Modal billing sync failed (" + type(exc).__name__ + "). Install hosting dependencies, sign in with "
                     "`uv run --extra hosting modal token new`, and check billing access and configured App names. "
                     "Modal billing reports require a Team or Enterprise workspace.")
            self._save("status.json", {"error": error, "attempted_at": self.now().isoformat()})
            return False
        finally:
            self._lock.release()

    def _snapshot(self, workspace, start, end, now, identities, rows) -> dict:
        normalized = []
        app_ids = set(identities.values()) - {None}
        for row in rows:
            if row["object_id"] not in app_ids:
                continue
            cost = Decimal(str(row["cost"]))
            if not cost.is_finite() or cost < 0:
                raise ValueError("Invalid Modal billing amount")
            interval = row["interval_start"]
            if isinstance(interval, datetime):
                interval = interval.replace(tzinfo=interval.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
            normalized.append({"object_id": row["object_id"], "description": row["description"],
                "environment_name": row["environment_name"], "interval_start": interval,
                "cost_usd": str(cost), "cost_by_resource": {k: str(v) for k, v in row.get("cost_by_resource", {}).items()},
                "tags": row.get("tags", {})})
        return {"workspace": workspace, "start": start.isoformat(), "end": end.isoformat(),
            "updated_at": now.isoformat(), "identities": identities,
            "apps": {m.id: m.modal_app for m in self.models}, "rows": normalized}

    def view(self) -> dict:
        data = self._read("latest.json")
        status = self._read("status.json")
        identities = data.get("identities", {})
        rows = data.get("rows", [])
        models = []
        for model in self.models:
            object_id = identities.get(model.id) if data.get("apps", {}).get(model.id) == model.modal_app else None
            matched = [r for r in rows if r["object_id"] == object_id] if object_id else []
            # No report row can mean delayed billing or unused compute; don't invent $0.
            amount = sum((Decimal(r["cost_usd"]) for r in matched), Decimal(0)) if matched else None
            resources: dict[str, Decimal] = {}
            for row in matched:
                for resource, cost in row.get("cost_by_resource", {}).items():
                    resources[resource] = resources.get(resource, Decimal(0)) + Decimal(cost)
            changed = data and data.get("apps", {}).get(model.id) != model.modal_app
            error = ("Billing mapping changed; sync billing to resolve this App." if changed else
                     "Configured Modal App was not found in this workspace/environment." if data and not object_id else None)
            models.append({"model": model.id, "app": model.modal_app, "object_id": object_id,
                "cost_usd": float(amount) if amount is not None else None, "intervals": len(matched),
                "cost_by_resource": {k: float(v) for k, v in resources.items()},
                "error": error})
        # Shared App mappings must not double the workspace endpoint total.
        ids = {m["object_id"] for m in models} - {None}
        amounts = [Decimal(r["cost_usd"]) for r in rows if r["object_id"] in ids]
        return {"workspace": data.get("workspace"), "start": data.get("start"), "end": data.get("end"),
            "updated_at": data.get("updated_at"), "error": status.get("error"), "syncing": self._lock.locked(),
            "cost_usd": float(sum(amounts)) if amounts else None, "models": models}

    def trigger(self) -> None:
        threading.Thread(target=self.sync, name="rb-modal-billing-sync", daemon=True).start()

    def start(self):
        def run():
            while not self._stop.is_set():
                self.sync()
                self._stop.wait(300)
        self._thread = threading.Thread(target=run, name="rb-modal-billing", daemon=True)
        self._thread.start()
        return self

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
