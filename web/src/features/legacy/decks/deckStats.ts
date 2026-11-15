import type { CardInfo } from "@/api/types";

/** A deck is exactly this many different cards (the engine and the server both enforce it). */
export const DECK_SIZE = 8;

export type KindFilter = "all" | "Troop" | "Building" | "Spell";

/** Average elixir cost of the named cards. A card missing from the pool counts as free; an empty deck is 0. */
export function averageElixir(pool: readonly CardInfo[], names: readonly string[]): number {
  if (names.length === 0) return 0;
  const cost = new Map(pool.map((card) => [card.name, card.elixir]));
  return names.reduce((sum, name) => sum + (cost.get(name) ?? 0), 0) / names.length;
}

/** True when both lists hold the same cards, in any order. */
export function sameCards(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  const left = [...a].sort();
  const right = [...b].sort();
  return left.every((name, i) => name === right[i]);
}

/** The cards that match a search and a type, ordered by name. */
export function filterCards(cards: readonly CardInfo[], query: string, kind: KindFilter): CardInfo[] {
  const needle = query.trim().toLowerCase();
  return cards
    .filter((card) => (kind === "all" || card.kind === kind) && (needle === "" || card.name.toLowerCase().includes(needle)))
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** Toggle a card in a selection. A full selection ignores additions, so it can never exceed ``max``. */
export function toggleCard(selected: readonly string[], name: string, max: number = DECK_SIZE): string[] {
  if (selected.includes(name)) return selected.filter((n) => n !== name);
  return selected.length >= max ? [...selected] : [...selected, name];
}
