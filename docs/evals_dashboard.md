# Evals dashboard

A web app for running and reading RoyaleBench evaluations. The **Evals** area (the default page) drives
Valkyrie for evaluation and Modal for sandbox compute. The **Legacy** area is the original arena: models
playing Clash Royale against each other locally.

```
Browser (React app in web/)  →  FastAPI server (rb_server/)  →  rb_evals/  Valkyrie SDK, benchmarks/, results cache
                                                             →  cr_arena/  arena database, game engine
```

## Run it

```bash
cd web && npm install && npm run build      # once, and after changing the web app
uv run python -m rb_server                  # http://127.0.0.1:8000  (one process serves the API and the built app)
```

Development, with hot reload for both sides:

```bash
uv run python -m rb_server --reload         # API on :8000
cd web && npm run dev                       # app on http://127.0.0.1:5173, proxying /api to :8000
```

Try it without credentials or spending anything: `uv run python -m rb_server --fake` starts a simulated
Valkyrie with seeded runs. Jobs you start in this mode walk through the real states on a timer.

For real runs you need what [the smoke test](valkyrie_smoke.md) sets up: `valkyrie login`, Modal connected
as the sandbox provider, and a Valkyrie secret holding the model's API key (such as `anthropic-api-key-<you>`).
The page tells you which of these is missing.

For the Modal-hosted Qwen endpoint, follow [Qwen on Modal](qwen_modal.md).
Select the existing `mini_swe_agent`, the Qwen model preset and secret
`modal-qwen-api-key`; use dataset revision `@3`, which allows the endpoint hostname.
The preset adds the endpoint URL's `OPENAI_API_BASE` secret mapping and the
standard harness options to both dashboard launches and their preview commands.
The **API key secret** dropdown includes `modal-qwen-api-key`, the shared Modal
proxy key used by the configured Modal models. Selecting Qwen, Inkling, DeepSeek
or Kimi automatically selects this key, including after a manual key selection.
You can choose another key after selecting the model. If the shared key is absent,
the field stays empty so you can select a credential explicitly.
Modal sandbox credentials and Modal base-URL secrets remain hidden from this dropdown.

For [Inkling on Modal](inkling_modal.md), select `mini_swe_agent`, model
`openai/inkling-2-small`, existing secret `modal-qwen-api-key` and dataset revision
`@4`. Its preset injects `modal-inkling-base-url` as `OPENAI_API_BASE` and uses
the same stock harness options. Credential reuse and the model ID were accepted
by the endpoint in the live pilot.

For [DeepSeek on Modal](deepseek_modal.md), select `mini_swe_agent`, model
`openai/deepseek-v4.1-flash-1017`, existing secret `modal-qwen-api-key` and dataset
revision `@5`. Its preset supplies `modal-deepseek-base-url` as `OPENAI_API_BASE`
and the same stock harness options. Restart the dashboard after preset changes.

For [Kimi on Modal](kimi_modal.md), select `mini_swe_agent`, model
`openai/kimi-k3.1-pro`, existing secret `modal-qwen-api-key` and dataset revision
`@6`. The preset injects `modal-kimi-base-url` as `OPENAI_API_BASE`, applies the
same stock harness options, and identifies serving app `ep-kimi-k3-1-pro` for
the dashboard's Modal billing lookup.

## Evals

The Overview also shows [actual Modal endpoint spend](modal_billing.md)
for configured hosted models, including Qwen, Inkling, DeepSeek and Kimi. This separate
table uses the workspace billing API and persists metered charges across restarts;
it includes inference tokens, serving compute and all traffic to each App, before invoice
credits/discounts, with an expandable resource breakdown. It includes the latest
completed UTC hour and reconciles late corrections, including the previous month
when a snapshot exists. It refreshes every five minutes and displays the queried UTC
window, last successful sync, and billing-access errors. Run the server with
`uv run --extra hosting python -m rb_server` in an authenticated Modal environment.
Workspace billing access is separate from the Valkyrie sandbox provider connection.

