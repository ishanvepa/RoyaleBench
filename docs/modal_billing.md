# Modal endpoint billing

The Overview dashboard's **Modal endpoint spend** table reads actual metered
charges from `modal.Workspace.from_context().billing.report()`. These are Modal's
reported charges before credits and invoice adjustments, not token-price estimates.
The report includes inference token charges, serving compute, network egress and
all traffic on each configured App. Expand **Resource breakdown** to inspect
Modal's resource categories, including cached/uncached input and output tokens.
App-level billing totals are shown separately from task API spend. Their inference
token portion overlaps the task costs below; the two totals must not be added.

## Task and job inference costs

For the four configured Modal model IDs, task API cost includes inference tokens
calculated from complete endpoint response usage. Job totals and the leaderboard
use those same task costs.

Rates were verified directly against `Workspace.billing.rates()` on November 15,
2026, and are pinned in `rb_evals/modal_inference.py`:

| Model | Uncached input / million | Cached input / million | Output / million |
| --- | ---: | ---: | ---: |
| Qwen3.8-2.4T-A95B | $2.00 | $0.25 | $6.00 |
| Inkling 2 Small | $0.30 | $0.03 | $1.00 |
| DeepSeek V4.1 Flash 1017 | $0.25 | $0.005 | $1.00 |
| Kimi K3.1 Pro | $2.00 | $0.20 | $10.00 |

Uncached input is prompt tokens minus cached tokens. Completion includes reasoning
and is charged once; these models have equal reasoning and completion rates.
Every response must report input, cached-input and output counts, and the unique
response count must match the harness API-call count. Missing or invalid usage
stays unknown. Only exact configured model IDs receive these rates.

Each task saves `inference_cost.json` next to its cached output, with exact decimal
amounts, resource breakdown, token counts, rate version/source, original rate
snapshot and trajectory SHA-256. Writes are atomic. Repeated reads and restarts
reuse the saved pricing; a changed trajectory invalidates the record. Verify and
update the pinned rates when Modal changes pricing; existing records retain their
original rates. These are usage-based inference charges before invoice adjustments,
not a claim that Modal returned a per-request dollar receipt.

Already-cached tasks are backfilled on read without downloads. Newly downloaded
finished tasks are recorded by the normal background cost worker. The task trace
API exposes `cost_source=modal_token_usage`, the exact dollar string and pricing
details; the task panel shows the exact inference amount. Incomplete tasks never
reuse a stale successful charge. CPU, memory, network and sandbox costs remain
outside task inference totals.

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
App names. All four mappings were resolved successfully in workspace `ishanvepa171`
during live verification on November 15, 2026.
The SDK resolves each App to its ID without creating resources. An App that
cannot be found is shown explicitly; other resolved Apps can still have costs.
For additional hosted models, add their `modal_app` and restart the dashboard.
Multiple models mapped to one App share that App's bill; the total counts it once.

## Persistence and refresh

The real server syncs at startup and every five minutes, including while browsers
are closed. **Sync billing** requests a background refresh. GET requests read
persisted files and never call Modal. Simulated mode does not query real billing.

The report covers the month containing the last completed UTC hour, ending at the
beginning of the current hour. Only the current partial hour is excluded. Recent
charges are provisional: Modal can post usage later; subsequent syncs replace the complete
queried window, so corrections update totals without adding duplicate charges.
Monthly queries are split into windows of at most seven days to respect Modal's
hourly-report range limit. A failed window leaves the previous complete snapshot intact.
Monthly snapshots are retained, but the UI displays only the latest queried month.
If a snapshot exists for the previous month, each sync also reconciles that month
through its final hour. All report windows are fetched before snapshots are
replaced. Months older than the previous month are retained without automatic
reconciliation.

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
zero costs under `ignore_errors` or `off` are unknown, not free inference. Complete
usage for a priced Modal preset is recorded as task inference cost instead.
Existing cached trajectories are parsed without another artifact download.

## Verification status

Automated tests cover idempotent refresh, corrected charges, exact persistence
across restart, error retention, shared-App deduplication, unknown versus zero,
month boundaries, the dashboard API and the frontend table. Local Qwen, Inkling
and DeepSeek pilot trajectories can be read without launching model calls.
Live verification on November 15, 2026 confirmed billing access in workspace
`ishanvepa171`, resolved all four serving Apps, and retrieved actual compute
charges for each. It also exposed Modal's seven-day hourly range limit; a
regression test now checks bounded, contiguous requests across a whole month.
The investigation found that the extra one-hour ingestion buffer excluded every
available endpoint charge. Removing that buffer recovered and persisted
`$0.06473104` across the four Apps in the report ending at
`2026-11-15T08:00:00Z`: Qwen `$0.04988958`, Inkling `$0.00166774`, DeepSeek
`$0.00124824`, and Kimi `$0.01192548`. Reloading the billing service from disk
returned identical totals without network access. The resource breakdown confirms
these charges include inference tokens, so the UI now labels them endpoint spend
rather than compute. Regression tests cover this completed-hour case, corrected
charges, previous-month finalization and failed reconciliation retaining data.

The task-cost backfill recorded six cached tasks across the four models, totaling
`$0.12151977` in inference charges across those jobs. Live dashboard API reads
confirmed their task/job costs and exact pricing provenance. DeepSeek's
`$0.00123413` task inference charge matches the token subtotal of its Modal billing
row exactly. Task pricing tests cover all four variants, saved-rate retention,
duplicate responses, missing/invalid usage, changed trajectories, and job totals
after reconstructing the cache without artifact downloads. A second SDK rate
lookup verified all pinned rates, including reasoning/completion equivalence.

References: [Modal billing](https://modal.com/docs/guide/billing),
[Workspace billing API](https://modal.com/docs/reference/modal.Workspace#billingreport),
[billing CLI](https://modal.com/docs/cli/latest/billing).
