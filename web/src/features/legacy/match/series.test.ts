import { describe, expect, it } from "vitest";
import { decisionRow } from "@/test/legacyFixtures";
import { seriesOf } from "./series";

describe("seriesOf", () => {
  it("puts both sides on one row per moment, so the two lines share an x axis", () => {
    const points = seriesOf(
      [
        decisionRow({ team: 0, time_elapsed_s: 0, elixir: 5 }),
        decisionRow({ team: 1, time_elapsed_s: 0, elixir: 4 }),
        decisionRow({ team: 0, time_elapsed_s: 2, elixir: 6 }),
      ],
      "elixir",
    );
    expect(points).toEqual([
      { t: 0, blue: 5, red: 4 },
      { t: 2, blue: 6 },
    ]);
  });

  it("sorts by time even when the rows arrive out of order", () => {
    const points = seriesOf([decisionRow({ time_elapsed_s: 10, my_towers: 1 }), decisionRow({ time_elapsed_s: 2, my_towers: 2 })], "my_towers");
    expect(points.map((p) => p.t)).toEqual([2, 10]);
  });

  it("leaves a gap, rather than a zero, where a value was not recorded", () => {
    const points = seriesOf([decisionRow({ time_elapsed_s: 0, elixir: null }), decisionRow({ time_elapsed_s: 2, elixir: 3 })], "elixir");
    expect(points).toEqual([{ t: 2, blue: 3 }]);
  });

  it("is empty for no decisions", () => {
    expect(seriesOf([], "elixir")).toEqual([]);
  });
});
