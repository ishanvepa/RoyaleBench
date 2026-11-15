import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import type { ArenaPlayer, ArenaResults } from "@/api/types";
import { MetricBar } from "@/components/domain/MetricBar";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { Banner } from "@/components/ui/banner";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { ToggleChip } from "@/components/ui/toggle-chip";
import { familyColor } from "@/lib/family";
import { DASH, formatMoney, formatPercent, plural } from "@/lib/format";

const col = createColumnHelper<ArenaPlayer>();
const right = { align: "right" as const };

function useColumns(details: boolean, hasBuild: boolean, mostWins: number) {
  return useMemo(() => {
    const base = [
      col.accessor("rank", { header: "#", meta: right, cell: (c) => <span className="text-muted">{c.getValue()}</span> }),
      col.accessor("name", { header: "Player", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      col.accessor("games", { header: "Games", meta: right, sortDescFirst: true }),
      col.accessor("wins", {
        header: "Wins",
        meta: right,
        sortDescFirst: true,
        cell: (c) => <MetricBar value={c.getValue()} max={mostWins} color={familyColor(c.row.original.family)} text={String(c.getValue())} />,
      }),
      col.accessor("losses", { header: "Losses", meta: right }),
      col.accessor("draws", { header: "Draws", meta: right }),
      col.accessor("win_rate", {
        header: "Win rate",
        meta: right,
        sortDescFirst: true,
        cell: (c) => <MetricBar value={c.getValue()} max={1} color={familyColor(c.row.original.family)} text={formatPercent(c.getValue())} />,
      }),
      col.accessor("crowns", {
        header: "Crowns / game",
        meta: right,
        sortDescFirst: true,
        cell: (c) => <MetricBar value={c.getValue()} max={3} color={familyColor(c.row.original.family)} text={c.getValue().toFixed(2)} />,
      }),
    ];
    if (!details) return base;
    const optional = (value: number | null | undefined) => value ?? undefined;
    return [
      ...base,
      col.accessor("three_crowns", { header: "3-crown wins", meta: right, sortDescFirst: true }),
      col.accessor((r) => optional(r.reliability), {
        id: "reliability",
        header: "Reliability",
        meta: right,
        sortDescFirst: true,
        sortUndefined: "last",
        cell: (c) => <MetricBar value={c.row.original.reliability} max={1} color={familyColor(c.row.original.family)} text={formatPercent(c.row.original.reliability)} />,
      }),
      ...(hasBuild
        ? [
            col.accessor((r) => optional(r.deck_valid), {
              id: "deck_valid",
              header: "Valid decks",
              meta: right,
              sortDescFirst: true,
              sortUndefined: "last",
              cell: (c) => <MetricBar value={c.row.original.deck_valid} max={1} color={familyColor(c.row.original.family)} text={formatPercent(c.row.original.deck_valid)} />,
            }),
          ]
        : []),
      col.accessor((r) => optional(r.think_s), {
        id: "think_s",
        header: "Think time",
        meta: right,
        sortUndefined: "last",
        cell: (c) => (c.row.original.think_s == null ? DASH : `${c.row.original.think_s.toFixed(1)} s`),
      }),
      col.accessor((r) => optional(r.cost_per_game), {
        id: "cost_per_game",
        header: "Cost / game",
        meta: right,
        sortUndefined: "last",
        cell: (c) => formatMoney(c.row.original.cost_per_game),
      }),
    ];
  }, [details, hasBuild, mostWins]);
}

export interface StandingsState {
  q: string;
  details: boolean;
}

export function StandingsView({ results, state, onChange }: { results: ArenaResults; state: StandingsState; onChange: (patch: Partial<StandingsState>) => void }) {
  const hasBuild = results.players.some((p) => p.deck_valid !== null);
  const mostWins = Math.max(1, ...results.players.map((p) => p.wins));
  const columns = useColumns(state.details, hasBuild, mostWins);
  const shown = results.players.filter((p) => p.name.toLowerCase().includes(state.q.toLowerCase()));
  const scope = results.format === "duel" ? "This battle" : "This tournament";

  return (
    <div className="space-y-4">
      {results.running ? <Banner tone="info" title="In progress">Standings include finished games only.</Banner> : null}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Input aria-label="Find a player" placeholder="Find a player…" value={state.q} onChange={(e) => onChange({ q: e.target.value })} className="w-64" />
        <ToggleChip pressed={state.details} onPressedChange={(details) => onChange({ details })}>
          {state.details ? "Hide" : "Show"} model metrics
        </ToggleChip>
      </div>
      <DataTable
        caption="Standings"
        columns={columns}
        data={shown}
        getRowId={(p) => p.name}
        initialSorting={[{ id: "rank", desc: false }]}
        empty={results.games.length ? "No players match your search." : "No finished games yet. Results appear as games finish."}
      />
      <p className="text-xs text-muted">
        {scope} only · {plural(results.players.length, "player")} · {plural(results.games.length, "finished game")} · {results.deck_rules}. Ranked by wins; ties use fewer losses, then crown difference.
      </p>
      <details className="text-xs leading-relaxed text-muted">
        <summary className="cursor-pointer text-subtle">How to read these results</summary>
        <p className="mt-2">
          Round robin describes the competition: every player is scheduled against every other player. A 1 v 1 contains just two players. Deck rules are separate: preset decks are supplied to the
          players; model-built decks are chosen by each model. Different runs are kept separate.
        </p>
        <p className="mt-2">
          Win rate = wins / games. Crowns / game = average crowns won. Model metrics include legal-move reliability, valid deck rate when available, average thinking time, and cost per game. Ongoing
          runs may have unequal game counts.
        </p>
      </details>
    </div>
  );
}
