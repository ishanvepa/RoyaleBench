import type { PlayMove } from "@/api/types";

export interface MoveGroup {
  card: string;
  cost: number;
  kind: string;
  moves: PlayMove[];
}

export interface MovePreview {
  /** The game step the preview belongs to; a preview from an earlier step is ignored. */
  step: number;
  card: string;
  index: number;
}

export interface BoardMarker {
  key: string;
  x: number;
  y: number;
  active: boolean;
}

/** Wait is its own button; every other move belongs to the card it plays, in the order the engine listed them. */
export function groupMoves(moves: readonly PlayMove[]): { wait: PlayMove | null; groups: MoveGroup[] } {
  const wait = moves.find((m) => m.slot < 0 || m.kind === "WAIT") ?? null;
  const byCard = new Map<string, MoveGroup>();
  for (const move of moves) {
    if (move === wait) continue;
    let group = byCard.get(move.card);
    if (!group) {
      group = { card: move.card, cost: move.cost, kind: move.kind, moves: [] };
      byCard.set(move.card, group);
    }
    group.moves.push(move);
  }
  return { wait, groups: [...byCard.values()] };
}

/** Where the highlighted card could land: every placement of that card, with the hovered one marked active. */
export function markersFor(moves: readonly PlayMove[], preview: MovePreview | null, step: number): BoardMarker[] {
  if (!preview || preview.step !== step) return [];
  const markers: BoardMarker[] = [];
  for (const move of moves) {
    if (move.card === preview.card && move.x != null && move.y != null) {
      markers.push({ key: String(move.index), x: move.x, y: move.y, active: move.index === preview.index });
    }
  }
  return markers;
}
