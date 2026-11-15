import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { DecisionDetail, MatchReport } from "@/api/types";
import { decisionRow, GIANT_BEATDOWN, matchReport } from "@/test/legacyFixtures";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

const PATH = "/legacy/matches/tourney/a-b__s1";
let detailRequests: string[];

function useMatchHandlers(report: MatchReport = matchReport(), detail: DecisionDetail = { state: "THE BOARD AS THE MODEL SAW IT", raw: "I will defend.\nMOVE: 1" }) {
  server.use(
    http.get("*/api/legacy/jobs/:job/matches/:matchId", () => HttpResponse.json(report)),
    http.get("*/api/legacy/jobs/:job/matches/:matchId/decisions/:step/:team", ({ params }) => {
      detailRequests.push(`${String(params.step)}:${String(params.team)}`);
      return HttpResponse.json(detail);
    }),
  );
}

beforeEach(() => {
  detailRequests = [];
});

const rows = () => within(screen.getByRole("table", { name: "Decisions" })).getAllByRole("row").slice(1); // without the header

describe("Match page", () => {
  it("summarizes the match: sides, result, length and the deck both played", async () => {
    useMatchHandlers();
    renderApp(PATH);
    expect(await screen.findByRole("heading", { level: 1, name: /model-a\s*vs\s*model-b/ })).toBeInTheDocument();
    expect(screen.getByText("Crowns (blue-red)").nextElementSibling).toHaveTextContent("3-0");
    expect(screen.getByText("Winner").nextElementSibling).toHaveTextContent("model-a");
    expect(screen.getByText("Wall time").nextElementSibling).toHaveTextContent("12s");
    expect(screen.getByText(`Deck (mirror)`)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(GIANT_BEATDOWN.join(", ")))).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: /breadcrumb/i })).toHaveTextContent("tourney");
  });

  it("shows both decks when the sides played different ones", async () => {
    useMatchHandlers(matchReport({ deck: null, decks: { blue: ["Giant", "Zap"], red: ["HogRider", "Log"] } }));
    renderApp(PATH);
    expect(await screen.findByText(/blue: Giant, Zap · red: HogRider, Log/)).toBeInTheDocument();
  });

  it("does not claim a winner for a draw", async () => {
    useMatchHandlers(matchReport({ winner: "draw", crowns: [1, 1] }));
    renderApp(PATH);
    expect(await screen.findByText("Winner")).toBeInTheDocument();
    expect(screen.getByText("Winner").nextElementSibling).toHaveTextContent("draw");
    expect(screen.getByText("Crowns (blue-red)").nextElementSibling).toHaveTextContent("1-1");
  });

  it("charts both sides over game time, with a text alternative", async () => {
    useMatchHandlers();
    renderApp(PATH);
    const towers = await screen.findByRole("img", { name: /Own tower HP .* model-a \(blue\) against model-b \(red\)/ });
    const elixir = screen.getByRole("img", { name: /Elixir at each decision/ });
    for (const chart of [towers, elixir]) {
      expect(within(chart).getByText("blue: model-a")).toBeInTheDocument(); // the legend names each side's player
      expect(within(chart).getByText("red: model-b")).toBeInTheDocument();
      expect(chart.querySelectorAll("path.recharts-line-curve")).toHaveLength(2); // one line per side
    }
  });

  it("lists only the decisions where the model was asked, until told otherwise", async () => {
    useMatchHandlers();
    const { user } = renderApp(PATH);
    await screen.findByRole("table", { name: "Decisions" });
    expect(rows()).toHaveLength(3); // the fixture has four, one of them a forced wait
    await user.click(screen.getByRole("switch"));
    expect(rows()).toHaveLength(4);
    await user.click(screen.getByRole("switch"));
    expect(rows()).toHaveLength(3);
  });

  it("marks a reply that could not be parsed, with its error", async () => {
    useMatchHandlers();
    renderApp(PATH);
    const bad = await screen.findByRole("row", { name: /reply had no MOVE line/ });
    expect(within(bad).getByText("failed")).toBeInTheDocument();
  });

  it("loads what the model saw and answered only when a row is opened, and closes it again", async () => {
    useMatchHandlers();
    const { user } = renderApp(PATH);
    await screen.findByRole("table", { name: "Decisions" });
    expect(detailRequests).toEqual([]); // the board text of every decision would be a lot to download up front
    expect(screen.getByText(/Select a row to see the exact board text/)).toBeInTheDocument();

    await user.click(rows()[1] as HTMLElement); // step 0, red
    expect(await screen.findByText("THE BOARD AS THE MODEL SAW IT")).toBeInTheDocument();
    expect(screen.getByText(/I will defend\./)).toBeInTheDocument();
    expect(screen.getByText("Step 0 · red · model-b")).toBeInTheDocument();
    expect(detailRequests).toEqual(["0:1"]);
    expect(rows()[1]).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByText("THE BOARD AS THE MODEL SAW IT")).not.toBeInTheDocument());
  });

  it("explains, without asking the server, that a forced wait never reached the model", async () => {
    useMatchHandlers();
    const { user } = renderApp(PATH);
    await screen.findByRole("table", { name: "Decisions" });
    await user.click(screen.getByRole("switch")); // show forced waits too
    await user.click(rows()[2] as HTMLElement); // step 1, blue: the fixture's forced wait
    expect(await screen.findByText(/only .wait. was legal at this point/)).toBeInTheDocument();
    expect(screen.getByText("Step 1 · blue · model-a")).toBeInTheDocument();
    expect(detailRequests).toEqual([]);
  });

  it("offers the replay on demand, in a sandboxed frame", async () => {
    useMatchHandlers();
    const { user } = renderApp(PATH);
    await user.click(await screen.findByRole("button", { name: "Show replay" }));
    const frame = await screen.findByTitle("Replay of a-b__s1");
    expect(frame).toHaveAttribute("src", "/api/legacy/jobs/tourney/matches/a-b__s1/replay");
    expect(frame).toHaveAttribute("sandbox", "allow-scripts"); // the viewer runs script, so it must not reach this app's origin
    expect(screen.queryByRole("button", { name: "Show replay" })).not.toBeInTheDocument();
  });

  it("says why there is no replay: this game did not keep one", async () => {
    useMatchHandlers(matchReport({ has_replay: false }));
    renderApp(PATH);
    expect(await screen.findByText(/No replay was saved for this game/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show replay" })).not.toBeInTheDocument();
  });

  it("says a replay is saved when the match finishes, while it is still being played", async () => {
    useMatchHandlers(matchReport({ status: "running", has_replay: false, winner: null, crowns: null, wall_s: null }));
    renderApp(PATH);
    expect(await screen.findByText("A replay is saved when the match finishes.")).toBeInTheDocument();
  });

  it("shows the crash instead of a result", async () => {
    useMatchHandlers(matchReport({ status: "crashed", winner: null, crowns: null, has_replay: false, error: "RuntimeError: engine stalled" }));
    renderApp(PATH);
    expect(await screen.findByText("This match crashed")).toBeInTheDocument();
    expect(screen.getByText("RuntimeError: engine stalled")).toBeInTheDocument();
  });

  it("copes with a match that has logged no decisions yet", async () => {
    useMatchHandlers(matchReport({ decisions: [], status: "running", has_replay: false }));
    renderApp(PATH);
    expect(await screen.findByText("No decisions logged yet")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Decisions" })).not.toBeInTheDocument();
  });

  it("explains a match that does not exist", async () => {
    server.use(http.get("*/api/legacy/jobs/:job/matches/:matchId", () => apiError(404, "not_found", "No such match.")));
    renderApp("/legacy/matches/tourney/nope");
    expect(await screen.findByText("Couldn't load this match")).toBeInTheDocument();
    expect(screen.getByText(/No such match\./)).toBeInTheDocument();
  });

  it("sorts the decisions by a column when its header is clicked", async () => {
    useMatchHandlers(matchReport({ decisions: [decisionRow({ step: 0, latency_s: 1 }), decisionRow({ step: 1, latency_s: 3 }), decisionRow({ step: 2, latency_s: 2 })] }));
    const { user } = renderApp(PATH);
    await screen.findByRole("table", { name: "Decisions" });
    const steps = () => rows().map((r) => within(r).getAllByRole("cell")[0]?.textContent);
    expect(steps()).toEqual(["0", "1", "2"]);
    await user.click(screen.getByRole("button", { name: /Latency/ }));
    expect(steps()).toEqual(["1", "2", "0"]); // numbers sort high to low first
    await user.click(screen.getByRole("button", { name: /Latency/ }));
    expect(steps()).toEqual(["0", "2", "1"]);
  });
});
