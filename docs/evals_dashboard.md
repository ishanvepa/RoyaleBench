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

## Evals

| Page | What it does |
| --- | --- |
| Jobs | Every Valkyrie run, filterable by status, model and benchmark. Filters live in the URL. |
| New job | Pick a published benchmark and revision, run **all of it or selected tasks**, choose harness, model and API-key secret, set concurrency. A live review shows the task count, any problems, and the equivalent `valkyrie run start` command. Sandboxes are always Modal. |
| Job monitor | One run, updating as it goes: tasks by state, ETA, queue position, stop / resume / retry failed / change concurrency, and tabs for tasks, logs, errors and config. Task rows open the agent's trace. |
| Benchmarks | The folders under `benchmarks/`, marked draft, published or modified, with their published versions. **Publish** pushes the folder to Valkyrie as a new revision (nothing changes if the content is unchanged). |
| Benchmark and task pages | A benchmark's tasks with checks (missing tests, CRLF scripts, no timeout), and for each task its instruction, files and results across runs. |
| Leaderboard | Models by harness with solved, pass rate, score, agent failures, infrastructure errors, time and cost. Click any column to sort. |

One job is one Valkyrie run: one model on a whole benchmark or a subset. To compare models, start one job
per model. Valkyrie stays the source of truth; finished runs and downloaded costs are cached under
`runs/evals/` (git-ignored). Cost comes from the harness's own summary in each task's output (Claude Code
writes one) and does not include Modal's sandbox charges.

Settings (default harness, model presets, concurrency limits, the task count above which a job needs an
explicit confirmation) are in [`evals.toml`](../evals.toml). Benchmarks are authored as in
[task design](task_design.md): `benchmarks/<name>/<task-id>/` in Harbor format, plus an optional
`benchmark.toml` with a title, description and `kind` (`eval` or `smoke`). Do not add a `dataset.toml`:
Valkyrie treats it as a lock on the task list.

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
