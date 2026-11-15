import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import { Link } from "react-router";
import type { ArenaGame, ArenaResults } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { ALL, Select } from "@/components/ui/select";
import { formatNumber } from "@/lib/format";
import { formatLength, matchups, sideTotals, type Matchup } from "./stats";

const RECENT = 25;

function Stack({ label, totals }: { label: string; totals: number[] }) {
  const [w = 0, l = 0, d = 0] = totals;
  const n = w + l + d || 1;
  const pct = (x: number) => ((x / n) * 100).toFixed(1);
  return (
    <div>
      <h4 className="mb-2 text-[13px] font-medium uppercase tracking-[0.1em] text-muted">{label}</h4>
      <div role="img" aria-label={`${label}: ${pct(w)}% wins, ${pct(l)}% losses, ${pct(d)}% draws`} className="flex h-[9px] gap-px overflow-hidden rounded-sm bg-line">
        <span style={{ width: `${pct(w)}%` }} className="block bg-subtle" />
        <span style={{ width: `${pct(l)}%` }} className="block bg-muted/70" />
        <span style={{ width: `${pct(d)}%` }} className="block bg-muted/30" />
      </div>
      <p className="mt-2 text-sm text-subtle">
        Wins {pct(w)}% · Losses {pct(l)}% · Draws {pct(d)}%
      </p>
    </div>
  );
}

const matchupCol = createColumnHelper<Matchup>();
const gameCol = createColumnHelper<ArenaGame>();

export function GamesView({ results, player, onPlayerChange }: { results: ArenaResults; player: string; onPlayerChange: (p: string) => void }) {
  const focus = results.players.some((p) => p.name === player) ? player : "";
  const games = focus ? results.games.filter((g) => g.blue === focus || g.red === focus) : results.games;
  const people = focus ? results.players.filter((p) => p.name === focus) : results.players;
  const decisions = people.reduce((n, p) => n + p.decisions, 0);
  const { blue, red } = sideTotals(games, results.players, focus || null);
  const rows = useMemo(() => matchups(games, focus || null), [games, focus]);
  const logoOf = (name: string) => results.players.find((p) => p.name === name)?.logo_url;

  const matchupColumns = useMemo(
    () => [
      matchupCol.accessor("player", { header: "Player", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={logoOf(c.getValue())} /> }),
      matchupCol.accessor("opponent", { header: "Opponent", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={logoOf(c.getValue())} /> }),
      matchupCol.accessor("wins", { header: "W", meta: { align: "right" } }),
      matchupCol.accessor("losses", { header: "L", meta: { align: "right" } }),
      matchupCol.accessor("draws", { header: "D", meta: { align: "right" } }),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps -- logos come from the same results object
    [results],
  );
  const gameColumns = useMemo(
    () => [
      gameCol.accessor("blue", { header: "Blue", enableSorting: false, cell: (c) => <ModelLabel model={c.getValue()} logoUrl={logoOf(c.getValue())} /> }),
      gameCol.accessor("red", { header: "Red", enableSorting: false, cell: (c) => <ModelLabel model={c.getValue()} logoUrl={logoOf(c.getValue())} /> }),
      gameCol.accessor((g) => `${g.crowns[0]}–${g.crowns[1]}`, { id: "crowns", header: "Crowns", enableSorting: false, meta: { align: "right" } }),
      gameCol.accessor((g) => (g.winner === 2 ? "draw" : g.winner === 0 ? g.blue : g.red), {
        id: "winner",
        header: "Winner",
        enableSorting: false,
        cell: (c) => (c.getValue() === "draw" ? "draw" : <ModelLabel model={c.getValue()} logoUrl={logoOf(c.getValue())} />),
      }),
      gameCol.accessor((g) => g.deck_name ?? (g.deck_kind === "built" ? "Model-built" : "Preset deck"), { id: "deck", header: "Deck", enableSorting: false, cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
      gameCol.accessor((g) => formatLength(g.ticks), { id: "length", header: "Length", enableSorting: false, meta: { align: "right" } }),
      gameCol.display({
        id: "replay",
        header: () => <span className="sr-only">Replay</span>,
        cell: (c) =>
          c.row.original.replay ? (
            <Link className="text-subtle underline underline-offset-4 hover:text-ink" to={`/legacy/matches/${c.row.original.job}/${c.row.original.id}`}>
              replay ↗
            </Link>
          ) : null,
      }),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps -- logos come from the same results object
    [results],
  );

  return (
    <div className="space-y-10">
      <div className="mx-auto w-full max-w-sm">
        <Select
          aria-label="Filter games by model"
          value={focus || ALL}
          onValueChange={(v) => onPlayerChange(v === ALL ? "" : v)}
          options={[{ value: ALL, label: "All models" }, ...results.players.map((p) => ({ value: p.name, label: p.name }))]}
        />
      </div>
      <dl className="flex justify-center gap-14 text-center">
        {[
          ["Games", formatNumber(games.length)],
          ["Decisions", formatNumber(decisions)],
          ["Decisions / game", games.length ? (decisions / games.length).toFixed(1) : "0"],
        ].map(([label, value]) => (
          <div key={label}>
            <dd className="font-display text-3xl font-medium tabular-nums">{value}</dd>
            <dt className="mt-2 text-[13px] uppercase tracking-[0.1em] text-muted">{label}</dt>
          </div>
        ))}
      </dl>
      <div className="mx-auto w-full max-w-[722px] space-y-6">
        <Stack label="As blue" totals={blue} />
        <Stack label="As red" totals={red} />
      </div>
      <section>
        <h3 className="mb-3 text-center text-xl font-normal">Matchups</h3>
        <Card>
          <CardContent className="p-0">
            <DataTable caption="Matchups" columns={matchupColumns} data={rows} getRowId={(r) => `${r.player}|${r.opponent}`} className="border-0" empty="No games yet." />
          </CardContent>
        </Card>
      </section>
      <section>
        <h3 className="mb-3 text-center text-xl font-normal">Most recent games</h3>
        <DataTable caption="Most recent games" columns={gameColumns} data={games.slice(0, RECENT)} getRowId={(g) => g.id} empty="No games yet." />
      </section>
    </div>
  );
}
