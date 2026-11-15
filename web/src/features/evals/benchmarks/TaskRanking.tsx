import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link } from "react-router";
import type { BenchmarkTask, TaskRankingRow } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Money } from "@/components/domain/values";
import { DataTable } from "@/components/ui/data-table";
import { DASH, formatPercent, plural } from "@/lib/format";
import { useTaskRanking } from "../api/benchmarks";

const col = createColumnHelper<TaskRankingRow>();

export function TaskRanking({ benchmark, tasks }: { benchmark: string; tasks: BenchmarkTask[] }) {
  const ranking = useTaskRanking(benchmark);
  const columns = useMemo(() => [
    col.accessor((r) => r.rank ?? undefined, {
      id: "rank", header: "Rank", sortUndefined: "last", sortDescFirst: false,
      meta: { align: "right" }, cell: (c) => c.getValue() ?? DASH,
    }),
    col.accessor("task", {
      header: "Task",
      cell: (c) => tasks.some((t) => t.id === c.getValue() && t.local) ? (
        <Link to={`/evals/benchmarks/${benchmark}/tasks/${c.getValue()}?tab=results`}
          aria-label={`Results for ${c.getValue()}`}
          className="font-mono text-[13px] font-medium underline-offset-4 hover:underline">
          {c.getValue()}
        </Link>
      ) : <span className="font-mono text-[13px]">{c.getValue()}</span>,
    }),
    col.accessor("attempts", { header: "Attempts", meta: { align: "right" }, sortDescFirst: true }),
    col.accessor("solved", { header: "Passed", meta: { align: "right" }, sortDescFirst: true }),
    col.accessor((r) => r.pass_rate ?? undefined, {
      id: "pass_rate", header: "Avg pass rate", sortUndefined: "last", sortDescFirst: false,
      meta: { align: "right" }, cell: (c) => formatPercent(c.row.original.pass_rate),
    }),
    col.accessor((r) => r.cost_per_task ?? undefined, {
      id: "cost_per_task", header: "Avg cost / task", sortUndefined: "last", sortDescFirst: true,
      meta: { align: "right" }, cell: (c) => <Money usd={c.row.original.cost_per_task} />,
    }),
    col.accessor("cost_known", {
      header: "Cost coverage", meta: { align: "right" }, sortDescFirst: true,
      cell: (c) => `${c.getValue()} / ${c.row.original.attempts}`,
    }),
    col.accessor("infra_errors", { header: "Infra errors", meta: { align: "right" }, sortDescFirst: true }),
  ], [benchmark, tasks]);

  return (
    <section className="mt-8" aria-labelledby="task-ranking-title">
      <h2 id="task-ranking-title" className="mb-2 text-lg">Task ranking</h2>
      <p className="mb-4 text-[13px] text-muted">
        Hardest first; ties share a rank. Each attempt counts equally across models, harnesses and revisions in finished runs.
        Infrastructure errors are excluded. Average cost uses only attempts with known API costs; unknown values appear as a dash.
      </p>
      <QueryBoundary query={ranking} errorTitle="Couldn't load the task ranking">
        {(data) => (
          <>
            <p className="mb-3 text-[13px] text-subtle">
              {plural(data.runs_considered, "finished run")}
              {data.costs_pending > 0 ? ` · Cost data pending for ${plural(data.costs_pending, "task attempt")}.` : null}
            </p>
            <DataTable caption="Task ranking" columns={columns} data={data.rows} getRowId={(r) => r.task}
              initialSorting={[{ id: "rank", desc: false }]}
              empty="This benchmark has no tasks." />
          </>
        )}
      </QueryBoundary>
    </section>
  );
}
