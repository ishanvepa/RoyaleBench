import { describe, expect, it } from "vitest";
import { playState } from "@/test/legacyFixtures";
import { groupMoves, markersFor } from "./moves";

const moves = playState().moves;

describe("groupMoves", () => {
  it("separates wait from the card moves", () => {
    const { wait, groups } = groupMoves(moves);
    expect(wait?.index).toBe(0);
    expect(groups.map((g) => g.card)).toEqual(["Knight", "Fireball"]);
  });

  it("keeps each card's placements together, in the engine's order, with its cost and kind", () => {
    const knight = groupMoves(moves).groups[0];
    expect(knight).toMatchObject({ card: "Knight", cost: 3, kind: "TROOP" });
    expect(knight?.moves.map((m) => m.target)).toEqual(["left bridge", "right bridge"]);
  });

  it("copes with a list that has no wait (the game just ended) or nothing at all", () => {
    expect(groupMoves(moves.slice(1)).wait).toBeNull();
    expect(groupMoves([])).toEqual({ wait: null, groups: [] });
  });
});

describe("markersFor", () => {
  const preview = { step: 3, card: "Knight", index: 2 };

  it("marks every spot the card could land, and highlights the one being previewed", () => {
    const markers = markersFor(moves, preview, 3);
    expect(markers).toEqual([
      { key: "1", x: 3.5, y: 14, active: false },
      { key: "2", x: 14.5, y: 14, active: true },
    ]);
  });

  it("shows nothing without a preview", () => {
    expect(markersFor(moves, null, 3)).toEqual([]);
  });

  it("ignores a preview left over from an earlier step, since its moves no longer exist", () => {
    expect(markersFor(moves, preview, 4)).toEqual([]);
  });

  it("skips moves that have no position, such as wait", () => {
    expect(markersFor(moves, { step: 3, card: "wait", index: 0 }, 3)).toEqual([]);
  });
});
