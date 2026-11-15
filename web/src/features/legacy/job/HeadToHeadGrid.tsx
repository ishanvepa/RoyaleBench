import type { HeadToHeadCell } from "@/api/types";
import { heatColor } from "./heat";

/** Who beats whom: one cell per pair of players, showing the row player's points over games. */
export function HeadToHeadGrid({ cells }: { cells: HeadToHeadCell[] }) {
  const players = [...new Set(cells.flatMap((c) => [c.player, c.opponent]))].sort();
  const byPair = new Map(cells.map((c) => [`${c.player}|${c.opponent}`, c]));
  if (players.length === 0) return <p className="text-[13px] text-muted">No finished matches yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-0.5 text-xs" aria-label="Head to head: the row player's points over games">
        <thead>
          <tr>
            <td />
            {players.map((p) => (
              <th key={p} scope="col" className="max-w-[88px] px-1 pb-1 text-center align-bottom font-normal text-muted">
                <span className="block truncate" title={p}>
                  {p}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {players.map((row) => (
            <tr key={row}>
              <th scope="row" className="max-w-[140px] pr-2 text-right font-normal text-subtle">
                <span className="block truncate" title={row}>
                  {row}
                </span>
              </th>
              {players.map((opponent) => {
                const cell = byPair.get(`${row}|${opponent}`);
                if (row === opponent) return <td key={opponent} className="h-9 min-w-14 rounded bg-selected/40" aria-label="same player" />;
                if (!cell) return <td key={opponent} className="h-9 min-w-14 rounded bg-selected/20" aria-label="not played" />;
                const strong = Math.abs(cell.score - 0.5) > 0.3;
                return (
                  <td
                    key={opponent}
                    title={`${row} vs ${opponent}: ${cell.points} point${cell.points === 1 ? "" : "s"} in ${cell.games} game${cell.games === 1 ? "" : "s"}`}
                    className="h-9 min-w-14 rounded text-center tabular-nums"
                    style={{ background: heatColor(cell.score), color: strong ? "#fff" : "var(--rb-ink)" }}
                  >
                    {cell.points}/{cell.games}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
