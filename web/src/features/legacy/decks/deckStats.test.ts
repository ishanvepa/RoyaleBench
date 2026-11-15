import { describe, expect, it } from "vitest";
import { POOL } from "@/test/legacyFixtures";
import { averageElixir, DECK_SIZE, filterCards, sameCards, toggleCard } from "./deckStats";

describe("averageElixir", () => {
  it("averages the cost of the named cards", () => {
    expect(averageElixir(POOL, ["Giant", "Zap"])).toBe(3.5); // (5 + 2) / 2
    expect(averageElixir(POOL, ["Skeletons", "IceSpirits", "Log"])).toBeCloseTo(4 / 3);
  });

  it("is 0 for no cards, and counts a card the pool does not know as free", () => {
    expect(averageElixir(POOL, [])).toBe(0);
    expect(averageElixir(POOL, ["Giant", "NotACard"])).toBe(2.5);
  });
});

describe("sameCards", () => {
  it("ignores order", () => {
    expect(sameCards(["a", "b", "c"], ["c", "a", "b"])).toBe(true);
  });

  it("tells different or differently sized decks apart", () => {
    expect(sameCards(["a", "b"], ["a", "c"])).toBe(false);
    expect(sameCards(["a", "b"], ["a", "b", "c"])).toBe(false);
    expect(sameCards([], [])).toBe(true);
  });

  it("does not reorder the lists it is given", () => {
    const left = ["b", "a"];
    sameCards(left, ["a", "b"]);
    expect(left).toEqual(["b", "a"]);
  });
});

describe("filterCards", () => {
  const names = (cards: { name: string }[]) => cards.map((c) => c.name);

  it("orders by name when nothing is filtered", () => {
    const all = names(filterCards([...POOL].reverse(), "", "all"));
    expect(all).toEqual([...all].sort((a, b) => a.localeCompare(b)));
    expect(all).toHaveLength(POOL.length);
  });

  it("matches part of a name, ignoring case and surrounding spaces", () => {
    expect(names(filterCards(POOL, "  IC", "all"))).toEqual(["IceSpirits"]);
    expect(names(filterCards(POOL, "ar", "all"))).toEqual(["Archer"]);
  });

  it("filters by type, and combines it with the search", () => {
    expect(names(filterCards(POOL, "", "Spell"))).toEqual(["Fireball", "Log", "Zap"]);
    expect(names(filterCards(POOL, "o", "Spell"))).toEqual(["Log"]);
    expect(names(filterCards(POOL, "", "Building"))).toEqual(["Cannon"]);
  });

  it("returns nothing, rather than failing, when nothing matches", () => {
    expect(filterCards(POOL, "zzz", "all")).toEqual([]);
  });
});

describe("toggleCard", () => {
  it("adds a card at the end and removes one that is already chosen", () => {
    expect(toggleCard(["a"], "b")).toEqual(["a", "b"]);
    expect(toggleCard(["a", "b", "c"], "b")).toEqual(["a", "c"]);
  });

  it("never grows past the limit, but still lets a chosen card be removed", () => {
    const full = Array.from({ length: DECK_SIZE }, (_, i) => `card-${i}`);
    expect(toggleCard(full, "extra")).toEqual(full);
    expect(toggleCard(full, "card-0")).toHaveLength(DECK_SIZE - 1);
  });

  it("honours a different limit", () => {
    expect(toggleCard(["a", "b"], "c", 2)).toEqual(["a", "b"]);
    expect(toggleCard(["a", "b"], "c", 3)).toEqual(["a", "b", "c"]);
  });
});
