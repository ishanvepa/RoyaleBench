import type { DecisionRow } from "@/api/types";

export interface SeriesPoint {
  t: number;
  blue?: number;
  red?: number;
}

/** One row per moment in the game, with each side's value, so the two lines share an x axis. */
export function seriesOf(decisions: readonly DecisionRow[], field: "my_towers" | "elixir"): SeriesPoint[] {
  const byTime = new Map<number, SeriesPoint>();
  for (const d of decisions) {
    const value = d[field];
    if (value == null) continue;
    const point = byTime.get(d.time_elapsed_s) ?? { t: d.time_elapsed_s };
    point[d.team === 0 ? "blue" : "red"] = value;
    byTime.set(d.time_elapsed_s, point);
  }
  return [...byTime.values()].sort((a, b) => a.t - b.t);
}
