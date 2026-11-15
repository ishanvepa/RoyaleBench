import { createColumnHelper } from "@tanstack/react-table";
import { Plus, Rocket } from "lucide-react";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router";
import { z } from "zod";
import type { JobRow } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { ProgressCell } from "@/components/domain/SegmentedProgress";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration, RelativeTime, Score } from "@/components/domain/values";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { ALL, Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToggleChip } from "@/components/ui/toggle-chip";
import { Tooltip } from "@/components/ui/tooltip";
import { boolParam, listParam, stringParam, useSearchState } from "@/hooks/useSearchState";
import { harnessName, plural } from "@/lib/format";
import { useJobs } from "../api/jobs";
import { useCanStart } from "../useCanStart";

const searchSchema = z.object({ status: listParam(), dataset: stringParam(), model: stringParam(), mine: boolParam() });

/** Quick filters. "Running" covers both states in which Valkyrie is still working. */
const STATUS_FILTERS = [
  { label: "Running", statuses: ["IN_PROGRESS", "STOPPING"] },
  { label: "Finished", statuses: ["FINISHED"] },
  { label: "Failed", statuses: ["ERROR"] },
  { label: "Stopped", statuses: ["STOPPED"] },
];

const STATUS_RANK: Record<string, number> = { IN_PROGRESS: 0, STOPPING: 1, ERROR: 2, STOPPED: 3, FINISHED: 4 };
const col = createColumnHelper<JobRow>();

function useColumns() {
  return useMemo(
    () => [
      col.accessor((r) => STATUS_RANK[r.status] ?? 9, {
        id: "status",
        header: "Status",
        cell: (c) => <StatusPill kind="run" status={c.row.original.status} />,
      }),
      col.accessor("job", {
        header: "Job",
        cell: (c) => (
          <Link to={`/evals/jobs/${c.row.original.id}`} className="font-medium underline-offset-4 hover:underline">
            {c.getValue()}
          </Link>
        ),
      }),
      col.accessor("dataset", {
        header: "Benchmark",
        cell: (c) => (
          <Link to={`/evals/benchmarks/${c.getValue()}`} className="text-subtle underline-offset-4 hover:text-ink hover:underline">
            {c.getValue() || "–"}
          </Link>
        ),
      }),
      col.accessor("model", { header: "Model", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      col.accessor((r) => harnessName(r.harness), { id: "harness", header: "Harness", cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
      col.accessor("progress", {
        header: "Progress",
        cell: (c) => <ProgressCell done={c.row.original.done} total={c.row.original.total} counts={c.row.original.task_state_counts} />,
      }),
      col.accessor((r) => r.score ?? undefined, {
        id: "score",
        header: "Score",
        sortDescFirst: true,
        sortUndefined: "last",
        meta: { align: "right" },
        cell: (c) => <Score value={c.row.original.score} />,
      }),
      col.accessor((r) => r.started_by.split("@")[0] ?? "", { id: "by", header: "Started by", cell: (c) => <span className="text-subtle">{c.getValue() || "–"}</span> }),
      col.accessor((r) => (r.started_at ? Date.parse(r.started_at) : 0), {
        id: "started",
        header: "Started",
        sortDescFirst: true,
        cell: (c) => <RelativeTime value={c.row.original.started_at} />,
      }),
      col.accessor((r) => r.duration_s ?? undefined, {
        id: "duration",
        header: "Duration",
        sortUndefined: "last",
        sortDescFirst: true,
        meta: { align: "right" },
        cell: (c) => <Duration seconds={c.row.original.duration_s} />,
      }),
    ],
    [],
  );
}

export function Component() {
  const navigate = useNavigate();
  const [filters, setFilters] = useSearchState(searchSchema);
  const jobs = useJobs(filters);
  const canStart = useCanStart();
  const columns = useColumns();
  const filtered = filters.status.length > 0 || filters.dataset !== "" || filters.model !== "" || filters.mine;

  const newJob = canStart.allowed ? (
    <Button asChild variant="primary">
      <Link to="/evals/jobs/new">
        <Plus className="size-4" aria-hidden /> New job
      </Link>
    </Button>
  ) : (
    <Tooltip content={canStart.reason ?? "Unavailable"}>
      {/* A disabled button cannot show a tooltip on its own, so the hint sits on a wrapper. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- keyboard users need a focus stop to read why */}
      <span tabIndex={0}>
        <Button variant="primary" disabled>
          <Plus className="size-4" aria-hidden /> New job
        </Button>
      </span>
    </Tooltip>
  );

  return (
    <div>
      <PageHeader
        title="Jobs"
        description="Each job is one Valkyrie run: a model and harness attempting a benchmark, with sandboxes on Modal."
        actions={newJob}
      />
      <QueryBoundary query={jobs} errorTitle="Couldn't load jobs">
        {(data) => {
          const running = data.jobs.filter((j) => j.status === "IN_PROGRESS" || j.status === "STOPPING").length;
          return (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-3">
                <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
                  {STATUS_FILTERS.map((f) => {
                    const on = f.statuses.every((s) => filters.status.includes(s));
                    return (
                      <ToggleChip
                        key={f.label}
                        pressed={on}
                        onPressedChange={(next) =>
                          setFilters({
                            status: next
                              ? [...new Set([...filters.status, ...f.statuses])]
                              : filters.status.filter((s) => !f.statuses.includes(s)),
                          })
                        }
                      >
                        {f.label}
                      </ToggleChip>
                    );
                  })}
                </div>
                <Select
                  aria-label="Filter by benchmark"
                  className="w-44"
                  value={filters.dataset || ALL}
                  onValueChange={(v) => setFilters({ dataset: v === ALL ? "" : v })}
                  options={[{ value: ALL, label: "All benchmarks" }, ...data.datasets.map((d) => ({ value: d, label: d }))]}
                />
                <Select
                  aria-label="Filter by model"
                  className="w-56"
                  value={filters.model || ALL}
                  onValueChange={(v) => setFilters({ model: v === ALL ? "" : v })}
                  options={[{ value: ALL, label: "All models" }, ...data.models.map((m) => ({ value: m, label: m }))]}
                />
                <label className="flex items-center gap-2 text-[13px] text-subtle">
                  <Switch checked={filters.mine} onCheckedChange={(mine) => setFilters({ mine })} disabled={!data.me} />
                  Started by me
                </label>
                {filtered ? (
                  <Button variant="ghost" size="sm" onClick={() => setFilters({ status: [], dataset: "", model: "", mine: false })}>
                    Clear filters
                  </Button>
                ) : null}
                <p className="ml-auto text-[13px] text-muted" aria-live="polite">
                  {plural(data.jobs.length, "job")}
                  {filtered ? ` of ${data.total}` : ""}
                  {running ? ` · ${running} running` : ""}
                </p>
              </div>
              <DataTable
                caption="Jobs"
                columns={columns}
                data={data.jobs}
                getRowId={(r) => r.id}
                initialSorting={[{ id: "started", desc: true }]}
                onRowClick={(row) => void navigate(`/evals/jobs/${row.id}`)}
                empty={
                  data.total === 0 ? (
                    <EmptyState
                      icon={<Rocket className="size-6" aria-hidden />}
                      title="No jobs yet"
                      description="Start a job to run a model on a benchmark through Valkyrie. It appears here and updates live."
                      className="border-0"
                    />
                  ) : (
                    "No jobs match these filters."
                  )
                }
              />
            </>
          );
        }}
      </QueryBoundary>
    </div>
  );
}
