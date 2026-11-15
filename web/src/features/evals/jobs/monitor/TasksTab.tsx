import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import type { JobDetail, TaskRow } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration, Money } from "@/components/domain/values";
import { DataTable } from "@/components/ui/data-table";
import { formatReward } from "@/lib/format";
import { useBenchmark } from "../../api/benchmarks";
import { useJobTasks } from "../../api/jobs";
import { DifficultyBadge } from "../../benchmarks/badges";
import { TaskPanel } from "./TaskPanel";

const col = createColumnHelper<TaskRow & { difficulty: string }>();
const ORDER = ["IN_PROGRESS", "EVALUATING", "BUILDING", "ERROR", "STOPPED", "PENDING", "FINISHED"];

export function TasksTab({ detail, runId, selected, onSelect }: { detail: JobDetail; runId: string; selected: string; onSelect: (task: string) => void }) {
  const tasks = useJobTasks(runId, detail.active, (detail.job.costs_pending ?? 0) > 0);
  const benchmark = useBenchmark(detail.job.dataset);
  const rows = useMemo(() => {
    const difficulties = new Map(benchmark.data?.tasks.map((task) => [task.id, task.difficulty]));
    return (tasks.data?.tasks ?? []).map((task) => ({ ...task, difficulty: difficulties.get(task.task) ?? "" }));
  }, [tasks.data?.tasks, benchmark.data?.tasks]);
  const columns = useMemo(
    () => [
      col.accessor("task", { header: "Task", cell: (c) => <span className="font-mono text-[13px]">{c.getValue()}</span> }),
      col.accessor((r) => r.difficulty || undefined, {
        id: "difficulty",
        header: "Difficulty",
        sortUndefined: "last",
        cell: (c) => <DifficultyBadge difficulty={c.getValue() ?? ""} />,
      }),
      col.accessor((r) => ORDER.indexOf(r.status), {
        id: "status",
        header: "Status",
        cell: (c) => <StatusPill kind="task" status={c.row.original.status} />,
      }),
      col.accessor((r) => r.reward ?? undefined, {
        id: "reward",
        header: "Reward",
        sortUndefined: "last",
        sortDescFirst: true,
        meta: { align: "right" },
        cell: (c) => <span className="tabular-nums">{formatReward(c.row.original.reward)}</span>,
      }),
      col.accessor((r) => r.duration_s ?? undefined, {
        id: "duration",
        header: "Time",
        sortUndefined: "last",
        sortDescFirst: true,
        meta: { align: "right" },
        cell: (c) => <Duration seconds={c.row.original.duration_s} />,
      }),
      col.accessor((r) => r.cost_usd ?? undefined, {
        id: "cost",
        header: "API cost",
        sortUndefined: "last",
        sortDescFirst: true,
        meta: { align: "right" },
        cell: (c) => <Money usd={c.row.original.cost_usd} />,
      }),
      col.accessor("category", { header: "Failure", cell: (c) => <span className="text-subtle">{c.getValue() || "–"}</span> }),
      col.accessor("error", {
        header: "Error",
        enableSorting: false,
        cell: (c) => (
          <span className="block max-w-[28ch] truncate text-subtle" title={c.getValue()}>
            {c.getValue() || "–"}
          </span>
        ),
      }),
    ],
    [],
  );

  return (
    <QueryBoundary query={tasks} errorTitle="Couldn't load tasks">
      {(data) => {
        const row = data.tasks.find((t) => t.task === selected);
        return (
          <div className="space-y-3">
            <p className="text-[13px] text-muted">
              API costs are reported by the harness and exclude Modal charges. A dash means the cost is unknown.
            </p>
            <div className={row ? "grid items-start gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]" : ""}>
              <DataTable
                caption="Tasks in this run"
                columns={columns}
                data={rows}
                getRowId={(r) => r.task}
                initialSorting={[{ id: "status", desc: false }]}
                selectedRowId={selected || null}
                onRowClick={(r) => onSelect(r.task === selected ? "" : r.task)}
                empty="This run has no tasks yet."
              />
              {row ? <TaskPanel runId={runId} dataset={detail.job.dataset} task={row} onClose={() => onSelect("")} /> : null}
            </div>
          </div>
        );
      }}
    </QueryBoundary>
  );
}
