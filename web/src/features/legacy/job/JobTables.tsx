import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import type { EndingCount, PlayerMetrics, StandingRow, WinRow } from "@/api/types";
import { MetricBar } from "@/components/domain/MetricBar";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { Money } from "@/components/domain/values";
import { DataTable } from "@/components/ui/data-table";
import { familyColor } from "@/lib/family";
import { DASH, formatNumber, formatPercent } from "@/lib/format";

const right = { align: "right" as const };

// ---------------------------------------------------------------------------------- standings
const standingCol = createColumnHelper<StandingRow>();

export function StandingsTable({ rows }: { rows: StandingRow[] }) {
  const columns = useMemo(
    () => [
      standingCol.accessor("rank", { header: "#", meta: right, cell: (c) => <span className="text-muted">{c.getValue()}</span> }),
      standingCol.accessor("player", { header: "Player", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      standingCol.accessor("games", { header: "Games", meta: right, sortDescFirst: true }),
      standingCol.accessor("wins", { header: "W", meta: right, sortDescFirst: true }),
      standingCol.accessor("draws", { header: "D", meta: right }),
      standingCol.accessor("losses", { header: "L", meta: right }),
      standingCol.accessor("win_rate", {
        header: "Win %",
        meta: right,
        sortDescFirst: true,
        cell: (c) => <MetricBar value={c.getValue()} max={1} color={familyColor("other")} text={formatPercent(c.getValue())} />,
      }),
      standingCol.accessor("crowns_for", { header: "Crowns won", meta: right, sortDescFirst: true }),
      standingCol.accessor("crowns_against", { header: "Crowns lost", meta: right }),
    ],
    [],
  );
  return <DataTable caption="Standings" columns={columns} data={rows} getRowId={(r) => r.player} initialSorting={[{ id: "rank", desc: false }]} empty="No finished matches yet." />;
}

// ---------------------------------------------------------------------------------- win rates
const winCol = createColumnHelper<WinRow>();

export function WinTable({ rows }: { rows: WinRow[] }) {
  const columns = useMemo(
    () => [
      winCol.accessor("player", { header: "Player", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      winCol.accessor("games", { header: "Games", meta: right, sortDescFirst: true }),
      winCol.accessor("wins", { header: "W", meta: right, sortDescFirst: true }),
      winCol.accessor("draws", { header: "D", meta: right }),
      winCol.accessor("losses", { header: "L", meta: right }),
      winCol.accessor("win_rate", {
        header: "Win rate",
        meta: right,
        sortDescFirst: true,
        cell: (c) => <MetricBar value={c.getValue()} max={1} color={familyColor("other")} text={formatPercent(c.getValue())} />,
      }),
      winCol.accessor("avg_crowns", { header: "Avg crowns", meta: right, sortDescFirst: true }),
      winCol.accessor("avg_conceded", { header: "Avg conceded", meta: right }),
      winCol.accessor("three_crown_wins", { header: "3-crown wins", meta: right, sortDescFirst: true }),
      winCol.accessor("won_at_full_time", { header: "At full time", meta: right, sortDescFirst: true }),
      winCol.accessor("won_in_overtime", { header: "In overtime", meta: right, sortDescFirst: true }),
      winCol.accessor("won_on_tiebreak", { header: "On tiebreak", meta: right, sortDescFirst: true }),
      winCol.accessor("wins_as_blue", { header: "Wins as blue", meta: right, sortDescFirst: true }),
      winCol.accessor("wins_as_red", { header: "Wins as red", meta: right, sortDescFirst: true }),
    ],
    [],
  );
  return <DataTable caption="Win rate per player" columns={columns} data={rows} getRowId={(r) => r.player} initialSorting={[{ id: "win_rate", desc: true }]} empty="No finished matches yet." />;
}

/** How matches ended, as labelled bars. Plain markup so the numbers are readable text. */
export function EndingBars({ endings }: { endings: EndingCount[] }) {
  const most = Math.max(1, ...endings.map((e) => e.matches));
  return (
    <ul className="space-y-2" aria-label="How matches ended">
      {endings.map((e) => (
        <li key={e.ending} className="grid grid-cols-[200px_1fr_32px] items-center gap-3 text-[13px]">
          <span className="text-subtle">{e.ending}</span>
          <span aria-hidden className="h-[18px] overflow-hidden rounded-r bg-selected">
            <span className="block h-full rounded-r bg-muted" style={{ width: `${(e.matches / most) * 100}%` }} />
          </span>
          <span className="text-right tabular-nums">{e.matches}</span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------------- per-model metrics
const metricCol = createColumnHelper<PlayerMetrics>();

export function MetricsTable({ rows }: { rows: PlayerMetrics[] }) {
  const columns = useMemo(() => {
    const opt = (v: number | null) => v ?? undefined;
    const number = (header: string, get: (r: PlayerMetrics) => number | null | undefined, format: (v: number) => string, hint?: string) =>
      metricCol.accessor((r) => opt(get(r) ?? null), {
        id: header,
        header: () => <span title={hint}>{header}</span>,
        meta: right,
        sortUndefined: "last",
        sortDescFirst: true,
        cell: (c) => {
          const v = get(c.row.original);
          return v == null ? <span className="text-muted">{DASH}</span> : format(v);
        },
      });
    return [
      metricCol.accessor("player", { header: "Player", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      number("Decisions asked", (r) => r.asked, formatNumber, "Decision points where a move other than wait was possible: the only times the model is called"),
      number("Cards played", (r) => r.plays, formatNumber),
      number("Refused by engine", (r) => r.refused, formatNumber, "Plays the engine rejected"),
      number("API error rate", (r) => r.error_rate, (v) => formatPercent(v), "Timeouts, API errors, refusals; played as wait"),
      number("Bad reply rate", (r) => r.bad_reply_rate, (v) => formatPercent(v), "No MOVE line, or an illegal move number; played as wait"),
      number("Avg latency (s)", (r) => r.avg_latency_s, (v) => v.toFixed(2)),
      number("Max latency (s)", (r) => r.max_latency_s, (v) => v.toFixed(1)),
      number("Tokens in", (r) => r.tokens_in, formatNumber),
      number("Tokens out", (r) => r.tokens_out, formatNumber),
      number("Cached read", (r) => r.cache_read, formatNumber),
      metricCol.accessor("est_cost_usd", { header: "Est. cost", meta: right, sortDescFirst: true, cell: (c) => <Money usd={c.getValue()} /> }),
    ];
  }, []);
  return (
    <div className="space-y-2">
      <DataTable caption="Per-model metrics" columns={columns} data={rows} getRowId={(r) => r.player} initialSorting={[{ id: "player", desc: false }]} empty="No decisions logged yet." />
      <p className="text-xs text-muted">Errors and bad replies are played as &ldquo;wait&rdquo;. Bots make no API calls, so their latency, token and error columns are blank.</p>
    </div>
  );
}
