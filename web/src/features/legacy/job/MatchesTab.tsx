import { createColumnHelper } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router";
import type { MatchRow } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration } from "@/components/domain/values";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { DataTable } from "@/components/ui/data-table";
import { ALL, Select } from "@/components/ui/select";
import { ToggleChip } from "@/components/ui/toggle-chip";
import { DASH, formatDuration } from "@/lib/format";
import { PAGE_SIZE, useJobMatches } from "../api/jobs";

const STATUSES = ["done", "running", "queued", "crashed"];
const col = createColumnHelper<MatchRow>();

export interface MatchFilters {
  status: string[];
  player: string;
  page: number;
}

export function MatchesTab({ job, filters, onChange, live }: { job: string; filters: MatchFilters; onChange: (patch: Partial<MatchFilters>) => void; live: boolean }) {
  const matches = useJobMatches(job, filters, live);
  const navigate = useNavigate();
  const columns = useMemo(
    () => [
      col.accessor("status", { header: "Status", cell: (c) => <StatusPill kind="arena" status={c.getValue()} /> }),
      col.accessor("match_id", {
        header: "Match",
        cell: (c) => (
          <Link to={`/legacy/matches/${job}/${c.getValue()}`} className="font-mono text-xs underline-offset-4 hover:underline">
            {c.getValue()}
          </Link>
        ),
      }),
      col.accessor("blue", { header: "Blue" }),
      col.accessor("red", { header: "Red" }),
      col.accessor("winner", { header: "Winner", cell: (c) => c.getValue() ?? <span className="text-muted">{DASH}</span> }),
      col.display({
        id: "score",
        header: "Crowns / live",
        cell: (c) => {
          const m = c.row.original;
          if (m.crowns) return <span className="tabular-nums">{m.crowns[0]}-{m.crowns[1]}</span>;
          return m.time_left_s != null ? <span className="text-info">{Math.round(m.time_left_s)}s left</span> : <span className="text-muted">{DASH}</span>;
        },
      }),
      col.accessor("ending", { header: "Ending", cell: (c) => <span className="text-subtle">{c.getValue() ?? DASH}</span> }),
      col.accessor((r) => r.length_s ?? undefined, { id: "length", header: "Length", sortUndefined: "last", meta: { align: "right" }, cell: (c) => formatDuration(c.row.original.length_s) }),
      col.display({
        id: "errors",
        header: "Errors (b/r)",
        meta: { align: "right" },
        cell: (c) => {
          const m = c.row.original;
          return m.errors_blue == null ? DASH : `${m.errors_blue}/${m.errors_red ?? 0}`;
        },
      }),
      col.accessor((r) => r.wall_s ?? undefined, { id: "wall", header: "Wall time", sortUndefined: "last", meta: { align: "right" }, cell: (c) => <Duration seconds={c.row.original.wall_s} /> }),
    ],
    [job],
  );

  return (
    <div className="space-y-4">
      <QueryBoundary query={matches} errorTitle="Couldn't load matches">
        {(data) => {
          const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
          const crashed = data.matches.filter((m) => m.status === "crashed" && m.error);
          return (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
                  {STATUSES.map((s) => (
                    <ToggleChip
                      key={s}
                      pressed={filters.status.includes(s)}
                      onPressedChange={(on) => onChange({ status: on ? [...filters.status, s] : filters.status.filter((x) => x !== s), page: 1 })}
                    >
                      {s}
                    </ToggleChip>
                  ))}
                </div>
                <div className="w-56">
                  <Select
                    aria-label="Filter by player"
                    value={filters.player || ALL}
                    onValueChange={(v) => onChange({ player: v === ALL ? "" : v, page: 1 })}
                    options={[{ value: ALL, label: "All players" }, ...data.players.map((p) => ({ value: p, label: p }))]}
                  />
                </div>
                <p className="ml-auto text-[13px] text-muted">{data.total} matches</p>
              </div>
              <DataTable
                caption="Matches"
                columns={columns}
                data={data.matches}
                getRowId={(m) => m.match_id}
                onRowClick={(m) => (m.status === "queued" ? undefined : void navigate(`/legacy/matches/${job}/${m.match_id}`))}
                empty="No matches match these filters."
              />
              {pages > 1 ? (
                <nav aria-label="Pages" className="flex items-center justify-end gap-2 text-[13px] text-subtle">
                  <Button variant="secondary" size="sm" onClick={() => onChange({ page: filters.page - 1 })} disabled={filters.page <= 1} aria-label="Previous page">
                    <ChevronLeft className="size-4" aria-hidden />
                  </Button>
                  <span aria-live="polite">
                    Page {data.page} of {pages}
                  </span>
                  <Button variant="secondary" size="sm" onClick={() => onChange({ page: filters.page + 1 })} disabled={filters.page >= pages} aria-label="Next page">
                    <ChevronRight className="size-4" aria-hidden />
                  </Button>
                </nav>
              ) : null}
              {crashed.map((m) => (
                <details key={m.match_id} className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2">
                  <summary className="cursor-pointer text-[13px] text-danger">Crashed: {m.match_id}</summary>
                  <CodeBlock className="mt-2" code={m.error ?? ""} wrap maxHeight="14rem" />
                </details>
              ))}
            </>
          );
        }}
      </QueryBoundary>
    </div>
  );
}
