import type { BoardEntity, PlayState } from "@/api/types";

/** The arena is 18 tiles wide and 32 tall; one tile is drawn this many SVG units across. */
export const TILE = 18;
export const ARENA_W = 18;
export const ARENA_H = 32;
export const BOARD_W = ARENA_W * TILE;
export const BOARD_H = ARENA_H * TILE;

/**
 * Tile coordinates (x from your left edge, y up from your back edge, as the server sends them) to SVG units.
 * SVG's y axis points down, so y is flipped: your side is at the bottom.
 */
export function toPx(x: number, y: number): readonly [number, number] {
  return [x * TILE, (ARENA_H - y) * TILE];
}

export const isTower = (entity: Pick<BoardEntity, "kind">): boolean => entity.kind === "king" || entity.kind === "princess";

/** Half the width of an entity's body. Towers have fixed sizes; units follow their radius, with a floor so small ones stay visible. */
export function bodyRadius(entity: Pick<BoardEntity, "kind" | "radius">): number {
  if (entity.kind === "king") return 1.6 * TILE;
  if (entity.kind === "princess") return 1.25 * TILE;
  return Math.max(5, entity.radius * TILE);
}

/** Ground units are drawn below flying ones, and units below towers within each layer. */
export function drawOrder<T extends Pick<BoardEntity, "flying" | "kind">>(entities: readonly T[]): T[] {
  return [...entities].sort((a, b) => Number(a.flying) - Number(b.flying) || Number(isTower(a)) - Number(isTower(b)));
}

export function hpFraction(hp: number, max: number): number {
  return max > 0 ? Math.min(1, Math.max(0, hp / max)) : 0;
}

export function hpColor(fraction: number): string {
  if (fraction > 0.6) return "#3ecf4a";
  if (fraction > 0.3) return "#f2c230";
  return "#f0503c";
}

/** Fill and outline for each side (0 is you, blue; 1 is the opponent, red). */
export const SIDE = {
  0: { fill: "var(--rb-side-blue)", stroke: "color-mix(in srgb, var(--rb-side-blue) 55%, black)" },
  1: { fill: "var(--rb-side-red)", stroke: "color-mix(in srgb, var(--rb-side-red) 55%, black)" },
} as const;

export const sideOf = (team: number) => (team === 0 ? SIDE[0] : SIDE[1]);

/** What a screen reader hears for the board; everything else on it is also available as text beside it. */
export function boardSummary(state: Pick<PlayState, "entities" | "opponent">): string {
  const count = (team: number, towers: boolean) => state.entities.filter((e) => e.team === team && isTower(e) === towers).length;
  return `Arena. You have ${count(0, false)} units and ${count(0, true)} towers standing. ${state.opponent} has ${count(1, false)} units and ${count(1, true)} towers standing.`;
}

/** 92.4 seconds as "1:32". */
export function clock(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
