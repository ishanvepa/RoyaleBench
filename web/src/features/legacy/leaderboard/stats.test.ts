import { describe, expect, it } from "vitest";
import type { ArenaGame, ArenaPlayer } from "@/api/types";
import { formatLength, matchups, runLabel, sideTotals, skylineLayout } from "./stats";

const player = (name: string, overrides: Partial<ArenaPlayer> = {}): ArenaPlayer => ({
  rank: 1, name, family: "claude", logo_url: null, llm: true, games: 4, wins: 2, losses: 1, draws: 1, win_rate: 0.5, crowns: 1.5, conceded: 1,
  crown_diff: 2, three_crowns: 0, reliability: 0.9, think_s: 2, cost_per_game: 0.1, deck_valid: null, decisions: 100, as_blue: [1, 0, 1], as_red: [1, 1, 0], ...overrides,
});

const game = (blue: string, red: string, winner: number, finished_at = 1): ArenaGame => ({
  id: `${blue}-${red}-${finished_at}`, job: "j", blue, red, winner, crowns: [1, 0], ticks: 3000, deck_name: null, deck_kind: "preset", finished_at, replay: false,
});

describe("skylineLayout", () => {
  it("puts the best at the top and scales by value", () => {
    const { points, height } = skylineLayout([player("low", { wins: 0 }), player("high", { wins: 10 }), player("mid", { wins: 5 })], "wins");
    expect(points.map((p) => p.player.name)).toEqual(["high", "mid", "low"]);
    expect(points[0]!.top).toBe(40);
    expect(points[0]!.top).toBeLessThan(points[1]!.top);
    expect(points[1]!.top).toBeLessThan(points[2]!.top);
    expect(height).toBeGreaterThan(points[2]!.top);
  });

  it("keeps labels apart when values are close or equal", () => {
    const { points } = skylineLayout([player("a", { wins: 5 }), player("b", { wins: 5 }), player("c", { wins: 5 }), player("d", { wins: 5.01 })], "wins");
    for (let i = 1; i < points.length; i++) expect(points[i]!.top - points[i - 1]!.top).toBeGreaterThanOrEqual(26);
  });

  it("leaves out players without a value, and bots for LLM-only metrics", () => {
    const players = [player("model", { reliability: 0.8 }), player("bot", { llm: false, reliability: null }), player("noisy", { reliability: null })];
    expect(skylineLayout(players, "reliability").points.map((p) => p.player.name)).toEqual(["model"]);
    expect(skylineLayout(players, "wins").points).toHaveLength(3);
    expect(skylineLayout([], "wins")).toEqual({ points: [], height: 0 });
  });
});

describe("matchups", () => {
  const games = [game("a", "b", 0, 1), game("b", "a", 0, 2), game("a", "c", 2, 3), game("c", "a", 1, 4)];

  it("from one player's view, flips games where they were red", () => {
    const rows = matchups(games, "a");
    const ab = rows.find((r) => r.opponent === "b")!;
    expect([ab.player, ab.wins, ab.losses, ab.draws]).toEqual(["a", 1, 1, 0]);
    const ac = rows.find((r) => r.opponent === "c")!;
    expect([ac.wins, ac.losses, ac.draws]).toEqual([1, 0, 1]); // a draw, and a win as blue... c was blue in the last game and lost
    expect(rows.map((r) => r.opponent)).toEqual(["c", "b"]); // most recent pairing first
  });

  it("without a focus, lists each pair once from the alphabetically first player", () => {
    const rows = matchups(games, null);
    expect(rows.map((r) => `${r.player} v ${r.opponent}`).sort()).toEqual(["a v b", "a v c"]);
  });
});

describe("sideTotals", () => {
  it("counts every game from both seats for everyone", () => {
    const { blue, red } = sideTotals([game("a", "b", 0), game("a", "b", 1), game("b", "a", 2)], [], null);
    expect(blue).toEqual([1, 1, 1]);
    expect(red).toEqual([1, 1, 1]);
  });
  it("uses the player's own record when one is focused", () => {
    const { blue, red } = sideTotals([], [player("a", { as_blue: [3, 1, 0], as_red: [0, 2, 1] })], "a");
    expect([blue, red]).toEqual([[3, 1, 0], [0, 2, 1]]);
    expect(sideTotals([], [], "ghost").blue).toEqual([0, 0, 0]);
  });
});

describe("formatLength and runLabel", () => {
  it("formats game length", () => {
    expect(formatLength(3600)).toBe("3:00");
    expect(formatLength(3000)).toBe("2:30");
    expect(formatLength(null)).toBe("");
  });
  it("labels runs without claiming results they do not have", () => {
    expect(runLabel({ name: "battle-x", scored_games: 0, status: "running", deck_rules: "Preset decks" })).toBe("battle-x · No results · Running");
    expect(runLabel({ name: "battle-x", scored_games: 0, status: "stopped", deck_rules: "Preset decks" })).toBe("battle-x · No results · Stopped");
    expect(runLabel({ name: "battle-x", scored_games: 0, status: "queued_for_retry", deck_rules: "Preset decks" })).toBe("battle-x · No results · Queued for retry");
    expect(runLabel({ name: "b", scored_games: 1, status: "done", deck_rules: "Preset decks" })).toBe("b · 1 finished game · Preset decks");
    expect(runLabel({ name: "b", scored_games: 5, status: "done", deck_rules: "Model-built decks" })).toBe("b · 5 finished games · Model-built decks");
  });
});
