/** Pure calculations behind the leaderboard views, kept apart from the components so they can be tested directly. */
import type { ArenaGame, ArenaPlayer } from "@/api/types";

export const METRICS = [
  { key: "wins", label: "Wins", llmOnly: false },
  { key: "win_rate", label: "Win rate", llmOnly: false },
  { key: "crowns", label: "Crowns / game", llmOnly: false },
  { key: "reliability", label: "Reliability", llmOnly: true },
] as const;
export type MetricKey = (typeof METRICS)[number]["key"];

export const METRIC_FORMAT: Record<MetricKey, (v: number) => string> = {
  wins: (v) => String(v),
  win_rate: (v) => `${(v * 100).toFixed(1)}%`,
  crowns: (v) => v.toFixed(2),
  reliability: (v) => `${(v * 100).toFixed(1)}%`,
};

export interface SkylinePoint {
  player: ArenaPlayer;
  value: number;
  top: number;
}

const MIN_GAP = 26;

/**
 * Place players on a vertical axis by value, best at the top. Points that would sit closer than ``MIN_GAP`` px are
 * pushed apart so their labels never overlap. Returns the points and the height the axis needs.
 */
export function skylineLayout(players: readonly ArenaPlayer[], metric: MetricKey): { points: SkylinePoint[]; height: number } {
  const eligible = players
    .filter((p) => (METRICS.find((m) => m.key === metric)?.llmOnly ? p.llm : true))
    .map((p) => ({ player: p, value: p[metric] }))
    .filter((p): p is { player: ArenaPlayer; value: number } => p.value !== null && p.value !== undefined);
  if (eligible.length === 0) return { points: [], height: 0 };
  const values = eligible.map((e) => e.value);
  const hi = Math.max(...values);
  const lo = Math.min(...values);
  const span = Math.max(360, eligible.length * 46) - 60;
  const sorted = [...eligible].sort((a, b) => b.value - a.value || a.player.name.localeCompare(b.player.name));
  const tops: number[] = [];
  for (const [i, e] of sorted.entries()) {
    const natural = hi === lo ? 0 : ((hi - e.value) / (hi - lo)) * span;
    tops.push(i === 0 ? natural : Math.max(natural, (tops[i - 1] ?? 0) + MIN_GAP));
  }
  const points = sorted.map((e, i) => ({ ...e, top: (tops[i] ?? 0) + 40 }));
  return { points, height: (tops[tops.length - 1] ?? 0) + 80 };
}

export interface Matchup {
  player: string;
  opponent: string;
  wins: number;
  losses: number;
  draws: number;
  last: number;
}

/**
 * Win/loss/draw per pairing. With a ``focus`` player every row is from that player's point of view; otherwise
 * each pair appears once, ordered alphabetically, from the first player's point of view.
 */
export function matchups(games: readonly ArenaGame[], focus: string | null): Matchup[] {
  const rows = new Map<string, Matchup>();
  for (const g of games) {
    let a = g.blue;
    let b = g.red;
    let result = g.winner; // 0: a won, 1: b won, 2: draw
    if (focus !== null) {
      if (a !== focus) {
        [a, b] = [b, a];
        result = result === 2 ? 2 : 1 - result;
      }
    } else if (a > b) {
      [a, b] = [b, a];
      result = result === 2 ? 2 : 1 - result;
    }
    const key = `${a}|${b}`;
    const row = rows.get(key) ?? { player: a, opponent: b, wins: 0, losses: 0, draws: 0, last: 0 };
    if (result === 0) row.wins += 1;
    else if (result === 1) row.losses += 1;
    else row.draws += 1;
    row.last = Math.max(row.last, g.finished_at ?? 0);
    rows.set(key, row);
  }
  return [...rows.values()].sort((x, y) => y.last - x.last);
}

/** [wins, losses, draws] as blue and as red, for everyone or for one player. */
export function sideTotals(games: readonly ArenaGame[], players: readonly ArenaPlayer[], focus: string | null) {
  if (focus !== null) {
    const p = players.find((x) => x.name === focus);
    return { blue: (p?.as_blue ?? [0, 0, 0]) as number[], red: (p?.as_red ?? [0, 0, 0]) as number[] };
  }
  const blue = [0, 0, 0];
  const red = [0, 0, 0];
  for (const g of games) {
    if (g.winner === 0) {
      blue[0]! += 1;
      red[1]! += 1;
    } else if (g.winner === 1) {
      blue[1]! += 1;
      red[0]! += 1;
    } else {
      blue[2]! += 1;
      red[2]! += 1;
    }
  }
  return { blue, red };
}

/** Game length from 50 ms ticks, as m:ss. */
export function formatLength(ticks: number | null | undefined): string {
  if (!ticks) return "";
  const seconds = Math.round(ticks * 0.05);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Label of a run in the picker: its name, how many finished games it has, and its deck rules. */
export function runLabel(run: { name: string; scored_games: number; status: string; deck_rules: string }): string {
  if (!run.scored_games) {
    const status = run.status.replace(/_/g, " ");
    return `${run.name} · No results · ${status.charAt(0).toUpperCase()}${status.slice(1)}`;
  }
  return `${run.name} · ${run.scored_games} finished ${run.scored_games === 1 ? "game" : "games"} · ${run.deck_rules}`;
}
