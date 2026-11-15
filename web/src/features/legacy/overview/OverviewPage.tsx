import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import type { OverviewJob } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration, Money, RelativeTime } from "@/components/domain/values";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Metric } from "@/components/ui/metric";
import { PageHeader } from "@/components/ui/page-header";
import { Switch } from "@/components/ui/switch";
import { formatNumber } from "@/lib/format";
import { useOverview } from "../api/jobs";

const col = createColumnHelper<OverviewJob>();
const STATUS_RANK: Record<string, number> = { running: 0, queued: 1, stopped: 2, done: 3 };

export function Component() {
  const [live, setLive] = useState(true);
  const overview = useOverview(live);
  const navigate = useNavigate();
  const columns = useMemo(
    () => [
      col.accessor((r) => STATUS_RANK[r.status] ?? 9, { id: "status", header: "Status", cell: (c) => <StatusPill kind="arena" status={c.row.original.status} /> }),
      col.accessor("name", {
        header: "Job",
        cell: (c) => (
          <Link to={`/legacy/jobs/${c.getValue()}`} className="font-medium underline-offset-4 hover:underline">
            {c.getValue()}
          </Link>
        ),
      }),
      col.accessor("progress", {
        header: "Progress",
        cell: (c) => (
          <span className="flex min-w-[130px] items-center gap-2">
            <span className="h-2 w-20 shrink-0 overflow-hidden rounded-full bg-selected" role="img" aria-label={`${c.row.original.done} of ${c.row.original.total} matches done`}>
              <span className="block h-full bg-success" style={{ width: `${c.getValue() * 100}%` }} />
            </span>
            <span className="text-xs tabular-nums text-subtle">
              {c.row.original.done}/{c.row.original.total}
            </span>
          </span>
        ),
      }),
      col.accessor("running", { header: "Running", meta: { align: "right" } }),
      col.accessor("crashed", { header: "Crashed", meta: { align: "right" }, cell: (c) => (c.getValue() > 0 ? <span className="text-danger">{c.getValue()}</span> : c.getValue()) }),
      col.accessor((r) => r.players.join(", "), {
        id: "players",
        header: "Players",
        enableSorting: false,
        cell: (c) => (
          <span className="block max-w-[34ch] truncate text-subtle" title={c.getValue()}>
            {c.getValue()}
          </span>
        ),
      }),
      col.accessor((r) => r.started_at ?? 0, { id: "started", header: "Started", sortDescFirst: true, cell: (c) => <RelativeTime value={c.row.original.started_at ? new Date(c.row.original.started_at * 1000) : null} /> }),
      col.accessor((r) => r.elapsed_s ?? undefined, { id: "elapsed", header: "Elapsed", sortUndefined: "last", sortDescFirst: true, meta: { align: "right" }, cell: (c) => <Duration seconds={c.row.original.elapsed_s} /> }),
      col.accessor("notes", { header: "Notes", enableSorting: false, cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
    ],
    [],
  );

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Tournaments and battles run on this machine's arena: their progress, spend and results."
        actions={
          <label className="flex items-center gap-2 text-[13px] text-subtle">
            <Switch checked={live} onCheckedChange={setLive} /> Live updates
          </label>
        }
      />
      <QueryBoundary query={overview} errorTitle="Couldn't load the overview">
        {(data) => (
          <div className="space-y-6">
            <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Metric label="Jobs (running)" value={`${data.totals.jobs} (${data.totals.running_jobs})`} />
              <Metric label="Matches finished" value={`${data.totals.matches_done} / ${data.totals.matches_total}`} />
              <Metric label="Model decisions made" value={formatNumber(data.totals.decisions)} />
              <Metric label="Est. API spend" value={<Money usd={data.totals.est_spend_usd} />} hint="Provider-reported cost where available, else tokens × list prices from the config" />
            </dl>
            <DataTable
              caption="Jobs"
              columns={columns}
              data={data.jobs}
              getRowId={(r) => r.name}
              initialSorting={[{ id: "started", desc: true }]}
              onRowClick={(r) => void navigate(`/legacy/jobs/${r.name}`)}
              empty={<EmptyState title="No jobs yet" description="Open Play and choose Model vs model to start a battle." className="border-0" />}
            />
          </div>
        )}
      </QueryBoundary>
    </div>
  );
}
