import { createColumnHelper } from "@tanstack/react-table";
import { Link } from "react-router";
import type { JobRow } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { ProgressCell } from "@/components/domain/SegmentedProgress";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration, Money, RelativeTime, Score } from "@/components/domain/values";
import { harnessName } from "@/lib/format";
import { RunCost } from "./JobCosts";

const col = createColumnHelper<JobRow>();

/** Sort order for the status column: what is happening now first, then what went wrong, then what is done. */
const STATUS_RANK: Record<string, number> = { IN_PROGRESS: 0, STOPPING: 1, ERROR: 2, STOPPED: 3, FINISHED: 4 };

/**
 * The columns a table of jobs is built from. The Jobs page shows all of them; the Overview shows a shorter set.
 * Defined once at module level, so the references are stable and tables never re-create their columns.
 */
export const jobColumns = {
  status: col.accessor((r) => STATUS_RANK[r.status] ?? 9, {
    id: "status",
    header: "Status",
    cell: (c) => <StatusPill kind="run" status={c.row.original.status} />,
  }),
  job: col.accessor("job", {
    header: "Job",
    cell: (c) => (
      <Link to={`/evals/jobs/${c.row.original.id}`} className="font-medium underline-offset-4 hover:underline">
        {c.getValue()}
      </Link>
    ),
  }),
  benchmark: col.accessor("dataset", {
    header: "Benchmark",
    cell: (c) => (
      <Link to={`/evals/benchmarks/${c.getValue()}`} className="text-subtle underline-offset-4 hover:text-ink hover:underline">
        {c.getValue() || "–"}
      </Link>
    ),
  }),
  model: col.accessor("model", { header: "Model", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
  harness: col.accessor((r) => harnessName(r.harness), { id: "harness", header: "Harness", cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
  progress: col.accessor("progress", {
    header: "Progress",
    cell: (c) => <ProgressCell done={c.row.original.done} total={c.row.original.total} counts={c.row.original.task_state_counts} />,
  }),
  score: col.accessor((r) => r.score ?? undefined, {
    id: "score",
    header: "Score",
    sortDescFirst: true,
    sortUndefined: "last",
    meta: { align: "right" },
    cell: (c) => <Score value={c.row.original.score} />,
  }),
  startedBy: col.accessor((r) => r.started_by.split("@")[0] ?? "", { id: "by", header: "Started by", cell: (c) => <span className="text-subtle">{c.getValue() || "–"}</span> }),
  cost: col.accessor((r) => r.cost_usd ?? undefined, {
    id: "cost", header: "API cost", sortUndefined: "last", sortDescFirst: true,
    meta: { align: "right" }, cell: (c) => <RunCost job={c.row.original} />,
  }),
  costPerTask: col.accessor((r) => r.cost_per_task ?? undefined, {
    id: "cost_per_task", header: "Cost / task", sortUndefined: "last", sortDescFirst: true,
    meta: { align: "right" }, cell: (c) => <Money usd={c.row.original.cost_per_task} />,
  }),
  started: col.accessor((r) => (r.started_at ? Date.parse(r.started_at) : 0), {
    id: "started",
    header: "Started",
    sortDescFirst: true,
    cell: (c) => <RelativeTime value={c.row.original.started_at} />,
  }),
  duration: col.accessor((r) => r.duration_s ?? undefined, {
    id: "duration",
    header: "Duration",
    sortUndefined: "last",
    sortDescFirst: true,
    meta: { align: "right" },
    cell: (c) => <Duration seconds={c.row.original.duration_s} />,
  }),
};