| Page | What it does |
| --- | --- |
| Jobs | Every Valkyrie run, filterable by status, model and benchmark, with sortable API cost and average cost per task for each run. Fetch missing costs for the visible runs here. Filters live in the URL. |
| New job | Pick a published benchmark and revision, run **all of it or selected tasks**, choose harness, model and API-key secret, set concurrency. A live review shows the task count, any problems, and the equivalent `valkyrie run start` command. Sandboxes are always Modal. |
| Job monitor | One run, updating as it goes: tasks by state, ETA, queue position, API cost and average cost per task, stop / resume / retry failed / change concurrency, and tabs for tasks, logs, errors and config. Fetch missing costs for this run here. Task rows show difficulty badges (easy green, medium amber, hard red) from current local benchmark metadata, with a dash when unavailable; rows open details with **Watch replay**, **View resolution** when the task exists locally, and the agent's trace. |
| Benchmarks | The folders under `benchmarks/`, marked draft, published or modified, with their published versions. **Publish** pushes the folder to Valkyrie as a new revision (nothing changes if the content is unchanged). |
| Benchmark and task pages | A benchmark's tasks with checks (missing tests, CRLF scripts, no timeout), difficulty badges (easy green, medium amber, hard red), and for each task its instruction, files and results across runs. The task header offers **View resolution** for a validated reference; each result offers **Watch replay** alongside its agent trace. |
| Leaderboard | Models by harness with solved, pass rate, score, agent failures, infrastructure errors, time and cost. Click any column to sort. |
| Overview | Totals over every job (jobs and how many are running, tasks finished, tasks solved, estimated API spend) above the ten most recent jobs. Solved and spend come from the leaderboard's finished runs, smoke tests included. |
| Models | The models in `evals.toml` plus any a job has used, with their provider, key variable, whether a stored Valkyrie secret mentions the provider (it does not test the key), job count, tasks run and solved, and last run. Filter by family; the job count links to the Jobs page filtered by that model. |

Model labels use family logos, including Qwen, Inkling (Thinking Machines), DeepSeek, and Kimi. The New job model dropdown shows these logos beside each model and in the selected value. Family detection checks the model name before the provider prefix, so OpenAI-compatible Modal endpoints retain the correct family logo. Kimi and Moonshot model names share the Kimi logo.

