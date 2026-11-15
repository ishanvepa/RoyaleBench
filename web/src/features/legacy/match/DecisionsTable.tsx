import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import type { DecisionRow } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { DataTable } from "@/components/ui/data-table";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { DASH } from "@/lib/format";
import { useDecisionDetail } from "../api/jobs";

const col = createColumnHelper<DecisionRow>();
const rowId = (d: DecisionRow) => `${d.step}:${d.team}`;

function Detail({ job, matchId, row, onClose }: { job: string; matchId: string; row: DecisionRow; onClose: () => void }) {
  // A forced wait never reached the model, so there is no board text or reply to fetch.
  const detail = useDecisionDetail(job, matchId, row.asked ? row.step : null, row.asked ? row.team : null);
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Step {row.step} · {row.team === 0 ? "blue" : "red"} · {row.player}
        </CardTitle>
        <button type="button" onClick={onClose} className="text-[13px] text-muted underline underline-offset-4 hover:text-ink">
          Close
        </button>
      </CardHeader>
      <CardContent className="grid gap-5 lg:grid-cols-2">
        {row.asked ? (
          <QueryBoundary query={detail} errorTitle="Couldn't load this decision" skeleton={<Skeleton className="h-40 w-full lg:col-span-2" />}>
            {(d) => (
              <>
                <section className="space-y-1.5">
                  <h3 className="text-[13px] font-medium">What the model saw</h3>
                  <CodeBlock code={d.state || "(not recorded)"} maxHeight="26rem" wrap />
                </section>
                <section className="space-y-1.5">
                  <h3 className="text-[13px] font-medium">Model reply</h3>
                  <CodeBlock code={d.raw || "(empty)"} maxHeight="26rem" wrap />
                </section>
              </>
            )}
          </QueryBoundary>
        ) : (
          <p className="text-[13px] text-muted lg:col-span-2">Not asked: only &ldquo;wait&rdquo; was legal at this point, so the model was not called.</p>
        )}
      </CardContent>
    </Card>
  );
}

export function DecisionsTable({ job, matchId, decisions }: { job: string; matchId: string; decisions: DecisionRow[] }) {
  const [onlyAsked, setOnlyAsked] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const shown = onlyAsked ? decisions.filter((d) => d.asked) : decisions;
  const row = decisions.find((d) => rowId(d) === selected) ?? null;
  const columns = useMemo(
    () => [
      col.accessor("step", { header: "Step", meta: { align: "right" } }),
      col.accessor((d) => d.time_left_s ?? undefined, { id: "left", header: "Time left (s)", sortUndefined: "last", meta: { align: "right" }, cell: (c) => (c.row.original.time_left_s == null ? DASH : Math.round(c.row.original.time_left_s)) }),
      col.accessor((d) => (d.team === 0 ? "blue" : "red"), {
        id: "side",
        header: "Side",
        cell: (c) => (
          <span className="inline-flex items-center gap-2">
            <span aria-hidden className="size-2 rounded-full" style={{ background: c.row.original.team === 0 ? "var(--rb-side-blue)" : "var(--rb-side-red)" }} />
            {c.row.original.player}
          </span>
        ),
      }),
      col.accessor("move", { header: "Move", cell: (c) => <span className="text-subtle">{c.getValue() ?? DASH}</span> }),
      col.accessor("result", { header: "Result", cell: (c) => <span className="text-subtle">{c.getValue() ?? DASH}</span> }),
      col.accessor("ok", { header: "Parsed ok", cell: (c) => (c.row.original.asked ? c.getValue() ? <Badge tone="success">ok</Badge> : <Badge tone="danger">failed</Badge> : <span className="text-muted">{DASH}</span>) }),
      col.accessor((d) => d.latency_s ?? undefined, { id: "latency", header: "Latency (s)", sortUndefined: "last", meta: { align: "right" }, cell: (c) => (c.row.original.asked && c.row.original.latency_s != null ? c.row.original.latency_s.toFixed(2) : DASH) }),
      col.accessor("tokens_in", { header: "Tokens in", meta: { align: "right" } }),
      col.accessor("tokens_out", { header: "Tokens out", meta: { align: "right" } }),
      col.accessor("error", { header: "Error", enableSorting: false, cell: (c) => <span className="block max-w-[26ch] truncate text-danger" title={c.getValue()}>{c.getValue()}</span> }),
    ],
    [],
  );
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg">Decisions</h2>
        <label className="flex items-center gap-2 text-[13px] text-subtle">
          <Switch checked={onlyAsked} onCheckedChange={setOnlyAsked} /> Only decisions where the model was asked
        </label>
      </div>
      <DataTable
        caption="Decisions"
        columns={columns}
        data={shown}
        getRowId={rowId}
        initialSorting={[{ id: "step", desc: false }]}
        selectedRowId={selected}
        onRowClick={(d) => setSelected(rowId(d) === selected ? null : rowId(d))}
        empty="No decisions logged yet."
      />
      {row ? <Detail job={job} matchId={matchId} row={row} onClose={() => setSelected(null)} /> : <p className="text-xs text-muted">Select a row to see the exact board text the model saw and its full reply.</p>}
    </div>
  );
}
