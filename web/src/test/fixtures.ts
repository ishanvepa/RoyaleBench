/** Typed API fixtures for tests. Because they use the generated types, a changed API breaks them at compile time. */
import type {
  BenchmarkDetail,
  BenchmarkList,
  BenchmarkRow,
  Environment,
  JobDetail,
  JobList,
  JobPreview,
  JobRow,
  Leaderboard,
  LeaderboardRow,
  TaskList,
} from "@/api/types";

export const environment = (overrides: Partial<Environment> = {}): Environment => ({
  valkyrie_ok: true,
  valkyrie_error: null,
  valkyrie_error_kind: null,
  identity: { organization: "org", email: "ishan@example.com", name: "Ishan", credential: "login" },
  modal_configured: true,
  providers: { modal: "modal-credentials" },
  secrets: ["anthropic-api-key-ben", "anthropic-api-key-ishan", "modal-credentials"],
  agents: ["claude_code-v1.0.0", "codex-v1.0.0"],
  queue: { waiting: 0, building: 0, in_progress: 0, evaluating: 0 },
  read_only: false,
  fake: false,
  settings: {
    benchmark: "royalebench",
    provider: "modal",
    default_agent: "claude_code-v1.0.0",
    default_concurrency: 1,
    max_concurrency: 10,
    confirm_over_tasks: 5,
    models: [{ id: "anthropic/claude-sonnet-4-6", secret_env: "ANTHROPIC_API_KEY", family: "claude", logo_url: "/api/assets/logos/claude" }],
  },
  ...overrides,
});

export const jobRow = (overrides: Partial<JobRow> = {}): JobRow => ({
  cost_known: 0,
  costs_pending: 0,
  id: "run-1",
  job: "smoke-run",
  status: "FINISHED",
  benchmark: "royalebench/smoke",
  dataset: "smoke",
  model: "anthropic/claude-sonnet-4-6",
  family: "claude",
  logo_url: "/api/assets/logos/claude",
  harness: "claude_code-v1.0.0",
  done: 1,
  total: 1,
  progress: 1,
  score: 100,
  started_by: "ben@example.com",
  started_at: "2026-11-14T10:00:00Z",
  duration_s: 45,
  error: "",
  task_state_counts: { FINISHED: 1 },
  ...overrides,
});

export const jobList = (jobs: JobRow[] = [jobRow()]): JobList => ({
  jobs,
  total: jobs.length,
  datasets: [...new Set(jobs.map((j) => j.dataset))],
  models: [...new Set(jobs.map((j) => j.model))],
  me: "ishan@example.com",
});

export const jobDetail = (overrides: Partial<JobDetail> = {}, job: Partial<JobRow> = {}): JobDetail => ({
  job: jobRow(job),
  provider: "modal",
  concurrency: 1,
  dataset_version: "royalebench/smoke@1",
  task_ids: null,
  secrets: { ANTHROPIC_API_KEY: "anthropic-api-key-ishan" },
  project: "default",
  eta_s: null,
  queue: null,
  active: false,
  ...overrides,
});

export const taskList = (): TaskList => ({
  tasks: [
    { task: "elixir-check", status: "FINISHED", category: "", error: "", duration_s: 45, started_at: "2026-11-14T10:00:00Z", finished_at: "2026-11-14T10:00:45Z", reward: 1, solved: true },
  ],
  counts: { FINISHED: 1 },
});

export const preview = (overrides: Partial<JobPreview> = {}): JobPreview => ({
  valid: true,
  errors: [],
  warnings: [],
  task_count: 3,
  needs_confirmation: false,
  cli_command: "valkyrie run start --agent claude_code-v1.0.0 --provider modal",
  secret_env: "ANTHROPIC_API_KEY",
  resolved_revision: "1",
  dataset_ref: "royalebench/alpha@1",
  known_tasks: ["t1", "t2", "t3"],
  ...overrides,
});

export const benchmarkRow = (overrides: Partial<BenchmarkRow> = {}): BenchmarkRow => ({
  name: "alpha",
  title: "Alpha",
  description: "",
  kind: "eval",
  state: "published",
  local: true,
  task_count: 3,
  versions: 1,
  latest_revision: 1,
  tags: ["latest", "v1"],
  runs: 2,
  best_score: 80,
  problems: 0,
  ...overrides,
});

export const benchmarkList = (benchmarks: BenchmarkRow[] = [benchmarkRow()]): BenchmarkList => ({ benchmarks, valkyrie_error: null });

export const benchmarkDetail = (row: Partial<BenchmarkRow> = {}): BenchmarkDetail => ({
  benchmark: benchmarkRow(row),
  dataset_ref: "royalebench/alpha",
  folder: "benchmarks/alpha",
  versions: [{ revision: 1, digest: "sha256:abc123abc123", task_count: 3, tags: ["latest", "v1"], created_by: "ben@example.com", created_at: "2026-11-13T10:00:00Z" }],
  tasks: ["t1", "t2", "t3"].map((id) => ({ id, name: "", description: "", category: "lanes", difficulty: "easy", agent_timeout_s: 60, verifier_timeout_s: 10, resources: {}, sync: "in sync", local: true, problems: [] })),
  errors: [],
  valkyrie_error: null,
});

export const leaderboardRow = (overrides: Partial<LeaderboardRow> = {}): LeaderboardRow => ({
  rank: 1,
  model: "anthropic/claude-opus-5-5",
  family: "claude",
  logo_url: "/api/assets/logos/claude",
  harness: "claude_code-v1.0.0",
  runs: 1,
  tasks_run: 4,
  solved: 3,
  pass_rate: 0.75,
  score: 75,
  agent_failures: 0,
  infra_errors: 0,
  avg_agent_s: 4.6,
  cost_usd: 0.4,
  cost_per_task: 0.1,
  cost_known: 4,
  last_run: "2026-11-14T10:00:00Z",
  ...overrides,
});

export const leaderboard = (rows: LeaderboardRow[], overrides: Partial<Leaderboard> = {}): Leaderboard => ({
  rows,
  filters: { datasets: ["arena-lite"], revisions: ["1"], harnesses: ["claude_code-v1.0.0"] },
  runs_considered: rows.length,
  tasks_considered: rows.reduce((n, r) => n + r.tasks_run, 0),
  costs_pending: 0,
  smoke_datasets: ["smoke"],
  ...overrides,
});