One job is one Valkyrie run: one model on a whole benchmark or a subset. To compare models, start one job
per model. Valkyrie stays the source of truth; finished runs and downloaded costs are cached under
`runs/evals/` (git-ignored). Cost comes from the harness's own summary in each task's output (Claude Code
writes one), or from complete Modal endpoint token usage at verified, pinned rates.
Task and job inference costs exclude infrastructure charges. The Modal endpoint
billing table includes the same inference charges, so its total must not be added
to task/job API spend. See [inference pricing and persistence](modal_billing.md#task-and-job-inference-costs).

Run cost metrics are available for **finished runs** and share the leaderboard's task-output cache.
The real dashboard server automatically fetches missing cost data **when a job finishes completely**,
checking run status every **10 seconds**, even when no browser is open. This includes smoke tests and
already-finished runs found at startup. Cached outputs are reused,
automatic and manual downloads cannot overlap, and failed downloads are retried on the next check.
This runs while the server is running; simulated Valkyrie mode keeps manual downloads for predictable demos.
Open pages check download status and pending run costs every 30 seconds, polling faster during a download.
The Jobs and Job monitor pages offer **Fetch cost data**, show background download progress, and refresh
the figures when it completes. The Overview's recent jobs also show each run's API cost. Unknown cost is
shown as a dash; a reported zero is `$0` unless mini-SWE-agent used an unknown-price
fallback or disabled cost tracking. Its token usage is recovered from `trajectory.json`,
including for previously cached tasks. Complete usage for the four configured Modal
models produces a persisted `inference_cost.json` with exact decimal costs, the
original rate snapshot and trajectory hash; incomplete usage stays unknown.
An asterisk marks a partial total, with task coverage shown on
hover and on the monitor. Cost per task averages only tasks with known costs. Run totals include all tasks
with reported costs, including infrastructure failures; the leaderboard excludes infrastructure failures
from its model-scoring pool and associated cost totals. Failed, stopped, and active runs have no run-level
cost metrics yet. Downloading costs does not launch evaluations.

Each job's **Tasks** tab also shows a sortable **API cost** column and the selected task's cost
in its detail panel. These are the individual harness-reported or Modal token costs from the same cache as the run
total, available for finished runs. The table refreshes as cost data is downloaded; zero is shown as
`$0` and unknown costs as a dash. These figures exclude sandbox and endpoint infrastructure charges.
The task trace shows the exact Modal inference dollar amount and its pricing source.

To watch a task, select its row in a job's **Tasks** tab, then **Watch replay**. The same button is on
each row of a task definition's **Results** tab. Playback opens in a wide dialog with play/pause,
frame stepping, a timeline, speed selection and side switching. The first opening downloads
`<task>/artifacts/royale.tar.gz` and renders `royale/replay.msgpack` with the shared battle graphics.
This uses the current carried referee artifact format; tasks without it show an explanation.
Recorded frames show the actual attempt, which can end before the independently graded continuation.
Stopped or failed tasks can expose a **Partial replay**. Active tasks become watchable after finishing
or stopping. Finished-run replay files are cached separately from agent traces; stopped/failed runs are
fetched again on opening so a retry or resume does not reuse an earlier attempt. Missing files and
transfer failures can be retried. Playback never starts a model or sandbox. Fake mode's `arena-lite`
tasks show explicitly labelled sample gameplay; its smoke tasks have no replay.

On a local benchmark task page, **View resolution** plays the reference solution in the same
controls as a model replay. The button loads only when opened and reads a saved
`runs/<benchmark>/docker*/<task>/replay.msgpack`; it never runs a solution, model or sandbox.
The server requires passing Docker validation with matching task configuration and packaged
referee protocol hashes. This matters when older validation directories coexist with newer
dataset revisions, as with v3's `docker-revision2`. If no matching validated replay exists,
the dialog explains that it is unavailable. A run's task panel shows the resolution for the
current local task version, which may differ from an older run revision. Reference gameplay
is a local dashboard view; the solution remains outside the agent sandbox.

**RoyaleBench v3** is the default benchmark for new jobs (`default_dataset` in `evals.toml`). It
uses coordinate actions across all 11 released scenarios. Explicit benchmark links override the
default, and an unpublished/unavailable default falls back to an available published benchmark.
See the [v3 guide](royalebench_v3.md) for validation and launch commands.

The historical **RoyaleBench coordinates pilot** is discovered separately from **RoyaleBench v1**. It uses
three matching positions with direct coordinate actions; see the [protocol guide](coordinate_harness.md).
The guide records its published revision and small Sonnet 4.6 comparison; local reference
validation remains distinct from model results.

New real runs are enrolled in [data collection](data_collection.md). A server-side worker archives
their raw artifacts, normalizes telemetry, exports analysis tables, and verifies a durable copy outside
the dashboard cache. The standalone collector works when this server is closed. Existing runs are not backfilled.

Settings (default harness, model presets, concurrency limits, the task count above which a job needs an
explicit confirmation) are in [`evals.toml`](../evals.toml). Benchmarks are authored as in
[task design](task_design.md): `benchmarks/<name>/<task-id>/` in Harbor format, plus an optional
`benchmark.toml` with a title, description and `kind` (`eval` or `smoke`). Do not add a `dataset.toml`:
Valkyrie treats it as a lock on the task list.

The current maximum concurrency is 50 tasks per run, for both new jobs and active runs. Change
`[valkyrie].max_concurrency` in `evals.toml` to adjust the dashboard limit.

## Codex launch troubleshooting

On November 14, 2026, the installed `codex-v1.0.0` contract restricted `defaults.model.choices`
to six older, unprefixed model IDs. Starting `openai/gpt-6.1-sol` returned HTTP 500 before a run
was created, both from this dashboard and the Valkyrie CLI. The API-key secret mapping was correct.

The team's installed harness was repaired by downloading it, applying the repository's
[repair script](../tools/repair_codex_harness.py), and pushing the same harness name again:

```powershell
valkyrie agent download codex-v1.0.0 -o runs/evals/harness-inspect
uv run python tools/repair_codex_harness.py runs/evals/harness-inspect/codex-v1.0.0
valkyrie agent push runs/evals/harness-inspect/codex-v1.0.0
```

Keep shell scripts in LF format: downloaded harnesses installed from Windows can contain CRLF
despite this repository's `.gitattributes` (downloaded files are outside Git's checkout rules).
Run `4832a0e1-58b8-4205-abda-dbeb941ff415` failed before installing dependencies with
`setup.sh: line 2: $'\r': command not found` and `set: pipefail\r: invalid option name`.
Converting `setup.sh` as above fixes that shell parsing error. The uploaded archive was read back
and its `setup.sh` verified to contain no carriage returns (SHA-256
`c11383359efccd72dbb6fa5880c36c6fa927a1812f62206623b85d2f78cfe5a6`).

