import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { leaderboard, leaderboardRow } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const rows = [
  leaderboardRow({ rank: 1, model: "anthropic/claude-opus-5-5", solved: 3, score: 75, pass_rate: 0.75, cost_usd: 0.9, cost_per_task: 0.225, avg_agent_s: 9 }),
  leaderboardRow({ rank: 2, model: "openai/gpt-5", family: "gpt", logo_url: "/api/assets/logos/gpt", harness: "codex-v1.0.0", solved: 2, score: 50, pass_rate: 0.5, cost_usd: 0.2, cost_per_task: 0.05, avg_agent_s: 4 }),
  leaderboardRow({ rank: 3, model: "anthropic/claude-haiku-5-5", solved: 1, score: 25, pass_rate: 0.25, cost_usd: null, cost_per_task: null, cost_known: 0, avg_agent_s: 6 }),
];

const stubLeaderboard = (data = leaderboard(rows)) =>
  server.use(
    http.get("*/api/evals/leaderboard", () => HttpResponse.json(data)),
    http.get("*/api/evals/leaderboard/costs", () => HttpResponse.json({ state: "idle", done: 0, total: 0, error: null })),
  );

const models = () =>
  within(screen.getByRole("table", { name: "Model leaderboard" }))
    .getAllByRole("row")
    .slice(1)
    .map((r) => within(r).getAllByRole("cell")[1]?.textContent);

describe("Leaderboard page", () => {
  it("ranks models by score by default", async () => {
    stubLeaderboard();
    renderApp("/evals/leaderboard");
    await screen.findByRole("table", { name: "Model leaderboard" });
    expect(models()).toEqual(["claude-opus-5-5", "gpt-5", "claude-haiku-5-5"]);
    expect(screen.getByText(/3 rows from 3 finished runs/)).toBeInTheDocument();
  });

  it("sorts by the Sort by control and keeps the choice in the URL", async () => {
    stubLeaderboard();
    const { router, user } = renderApp("/evals/leaderboard");
    await screen.findByRole("table", { name: "Model leaderboard" });
    await user.click(screen.getByRole("combobox", { name: "Sort by" }));
    await user.click(await screen.findByRole("option", { name: "Average time" }));
    await waitFor(() => expect(router.state.location.search).toContain("sort=avg_agent_s"));
    expect(models()).toEqual(["claude-opus-5-5", "claude-haiku-5-5", "gpt-5"].sort((a, b) => ({ "gpt-5": 4, "claude-haiku-5-5": 6, "claude-opus-5-5": 9 })[a]! - ({ "gpt-5": 4, "claude-haiku-5-5": 6, "claude-opus-5-5": 9 })[b]!));
    await user.click(screen.getByRole("button", { name: /sort direction/i }));
    await waitFor(() => expect(router.state.location.search).toContain("dir=desc"));
    expect(models()).toEqual(["claude-opus-5-5", "claude-haiku-5-5", "gpt-5"]);
  });

  it("sorts by a column header too, and a link to a sorted view restores it", async () => {
    stubLeaderboard();
    const { user, unmount } = renderApp("/evals/leaderboard?sort=cost_usd&dir=desc");
    await screen.findByRole("table", { name: "Model leaderboard" });
    expect(models()).toEqual(["claude-opus-5-5", "gpt-5", "claude-haiku-5-5"]); // the model without a known cost is always last
    expect(screen.getByRole("columnheader", { name: "Cost" })).toHaveAttribute("aria-sort", "descending");
    await user.click(within(screen.getByRole("columnheader", { name: /^Model/ })).getByRole("button"));
    expect(models()).toEqual(["claude-haiku-5-5", "claude-opus-5-5", "gpt-5"]);
    unmount();
  });

  it("sends the filters to the API", async () => {
    const requests: URL[] = [];
    server.use(
      http.get("*/api/evals/leaderboard", ({ request }) => {
        requests.push(new URL(request.url));
        return HttpResponse.json(leaderboard(rows));
      }),
      http.get("*/api/evals/leaderboard/costs", () => HttpResponse.json({ state: "idle", done: 0, total: 0, error: null })),
    );
    const { user } = renderApp("/evals/leaderboard?dataset=arena-lite&harness=claude_code-v1.0.0");
    await screen.findByRole("table", { name: "Model leaderboard" });
    expect(requests[0]!.searchParams.get("dataset")).toBe("arena-lite");
    expect(requests[0]!.searchParams.get("harness")).toBe("claude_code-v1.0.0");
    await user.click(screen.getByRole("switch", { name: /include smoke tests/i }));
    await waitFor(() => expect(requests.at(-1)?.searchParams.get("include_smoke")).toBe("true"));
    expect(requests.at(-1)?.searchParams.get("dataset")).toBeNull(); // the benchmark filter resets with it
  });

  it("offers to download cost data, shows progress, and refreshes when it finishes", async () => {
    let state: "idle" | "running" | "done" = "idle";
    let posts = 0;
    let pendingNow = 5;
    server.use(
      http.get("*/api/evals/leaderboard", () => HttpResponse.json(leaderboard(rows, { costs_pending: pendingNow }))),
      http.get("*/api/evals/leaderboard/costs", () => {
        const current = state;
        if (state === "running") {
          state = "done"; // the next poll sees it finished
          pendingNow = 0;
        }
        return HttpResponse.json({ state: current, done: current === "running" ? 2 : 5, total: 5, error: null });
      }),
      http.post("*/api/evals/leaderboard/costs", () => {
        posts += 1;
        state = "running";
        return HttpResponse.json({ state: "running", done: 0, total: 5, error: null });
      }),
    );
    const { user } = renderApp("/evals/leaderboard");
    expect(await screen.findByText(/Cost data for 5 tasks hasn't been downloaded/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Fetch cost data" }));
    expect(await screen.findByText("Downloading cost data…")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/Cost data for 5 tasks/)).not.toBeInTheDocument(), { timeout: 4_000 });
    expect(posts).toBe(1);
  });

  it("explains an empty leaderboard", async () => {
    stubLeaderboard(leaderboard([]));
    renderApp("/evals/leaderboard");
    expect(await screen.findByText("No finished runs match")).toBeInTheDocument();
  });
});
