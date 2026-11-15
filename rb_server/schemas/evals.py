"""Request and response models for /api/evals."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------- environment
class Identity(BaseModel):
    organization: str
    email: str | None = None
    name: str | None = None
    credential: str = "none"


class QueueSummary(BaseModel):
    waiting: int = 0
    building: int = 0
    in_progress: int = 0
    evaluating: int = 0


class ModelPresetOut(BaseModel):
    id: str
    secret_env: str
    family: str
    logo_url: str | None = None


class EvalsSettingsOut(BaseModel):
    benchmark: str
    provider: str
    default_agent: str
    default_concurrency: int
    max_concurrency: int
    confirm_over_tasks: int
    models: list[ModelPresetOut]


class EnvironmentOut(BaseModel):
    valkyrie_ok: bool
    valkyrie_error: str | None = None
    valkyrie_error_kind: str | None = None
    identity: Identity | None = None
    modal_configured: bool = False
    providers: dict[str, str] = {}
    secrets: list[str] = []
    agents: list[str] = []
    queue: QueueSummary | None = None
    read_only: bool = False
    fake: bool = False
    settings: EvalsSettingsOut


# ---------------------------------------------------------------------- jobs
class JobRow(BaseModel):
    id: str
    job: str
    status: str
    benchmark: str
    dataset: str
    model: str
    family: str
    logo_url: str | None = None
    harness: str
    done: int
    total: int
    progress: float
    score: float | None = None
    cost_usd: float | None = None
    cost_per_task: float | None = None
    cost_known: int = 0
    costs_pending: int = 0
    started_by: str
    started_at: datetime | None = None
    duration_s: float | None = None
    error: str = ""
    task_state_counts: dict[str, int] = {}


class JobList(BaseModel):
    jobs: list[JobRow]
    total: int
    datasets: list[str]
    models: list[str]
    me: str | None = None


class QueueInfo(BaseModel):
    waiting: int = 0
    active: int = 0
    position: int | None = None


class JobDetail(BaseModel):
    job: JobRow
    provider: str
    concurrency: int | None = None
    dataset_version: str
    task_ids: list[str] | None = None
    secrets: dict[str, str] = {}  # environment variable -> secret *name* (never a value)
    project: str | None = None
    eta_s: float | None = None
    queue: QueueInfo | None = None
    active: bool


class TaskRow(BaseModel):
    task: str
    status: str
    category: str = ""
    error: str = ""
    duration_s: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    reward: float | None = None
    solved: bool = False


class TaskList(BaseModel):
    tasks: list[TaskRow]
    counts: dict[str, int]


class TaskDetail(BaseModel):
    task: str
    status: str
    category: str = ""
    error: str = ""
    reward: float | None = None
    solved: bool = False
    rewards: dict[str, float] = {}
    verifier_output: str = ""
    agent_s: float | None = None
    sandbox_s: float | None = None
    build_s: float | None = None
    eval_s: float | None = None
    exit_reason: str | None = None


class TraceStep(BaseModel):
    kind: str
    title: str
    text: str
    time: str | None = None
    tool: str | None = None  # tool name, set on tool_use steps and on the tool_result that answers them


class TraceOut(BaseModel):
    available: bool
    final_message: str = ""
    steps: list[TraceStep] = []
    steps_total: int = 0
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None


class ReplayOut(BaseModel):
    available: bool
    html: str = ""
    partial: bool = False
    message: str = ""


class LogLine(BaseModel):
    timestamp: datetime
    task_id: str | None = None
    message: str


class LogsOut(BaseModel):
    lines: list[LogLine]


class ErrorsOut(BaseModel):
    run: str | None = None
    tasks: dict[str, str] = {}


class JobSpecIn(BaseModel):
    dataset: str
    revision: str = "latest"
    agent: str
    model: str
    secret_name: str
    concurrency: int = 1
    label: str
    task_ids: list[str] | None = None  # None = every task in the revision
    confirm: bool = False  # required when the job is larger than the configured threshold


class JobPreviewOut(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    task_count: int = 0
    needs_confirmation: bool = False
    cli_command: str | None = None
    secret_env: str | None = None
    resolved_revision: str | None = None
    dataset_ref: str | None = None
    known_tasks: list[str] = []


class JobStartOut(BaseModel):
    run_id: str
    task_count: int
    warning: str | None = None


class ConcurrencyIn(BaseModel):
    concurrency: int = Field(ge=1)


class ResumeIn(BaseModel):
    concurrency: int | None = Field(default=None, ge=1)  # None keeps the run's current concurrency


class ConcurrencyOut(BaseModel):
    concurrency: int


# ---------------------------------------------------------------------- benchmarks
class VersionOut(BaseModel):
    revision: int
    digest: str
    task_count: int
    tags: list[str]
    created_by: str | None = None
    created_at: datetime | None = None


class BenchmarkRow(BaseModel):
    name: str
    title: str
    description: str
    kind: str
    state: str  # draft | published | modified | remote only
    local: bool
    task_count: int
    versions: int
    latest_revision: int | None = None
    tags: list[str]
    runs: int
    best_score: float | None = None
    problems: int


class BenchmarkList(BaseModel):
    benchmarks: list[BenchmarkRow]
    valkyrie_error: str | None = None


class TaskInfo(BaseModel):
    id: str
    name: str = ""
    description: str = ""
    category: str = ""
    difficulty: str = ""
    agent_timeout_s: float | None = None
    verifier_timeout_s: float | None = None
    resources: dict[str, float] = {}
    sync: str  # in sync | modified | not published | published only
    local: bool
    problems: list[str] = []


class BenchmarkDetail(BaseModel):
    benchmark: BenchmarkRow
    dataset_ref: str
    folder: str | None = None
    versions: list[VersionOut]
    tasks: list[TaskInfo]
    errors: list[str] = []
    valkyrie_error: str | None = None


class FileInfo(BaseModel):
    path: str
    size: int


class TaskDetailOut(BaseModel):
    benchmark: str
    task: TaskInfo
    instruction: str
    config_toml: str
    files: list[FileInfo]
    dockerfile: str | None = None
    test_script: str | None = None
    solution_script: str | None = None


class TaskResultRow(BaseModel):
    run_id: str
    job: str
    model: str
    family: str
    logo_url: str | None = None
    harness: str
    revision: str
    reward: float | None = None
    solved: bool
    agent_s: float | None = None
    cost: float | None = None
    error: str = ""
    failure_category: str = ""
    started_at: datetime | None = None


class TaskModelSummary(BaseModel):
    model: str
    family: str
    logo_url: str | None = None
    harness: str
    attempts: int
    solved: int
    pass_rate: float | None = None


class TaskResultsOut(BaseModel):
    results: list[TaskResultRow]
    summary: list[TaskModelSummary]


class PublishIn(BaseModel):
    tags: list[str] = []
    allow_problems: bool = False  # publish even when the task lint reports problems


class PublishOut(BaseModel):
    version: VersionOut
    changed: bool  # False when the folder matched the latest published revision
    stored: list[str] = []
    created: list[str] = []
    warnings: list[str] = []
    left_out: dict[str, list[str]] = {}


# ---------------------------------------------------------------------- leaderboard
class LeaderboardRow(BaseModel):
    rank: int
    model: str
    family: str
    logo_url: str | None = None
    harness: str
    runs: int
    tasks_run: int
    solved: int
    pass_rate: float | None = None
    score: float | None = None
    agent_failures: int
    infra_errors: int
    avg_agent_s: float | None = None
    cost_usd: float | None = None
    cost_per_task: float | None = None
    cost_known: int
    last_run: datetime | None = None


class LeaderboardFilters(BaseModel):
    datasets: list[str]
    revisions: list[str]
    harnesses: list[str]


class LeaderboardOut(BaseModel):
    rows: list[LeaderboardRow]
    filters: LeaderboardFilters
    runs_considered: int
    tasks_considered: int
    costs_pending: int
    smoke_datasets: list[str]


class CostsStatus(BaseModel):
    state: str  # idle | running | done | error
    done: int = 0
    total: int = 0
    error: str | None = None
