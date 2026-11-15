import { createColumnHelper } from "@tanstack/react-table";
import { Link } from "react-router";
import { z } from "zod";
import { isActiveRun, type Environment, type JobRow, type LeaderboardRow } from "@/api/types";
import { FamilyLabel } from "@/components/domain/FamilyLabel";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { RelativeTime } from "@/components/domain/values";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { ALL, Select } from "@/components/ui/select";
import { stringParam, useSearchState } from "@/hooks/useSearchState";
import { familyLabel } from "@/lib/family";
import { DASH } from "@/lib/format";
import { useEnvironment } from "../api/environment";
import { ALL_JOBS, useJobs } from "../api/jobs";
import { ALL_RESULTS, useLeaderboard } from "../api/leaderboard";
import { providerOf, secretsForProvider } from "../jobs/defaults";

const searchSchema = z.object({ family: stringParam() });

/** One model: how it is set up, whether a key for it is stored in Valkyrie, and how its jobs have gone. */
interface ModelStats {
  model: string;
  family: string;
  logoUrl: string | null;
  provider: string;
  /** Listed in evals.toml. Models that only appear because a job used them are not. */
  configured: boolean;
  secretEnv: string;
  /** Stored Valkyrie secrets that look like this provider's key, or null when Valkyrie could not be asked. */
  secrets: string[] | null;
  jobs: number;
  running: number;
  /** Graded tasks and solved tasks in finished runs, or null while the leaderboard has not loaded. */
  tasksRun: number | null;
  solved: number | null;
  lastRun: string | null;
}

function emptyStats(model: string, family: string, logoUrl: string | null | undefined, configured: boolean, secretEnv: string, env: Environment): ModelStats {
  const provider = providerOf(model);
  return {
    model,
    family,
    logoUrl: logoUrl ?? null,
    provider,
    configured,
    secretEnv,
    secrets: env.valkyrie_ok ? secretsForProvider(env.secrets, provider) : null,
    jobs: 0,
    running: 0,
    tasksRun: null,
    solved: null,
    lastRun: null,
  };
}

/** The configured models plus any other model a job has used, with each one's totals. */
function buildRows(env: Environment, jobs: readonly JobRow[], board: readonly LeaderboardRow[] | undefined): ModelStats[] {
  const byModel = new Map<string, ModelStats>();
  for (const preset of env.settings.models) byModel.set(preset.id, emptyStats(preset.id, preset.family, preset.logo_url, true, preset.secret_env, env));

  for (const job of jobs) {
    if (!job.model) continue;
    const row = byModel.get(job.model) ?? emptyStats(job.model, job.family, job.logo_url, false, "", env);
    byModel.set(job.model, row);
    row.jobs += 1;
    if (isActiveRun(job.status)) row.running += 1;
    if (job.started_at && (!row.lastRun || Date.parse(job.started_at) > Date.parse(row.lastRun))) row.lastRun = job.started_at;
  }

  if (board) {
    for (const row of byModel.values()) {
      const mine = board.filter((b) => b.model === row.model);
      row.tasksRun = mine.reduce((n, b) => n + b.tasks_run, 0);
      row.solved = mine.reduce((n, b) => n + b.solved, 0);
    }
  }
  return [...byModel.values()];
}

const col = createColumnHelper<ModelStats>();
const head = (label: string, explanation: string) => () => <span title={explanation}>{label}</span>;
const numeric = { align: "right" as const };

/** A count that is not known yet (null) shows a dash. */
const count = (value: number | null) => (value === null ? <span className="text-muted">{DASH}</span> : value);