The LF-only verification run `645774c9-cc67-4bd7-852d-d32a319e1fc1` completed dependency installation
and started Codex, then failed with HTTP 401, `Missing bearer or basic authentication in header`.
The repair script also forwards the injected `OPENAI_API_KEY` to the Codex subprocess as
`CODEX_API_KEY`, the environment override documented for
[`codex exec`](https://learn.chatgpt.com/docs/non-interactive-mode). This avoids relying on the
installer's home-directory credential file being available during agent execution. The existing
Valkyrie secret mapping remains `OPENAI_API_KEY` to the user's named secret.

Its `collect_outputs.py` already strips the
`openai/` prefix before passing the model to Codex. Removing the contract allowlist lets the model
provider validate availability; it does not establish that every model in `evals.toml` is supported.
Reinstalling the upstream harness may restore the old restriction.

After this change, Valkyrie accepted one task from `royalebench/royalebench-v1@1` with
`openai/gpt-6.1-sol`, `OPENAI_API_KEY` mapped to `openai-api-key-ishan`, Modal, and concurrency 1.
Run ID: `3247f17f-ba3a-452e-81ba-f1fab57f5cc1` (label `royalebench-codex-launch-check-fixed`).
That initial check subsequently failed with the CRLF shell error described above; launch acceptance
alone does not verify installation, API authentication, task completion, or scoring.

With all three repairs applied, run `667585dd-658f-4879-b6b3-fd37b09a5715`
(`royalebench-codex-auth-check`) successfully installed dependencies, authenticated, and played
`01-immediate-lethal` on the same dataset revision, model, secret, provider, and concurrency.
The model ran `cr act 5` (Fireball on the enemy's left princess tower); the separate verifier
recorded `reward: 1.0`, `integrity: 1.0`, and `objective_met: 1.0`. This verifies the repaired
execution path for one task, not the complete eleven-task benchmark.

## Legacy

Leaderboard, Play (you against a bot or model, turn by turn, or two models in a battle), Decks, Overview,
job and match pages with replays, and Models. They read the arena database: `DATABASE_URL` from `.env`
(the shared Postgres), else `runs/arena.db`. The real-time game for the phone-play link is separate and
unchanged: `uv run python -m cr_arena.live` (see [phone play](phone_play.md)).

## Safety

- The server listens on `127.0.0.1` and rejects other `Host` headers. Starting, stopping, publishing and
  battles spend credits, so do not expose it with `--host 0.0.0.0` on a network you do not trust.
- Anything that changes state needs the `x-rb-client: web` header, which a page on another site cannot send.
- `ROYALEBENCH_EVALS_READONLY=1` turns every state-changing endpoint into a 403 and disables the buttons.
  Use it when sharing a read-only view.
- Replays render in a sandboxed frame, so the replay viewer's script cannot reach the app.

## Environment variables

| Variable | Meaning |
| --- | --- |
| `ROYALEBENCH_HOST`, `ROYALEBENCH_PORT` | Where to listen (default `127.0.0.1:8000`). |
| `ROYALEBENCH_FAKE_VALKYRIE=1` | Same as `--fake`. |
| `ROYALEBENCH_EVALS_READONLY=1` | Read-only mode. |
| `ROYALEBENCH_EVALS_CONFIG`, `ROYALEBENCH_BENCHMARKS_DIR`, `ROYALEBENCH_CACHE_DIR` | Override `evals.toml`, `benchmarks/` and `runs/evals/`. |
| `ROYALEBENCH_ARENA_DB` | A SQLite path or Postgres URL for the Legacy pages (default: `DATABASE_URL`, else `runs/arena.db`). |
| `ROYALEBENCH_STATIC_DIR` | Serve a build other than `web/dist`. |

## Changing the API or the app

The API's OpenAPI description is committed as `rb_server/openapi.json`, and the web app's TypeScript types
are generated from it, so the two cannot drift apart silently. After changing a route or schema:

```bash
uv run python -m rb_server.export_openapi
cd web && npm run gen:api
```

Checks:

```bash
uv run python -m unittest discover -s tests   # API, evals backend, arena logic (no network, no credentials)
cd web && npm run check                       # generated types are current, typecheck, lint, unit tests, build
cd web && npm run e2e                         # browser tests against the simulated Valkyrie and a seeded arena (build first)
```
