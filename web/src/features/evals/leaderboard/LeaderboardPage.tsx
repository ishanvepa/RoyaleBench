import { createColumnHelper, type OnChangeFn, type SortingState } from "@tanstack/react-table";
import { ArrowDownWideNarrow, ArrowUpNarrowWide, Trophy } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { z } from "zod";
import type { Leaderboard, LeaderboardRow } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Duration, Money, RelativeTime, Score } from "@/components/domain/values";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { ALL, Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { boolParam, enumParam, stringParam, useSearchState } from "@/hooks/useSearchState";
import { harnessName, plural } from "@/lib/format";
import { useCostsDownload, useLeaderboard, type LeaderboardFilters } from "../api/leaderboard";

const searchSchema = z.object({
  dataset: stringParam(),
  revision: stringParam(),
  harness: stringParam(),
  smoke: boolParam(),
  full_only: boolParam(),
  sort: stringParam("rank").transform((v) => (v === "pass_rate" ? "score" : v)),
  dir: enumParam(["asc", "desc"] as const, "asc"),
});

const col = createColumnHelper<LeaderboardRow>();

/** A header with a plain-language explanation on hover. */
const head = (label: string, explanation: string) => () => <span title={explanation}>{label}</span>;

const numeric = { align: "right" as const };

function useColumns(onShowJobs: (row: LeaderboardRow) => void) {
  return useMemo(
    () => [
      col.accessor("rank", { header: head("#", "Rank by score"), meta: numeric, cell: (c) => <span className="text-muted">{c.getValue()}</span> }),
      col.accessor("model", { header: "Model", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      col.accessor((r) => harnessName(r.harness), { id: "harness", header: "Harness", cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
      col.accessor("runs", {
        header: head("Runs", "Finished runs pooled into this row. Click to inspect them."),
        meta: numeric,
        sortDescFirst: true,
        cell: (c) => (
          <button
            type="button"
            className="font-medium text-info underline-offset-4 hover:underline"
            onClick={() => onShowJobs(c.row.original)}
            aria-label={`View ${c.getValue()} ${c.getValue() === 1 ? "job" : "jobs"} for ${c.row.original.model}`}
          >
            {c.getValue()}
          </button>
        ),
      }),
      col.accessor("tasks_run", { header: head("Tasks run", "Tasks attempted across those runs (matches played)"), meta: numeric, sortDescFirst: true }),
      col.accessor("solved", { header: head("Solved", "Tasks that earned full reward (wins)"), meta: numeric, sortDescFirst: true }),
      col.accessor((r) => r.score ?? undefined, {
        id: "score",
        header: head("Score", "Mean reward across tasks, as a percentage"),
        meta: numeric,
        sortDescFirst: true,
        sortUndefined: "last",
        cell: (c) => <Score value={c.row.original.score} />,
      }),
      col.accessor("agent_failures", { header: head("Agent failures", "Tasks where the agent produced no graded result; they count as 0"), meta: numeric, sortDescFirst: true }),
      col.accessor("infra_errors", { header: head("Infra errors", "Tasks lost to Valkyrie or Modal; left out of the score"), meta: numeric, sortDescFirst: true }),
      col.accessor((r) => r.avg_agent_s ?? undefined, {
        id: "avg_agent_s",
        header: head("Avg time", "Average agent time per task"),
        meta: numeric,
        sortUndefined: "last",
        cell: (c) => <Duration seconds={c.row.original.avg_agent_s} />,
      }),
      col.accessor((r) => r.cost_usd ?? undefined, {
        id: "cost_usd",
        header: head("Cost", "Model usage the agent harness reports, summed. Excludes Modal charges."),
        meta: numeric,
        sortDescFirst: true,
        sortUndefined: "last",
        cell: (c) => {
          const row = c.row.original;
          return (
            <span title={row.cost_known < row.tasks_run ? `Cost is known for ${row.cost_known} of ${row.tasks_run} tasks` : undefined}>
              <Money usd={row.cost_usd} />
              {row.cost_usd != null && row.cost_known < row.tasks_run ? <span className="text-muted">*</span> : null}
            </span>
          );
        },
      }),
      col.accessor((r) => r.cost_per_task ?? undefined, {
        id: "cost_per_task",
        header: head("Cost / task", "Average cost over the tasks whose cost is known"),
        meta: numeric,
        sortDescFirst: true,
        sortUndefined: "last",
        cell: (c) => <Money usd={c.row.original.cost_per_task} />,
      }),
      col.accessor((r) => (r.last_run ? Date.parse(r.last_run) : 0), {
        id: "last_run",
        header: "Last run",
        sortDescFirst: true,
        cell: (c) => <RelativeTime value={c.row.original.last_run} />,
      }),
    ],
    [onShowJobs],
  );
}

/** The columns offered in the "Sort by" control (every column that can sort), with readable names. */
const SORT_LABELS: Record<string, string> = {
  rank: "Rank",
  model: "Model",
  harness: "Harness",
  runs: "Runs",
  tasks_run: "Tasks run",
  solved: "Solved",
  score: "Score",
  agent_failures: "Agent failures",
  infra_errors: "Infra errors",
  avg_agent_s: "Average time",
  cost_usd: "Cost",
  cost_per_task: "Cost per task",
  last_run: "Last run",
};

/** Higher-is-better and count columns start descending; names, rank and speed start ascending. */
const DESC_FIRST = new Set(["runs", "tasks_run", "solved", "score", "last_run", "cost_usd", "cost_per_task", "agent_failures", "infra_errors"]);

export function Component() {
  const [state, setState] = useSearchState(searchSchema);
  const [selectedRow, setSelectedRow] = useState<LeaderboardRow | null>(null);
  const filters: LeaderboardFilters = { dataset: state.dataset, revision: state.revision, harness: state.harness, includeSmoke: state.smoke, fullOnly: state.full_only };
  const leaderboard = useLeaderboard(filters);
  const costs = useCostsDownload(filters);
  const columns = useColumns(setSelectedRow);

  const sorting: SortingState = [{ id: state.sort, desc: state.dir === "desc" }];
  const onSortingChange: OnChangeFn<SortingState> = (updater) => {
    const next = (typeof updater === "function" ? updater(sorting) : updater)[0];
    if (next) setState({ sort: next.id, dir: next.desc ? "desc" : "asc" });
  };

  return (
    <div>
      <PageHeader
        title="Leaderboard"
        description="How each model does, pooled over every finished run on the selected benchmark. Click a Runs count to inspect its jobs; click a column to sort."
      />
      <QueryBoundary query={leaderboard} errorTitle="Couldn't load the leaderboard">
        {(data) => (
          <>
            <div className="mb-4 flex flex-wrap items-end gap-x-4 gap-y-3">
              <FilterSelect label="Benchmark" value={state.dataset} onChange={(v) => setState({ dataset: v, revision: "" })} allLabel={state.smoke ? "All benchmarks" : "All (except smoke tests)"} options={data.filters.datasets} />
              <FilterSelect label="Revision" value={state.revision} onChange={(v) => setState({ revision: v })} allLabel="Any revision" options={data.filters.revisions} format={(r) => `r${r}`} />
              <FilterSelect label="Harness" value={state.harness} onChange={(v) => setState({ harness: v })} allLabel="Any harness" options={data.filters.harnesses} format={harnessName} />
              <label className="flex items-center gap-2 pb-2 text-[13px] text-subtle" title="Runs with a result or error for every task in their published benchmark revision.">
                <Switch checked={state.full_only} onCheckedChange={(full_only) => setState({ full_only })} />
                Full benchmark runs only
              </label>
              <label className="flex items-center gap-2 pb-2 text-[13px] text-subtle">
                <Switch checked={state.smoke} onCheckedChange={(smoke) => setState({ smoke, dataset: "" })} />
                Include smoke tests
              </label>
              <div className="ml-auto flex items-end gap-2">
                <div className="w-44">
                  <span className="mb-1.5 block text-[13px] font-medium text-subtle" id="sort-by-label">
                    Sort by
                  </span>
                  <Select
                    aria-label="Sort by"
                    value={state.sort in SORT_LABELS ? state.sort : "rank"}
                    onValueChange={(sort) => setState({ sort, dir: DESC_FIRST.has(sort) ? "desc" : "asc" })}
                    options={Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label }))}
                  />
                </div>
                <Button variant="secondary" onClick={() => setState({ dir: state.dir === "asc" ? "desc" : "asc" })} aria-label={`Sort direction: ${state.dir === "asc" ? "ascending" : "descending"}. Click to reverse.`}>
                  {state.dir === "asc" ? <ArrowUpNarrowWide className="size-4" aria-hidden /> : <ArrowDownWideNarrow className="size-4" aria-hidden />}
                  {state.dir === "asc" ? "Ascending" : "Descending"}
                </Button>
              </div>
            </div>

            <CostsBanner data={data} costs={costs} />

            <DataTable
              caption="Model leaderboard"
              columns={columns}
              data={data.rows}
              getRowId={(r) => `${r.model}|${r.harness}`}
              sorting={sorting}
              onSortingChange={onSortingChange}
              empty={
                <EmptyState
                  icon={<Trophy className="size-6" aria-hidden />}
                  title="No finished runs match"
                  description={state.dataset || state.revision || state.harness || state.full_only ? "Try clearing a filter." : "Results appear here once a job finishes. Smoke tests are hidden unless you include them."}
                  className="border-0"
                />
              }
            />
            <p className="mt-3 text-xs text-muted">
              {plural(data.rows.length, "row")} from {plural(data.runs_considered, "finished run")} and {plural(data.tasks_considered, "task result")}. Failures caused by Valkyrie or Modal are
              left out of the score; failures by the agent count as 0. Cost is model usage reported by the agent harness and excludes Modal sandbox charges; * means it is known for only some of the tasks.
            </p>
          </>
        )}
      </QueryBoundary>
      <RunJobsDialog row={selectedRow} onOpenChange={(open) => !open && setSelectedRow(null)} />
    </div>
  );
}

function RunJobsDialog({ row, onOpenChange }: { row: LeaderboardRow | null; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog open={row !== null} onOpenChange={onOpenChange}>
      <DialogContent
        title={`${row?.runs ?? 0} ${(row?.runs ?? 0) === 1 ? "job" : "jobs"}`}
        description={row ? `${row.model} with ${harnessName(row.harness)}. Only finished jobs included in this leaderboard row are shown.` : undefined}
      >
        <ul className="divide-y divide-line">
          {row?.jobs.map((job) => (
            <li key={job.id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
              <Link to={`/evals/jobs/${job.id}`} className="min-w-0 font-medium underline-offset-4 hover:underline">
                <span className="block truncate">{job.job}</span>
                <span className="mt-0.5 block text-xs font-normal text-muted">{job.id}</span>
              </Link>
              <span className="shrink-0 text-xs text-muted"><RelativeTime value={job.started_at} /></span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  allLabel,
  options,
  format = (v) => v,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  allLabel: string;
  options: string[];
  format?: (value: string) => string;
}) {
  return (
    <div className="w-52">
      <span className="mb-1.5 block text-[13px] font-medium text-subtle">{label}</span>
      <Select
        aria-label={label}
        value={value || ALL}
        onValueChange={(v) => onChange(v === ALL ? "" : v)}
        options={[{ value: ALL, label: allLabel }, ...options.map((o) => ({ value: o, label: format(o) }))]}
      />
    </div>
  );
}

function CostsBanner({ data, costs }: { data: Leaderboard; costs: ReturnType<typeof useCostsDownload> }) {
  const status = costs.status;
  if (status?.state === "running") {
    return (
      <Banner tone="info" title="Downloading cost data…" className="mb-4">
        {status.done} of {status.total} task outputs. The table updates when it finishes.
      </Banner>
    );
  }
  if (status?.state === "error") {
    return (
      <Banner tone="danger" title="Cost download failed" className="mb-4">
        {status.error}{" "}
        <Button size="sm" variant="secondary" className="ml-2" onClick={() => costs.start.mutate()} loading={costs.start.isPending}>
          Retry
        </Button>
      </Banner>
    );
  }
  if (data.costs_pending > 0) {
    return (
      <Banner tone="neutral" title={`Cost data for ${plural(data.costs_pending, "task")} hasn't been downloaded`} className="mb-4">
        Cost lives in each task&apos;s agent output on Valkyrie, so it is fetched on request and cached.{" "}
        <Button size="sm" variant="secondary" className="ml-2" onClick={() => costs.start.mutate()} loading={costs.start.isPending}>
          Fetch cost data
        </Button>
      </Banner>
    );
  }
  return null;
}
