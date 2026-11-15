/** Background for a head-to-head cell: red when the row player lost, neutral at 50%, blue when they won. */
export function heatColor(score: number): string {
  const toward = score >= 0.5 ? "var(--rb-side-blue)" : "var(--rb-danger)";
  const strength = Math.round(Math.abs(score - 0.5) * 2 * 100);
  return `color-mix(in srgb, ${toward} ${strength}%, var(--rb-selected))`;
}
