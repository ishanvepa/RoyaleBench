import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import type { JobDetail, TaskRow } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration } from "@/components/domain/values";
import { DataTable } from "@/components/ui/data-table";
import { formatReward } from "@/lib/format";
import { useJobTasks } from "../../api/jobs";
import { TaskPanel } from "./TaskPanel";

const col = createColumnHelper<TaskRow>();
const ORDER = ["IN_PROGRESS", "EVALUATING", "BUILDING", "ERROR", "STOPPED", "PENDING", "FINISHED"];

export function TasksTab({ detail, runId, selected, onSelect }: { detail: JobDetail; runId: string; selected: string; onSelect: (task: string) => void }) {
  const tasks = useJobTasks(runId, detail.active);
  const columns = useMemo(
    () => [
      col.accessor("task", { header: "Task", cell: (c) => <span className="font-mono text-[13px]">{c.getValue()}</span> }),
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
          <div className={row ? "grid items-start gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]" : ""}>
            <DataTable
              caption="Tasks in this run"
              columns={columns}
              data={data.tasks}
              getRowId={(r) => r.task}
              initialSorting={[{ id: "status", desc: false }]}
              selectedRowId={selected || null}
              onRowClick={(r) => onSelect(r.task === selected ? "" : r.task)}
              empty="This run has no tasks yet."
            />
            {row ? <TaskPanel runId={runId} dataset={detail.job.dataset} task={row} onClose={() => onSelect("")} /> : null}
          </div>
        );
      }}
    </QueryBoundary>
  );
}