const COLUMNS = [
  col.accessor("model", { header: "Model", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logoUrl} /> }),
  col.accessor((r) => familyLabel(r.family), { id: "family", header: "Family", cell: (c) => <FamilyLabel family={c.row.original.family} logoUrl={c.row.original.logoUrl} /> }),
  col.accessor("provider", { header: "Provider", cell: (c) => <span className="text-subtle">{c.getValue() || DASH}</span> }),
  col.accessor("configured", {
    header: head("In evals.toml", "Models listed in evals.toml show up in the New job form. The others appear here because a job used them."),
    cell: (c) => (c.getValue() ? "yes" : <span className="text-muted">no</span>),
  }),
  col.accessor("secretEnv", { header: head("Key variable", "The environment variable the harness reads this model's API key from"), cell: (c) => <code className="font-mono text-xs">{c.getValue() || DASH}</code> }),
  col.accessor((r) => (r.secrets === null ? 2 : r.secrets.length > 0 ? 1 : 0), {
    id: "key",
    header: head("Key secret", "Whether a stored Valkyrie secret mentions this model's provider. It does not check that the key works."),
    cell: (c) => {
      const { secrets, provider } = c.row.original;
      if (secrets === null) return <span className="text-muted">{DASH}</span>;
      if (secrets.length === 0) return <Badge tone="danger">no {provider || "model"} secret</Badge>;
      return (
        <span title={secrets.join(", ")}>
          <Badge tone="success">{secrets.length === 1 ? "found" : `${secrets.length} found`}</Badge>
        </span>
      );
    },
  }),
  col.accessor("jobs", {
    header: head("Jobs", "Jobs that ran this model, in any state"),
    meta: numeric,
    sortDescFirst: true,
    cell: (c) => {
      const { jobs, running, model } = c.row.original;
      if (jobs === 0) return <span className="text-muted">0</span>;
      return (
        <>
          <Link to={`/evals/jobs?model=${encodeURIComponent(model)}`} className="underline-offset-4 hover:underline" aria-label={`${jobs} jobs for ${model}`}>
            {jobs}
          </Link>
          {running > 0 ? <span className="text-xs text-muted"> · {running} running</span> : null}
        </>
      );
    },
  }),
  col.accessor((r) => r.tasksRun ?? undefined, { id: "tasksRun", header: head("Tasks run", "Tasks graded across this model's finished runs, smoke tests included"), meta: numeric, sortDescFirst: true, sortUndefined: "last", cell: (c) => count(c.row.original.tasksRun) }),
  col.accessor((r) => r.solved ?? undefined, { id: "solved", header: head("Solved", "Tasks that earned full reward"), meta: numeric, sortDescFirst: true, sortUndefined: "last", cell: (c) => count(c.row.original.solved) }),
  col.accessor((r) => (r.lastRun ? Date.parse(r.lastRun) : undefined), {
    id: "lastRun",
    header: "Last run",
    sortDescFirst: true,
    sortUndefined: "last",
    cell: (c) => <RelativeTime value={c.row.original.lastRun} />,
  }),
];

export function Component() {
  const [{ family }, setState] = useSearchState(searchSchema);
  const environment = useEnvironment();
  const jobs = useJobs(ALL_JOBS);
  const results = useLeaderboard(ALL_RESULTS);

  return (
    <div>
      <PageHeader
        title="Models"
        description="The models you can run jobs with: those in evals.toml plus any a job has used, whether a key for them is stored in Valkyrie, and how each has done."
      />
      <QueryBoundary query={environment} errorTitle="Couldn't load the models">
        {(env) => (
          <QueryBoundary query={jobs} errorTitle="Couldn't load the models">
            {(jobList) => {
              const rows = buildRows(env, jobList.jobs, results.data?.rows);
              const families = [...new Set(rows.map((r) => r.family))].sort();
              const familyLogo = (f: string) => rows.find((r) => r.family === f)?.logoUrl;
              const shown = family ? rows.filter((r) => r.family === family) : rows;
              return (
                <div className="space-y-4">
                  <div className="w-60">
                    <Select
                      aria-label="Model family"
                      value={family || ALL}
                      onValueChange={(v) => setState({ family: v === ALL ? "" : v })}
                      options={[{ value: ALL, label: "All families" }, ...families.map((f) => ({ value: f, label: <FamilyLabel family={f} logoUrl={familyLogo(f)} /> }))]}
                    />
                  </div>
                  <DataTable caption="Models" columns={COLUMNS} data={shown} getRowId={(m) => m.model} initialSorting={[{ id: "model", desc: false }]} empty="No models in the configuration." />
                  <p className="text-xs text-muted">
                    From evals.toml ({env.settings.models.length} configured) and the {jobList.total} jobs on Valkyrie. API keys are stored as Valkyrie secrets shared across the organization, so “found” only means a
                    secret that mentions the provider exists. “Tasks run” and “solved” pool every finished run, smoke tests included.
                  </p>
                </div>
              );
            }}
          </QueryBoundary>
        )}
      </QueryBoundary>
    </div>
  );
}
