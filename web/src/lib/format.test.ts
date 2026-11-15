import { describe, expect, it } from "vitest";
import {
  DASH,
  formatBytes,
  formatDuration,
  formatMoney,
  formatPercent,
  formatRelative,
  formatReward,
  formatScore,
  harnessName,
  modelName,
  plural,
  shortId,
} from "./format";

describe("formatDuration", () => {
  it.each([
    [0, "0s"],
    [45, "45s"],
    [125, "2m 05s"],
    [3780, "1h 03m"],
    [44.6, "45s"],
  ])("%s seconds -> %s", (seconds, expected) => expect(formatDuration(seconds)).toBe(expected));

  it("shows a dash for missing, negative or non-finite values", () => {
    for (const bad of [null, undefined, -1, Number.NaN, Number.POSITIVE_INFINITY]) expect(formatDuration(bad)).toBe(DASH);
  });
});

describe("formatMoney", () => {
  it("keeps enough precision for sub-cent costs and trims for larger ones", () => {
    expect(formatMoney(0)).toBe("$0");
    expect(formatMoney(0.0016)).toBe("$0.0016");
    expect(formatMoney(0.0159)).toBe("$0.016");
    expect(formatMoney(12.345)).toBe("$12.35");
    expect(formatMoney(null)).toBe(DASH);
  });
});

describe("percentages and scores", () => {
  it("only shows decimals when they are needed", () => {
    expect(formatPercent(0.75)).toBe("75%");
    expect(formatPercent(2 / 3)).toBe("66.7%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(undefined)).toBe(DASH);
    expect(formatScore(100)).toBe("100%");
    expect(formatScore(66.666)).toBe("66.7%");
    expect(formatScore(null)).toBe(DASH);
  });
  it("formats rewards", () => {
    expect(formatReward(1)).toBe("1.0");
    expect(formatReward(0.5)).toBe("0.5");
    expect(formatReward(0.3333)).toBe("0.333");
    expect(formatReward(null)).toBe(DASH);
  });
});

describe("formatRelative", () => {
  const now = Date.parse("2026-11-14T12:00:00Z");
  it.each([
    ["2026-11-14T11:59:50Z", "just now"],
    ["2026-11-14T11:55:00Z", "5 min ago"],
    ["2026-11-14T09:00:00Z", "3 h ago"],
    ["2026-11-12T12:00:00Z", "2 d ago"],
  ])("%s -> %s", (iso, expected) => expect(formatRelative(iso, now)).toBe(expected));

  it("falls back to a calendar date for old timestamps and a dash for junk", () => {
    expect(formatRelative("2026-01-02T00:00:00Z", now)).toMatch(/2026/);
    expect(formatRelative("not a date", now)).toBe(DASH);
    expect(formatRelative(null, now)).toBe(DASH);
  });
});

describe("names and helpers", () => {
  it("shortens models, harnesses and ids", () => {
    expect(modelName("anthropic/claude-sonnet-4-6")).toBe("claude-sonnet-4-6");
    expect(modelName("plain")).toBe("plain");
    expect(harnessName("claude_code-v1.0.0")).toBe("claude_code");
    expect(harnessName("mini_swe_agent")).toBe("mini_swe_agent");
    expect(shortId("27f16d60-bfea-44f1-b371-c115be59bfab")).toBe("27f16d60");
    expect(shortId("run-1")).toBe("run-1");
  });
  it("pluralises and formats sizes", () => {
    expect(plural(1, "task")).toBe("1 task");
    expect(plural(1234, "task")).toBe("1,234 tasks");
    expect(plural(2, "match", "matches")).toBe("2 matches");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
  });
});
