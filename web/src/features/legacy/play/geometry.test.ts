import { describe, expect, it } from "vitest";
import { entity, towers } from "@/test/legacyFixtures";
import { ARENA_H, BOARD_H, BOARD_W, TILE, bodyRadius, boardSummary, clock, drawOrder, hpColor, hpFraction, isTower, toPx } from "./geometry";

describe("toPx", () => {
  it("puts your back-left corner at the bottom left, because SVG's y axis points down", () => {
    expect(toPx(0, 0)).toEqual([0, BOARD_H]);
    expect(toPx(18, 32)).toEqual([BOARD_W, 0]);
  });

  it("scales tiles to drawing units", () => {
    expect(toPx(9, 3)).toEqual([9 * TILE, (ARENA_H - 3) * TILE]);
  });

  it("is mirrored for the opponent's half", () => {
    const [, mine] = toPx(9, 3);
    const [, theirs] = toPx(9, 29);
    expect(theirs).toBeLessThan(mine);
  });
});

describe("bodyRadius", () => {
  it("gives towers fixed sizes, the king the larger", () => {
    expect(bodyRadius({ kind: "king", radius: 99 })).toBe(1.6 * TILE);
    expect(bodyRadius({ kind: "princess", radius: 99 })).toBe(1.25 * TILE);
  });

  it("follows a unit's radius, but never draws it smaller than 5", () => {
    expect(bodyRadius({ kind: "troop", radius: 1 })).toBe(TILE);
    expect(bodyRadius({ kind: "troop", radius: 0.1 })).toBe(5);
    expect(bodyRadius({ kind: "building", radius: 0.1 })).toBe(5);
  });
});

describe("drawOrder", () => {
  it("draws ground units first, then ground towers, then fliers, so nothing hides a tower's hit points", () => {
    const flyer = entity(1, 1, "troop", 5, 5, { flying: true });
    const king = entity(2, 0, "king", 9, 3);
    const troop = entity(3, 0, "troop", 9, 9);
    expect(drawOrder([flyer, king, troop]).map((e) => e.id)).toEqual([3, 2, 1]);
  });

  it("does not change the list it is given", () => {
    const list = [entity(1, 0, "king", 9, 3), entity(2, 0, "troop", 9, 9)];
    drawOrder(list);
    expect(list.map((e) => e.id)).toEqual([1, 2]);
  });
});

describe("hit points", () => {
  it("clamps the fraction to 0..1 and survives a zero maximum", () => {
    expect(hpFraction(50, 100)).toBe(0.5);
    expect(hpFraction(150, 100)).toBe(1);
    expect(hpFraction(-5, 100)).toBe(0);
    expect(hpFraction(10, 0)).toBe(0);
  });

  it("goes green, then yellow, then red as hit points drop", () => {
    expect(hpColor(1)).toBe("#3ecf4a");
    expect(hpColor(0.5)).toBe("#f2c230");
    expect(hpColor(0.1)).toBe("#f0503c");
  });
});

describe("isTower", () => {
  it("is true for the king and princess towers only", () => {
    expect(["king", "princess", "troop", "building"].map((kind) => isTower({ kind }))).toEqual([true, true, false, false]);
  });
});

describe("boardSummary", () => {
  it("counts each side's units and towers for screen readers", () => {
    const summary = boardSummary({ opponent: "search-bot", entities: [...towers(), entity(10, 1, "troop", 8, 20), entity(11, 1, "troop", 9, 20), entity(12, 0, "troop", 9, 9)] });
    expect(summary).toBe("Arena. You have 1 units and 3 towers standing. search-bot has 2 units and 3 towers standing.");
  });
});

describe("clock", () => {
  it("formats game time as minutes and seconds, truncating the fraction", () => {
    expect(clock(174)).toBe("2:54");
    expect(clock(92.9)).toBe("1:32");
    expect(clock(5)).toBe("0:05");
    expect(clock(0)).toBe("0:00");
  });

  it("never shows negative time", () => {
    expect(clock(-3)).toBe("0:00");
  });
});
