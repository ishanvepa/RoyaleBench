# Modal endpoint billing

The Overview dashboard's **Modal endpoint compute** table reads actual metered
charges from `modal.Workspace.from_context().billing.report()`. These are Modal's
reported charges before credits and invoice adjustments, not token-price estimates.
The report includes idle serving compute and all traffic on each configured App.
Costs are kept separate from harness API spend and are never allocated to individual
runs or tasks, since several runs can use the same endpoint concurrently.

## Connection

Run the dashboard in the environment that already has your Modal login:

```powershell
uv run --extra hosting python -m rb_server
```

The SDK uses the active Modal profile (`~/.modal.toml`, or `MODAL_CONFIG_PATH`),
or `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` in the server environment. A Valkyrie
provider connection or a model's `wk-… .ws-…` proxy credential does not supply
workspace billing access. If there is no existing login, authenticate locally
with `uv run --extra hosting modal token new`; never put token values in the
repository or chat. Modal's programmatic billing reports require a Team or
Enterprise workspace and suitable account permissions.

Each Modal model preset in `evals.toml` has `modal_app`, the exact serving App
name or `ap-` ID. Qwen, Inkling, DeepSeek and Kimi are configured from their endpoint
App names; these mappings still require live verification in the owning workspace.
The SDK resolves each App to its ID without creating resources. An App that
cannot be found is shown explicitly; other resolved Apps can still have costs.
For additional hosted models, add their `modal_app` and restart the dashboard.
Multiple models mapped to one App share that App's bill; the total counts it once.

## Persistence and refresh

The real server syncs at startup and every five minutes, including while browsers
are closed. **Sync billing** requests a background refresh. GET requests read
persisted files and never call Modal. Simulated mode does not query real billing.

The report covers the month containing the last included UTC hour, ending at the
beginning of the previous hour. This one-hour ingestion buffer avoids the current
partial hour. Modal can post usage later; subsequent syncs replace the complete
queried window, so corrections update totals without adding duplicate charges.
Monthly queries are split into windows of at most seven days to respect Modal's
hourly-report range limit. A failed window leaves the previous complete snapshot intact.
Monthly snapshots are retained, but the UI displays only the latest queried month.
Historical months are not automatically reconciled after the window rolls over.

Raw billing rows, resource breakdowns, Decimal amounts as strings, resolved App
IDs, workspace, interval boundaries and retrieval time are saved atomically under
`runs/evals/modal-billing/`. Set `ROYALEBENCH_BILLING_DIR` to a persistent directory
outside the results cache if that cache is routinely cleared. Restarting the
server preserves the records. A sync error is saved separately and leaves the
last successful report visible. No matching billing row is unknown (a dash);
an explicit reported zero is `$0`.

Mini-SWE-agent model usage is also read from its cached `trajectory.json`:
input, output, cached and reasoning tokens plus API-call counts are available
in task details. Reasoning is already included in completion tokens. Fallback
zero costs under `ignore_errors` or `off` are unknown, not free inference.
Existing cached trajectories are parsed without another artifact download.

## Verification status

Automated tests cover idempotent refresh, corrected charges, exact persistence
across restart, error retention, shared-App deduplication, unknown versus zero,
month boundaries, the dashboard API and the frontend table. Local Qwen, Inkling
and DeepSeek pilot trajectories can be read without launching model calls.
Live billing access and App resolution remain unverified until the dashboard
can use a login in the owning Modal workspace.

References: [Modal billing](https://modal.com/docs/guide/billing),
[Workspace billing API](https://modal.com/docs/reference/modal.Workspace#billingreport),
[billing CLI](https://modal.com/docs/cli/latest/billing).
