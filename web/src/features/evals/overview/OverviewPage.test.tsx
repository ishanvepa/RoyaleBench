import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { jobList, jobRow, leaderboard, leaderboardRow } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

const stubResults = (rows = [leaderboardRow({ tasks_run: 4, solved: 3, cost_usd: 0.4, cost_known: 4 }), leaderboardRow({ model: "openai/gpt-5", tasks_run: 6, solved: 2, cost_usd: 0.6, cost_known: 6 })]) =>
  server.use(http.get("*/api/evals/leaderboard", () => HttpResponse.json(leaderboard(rows))));

const tile = (label: string) => screen.getByText(label).closest("div") as HTMLElement;

describe("Evals overview", () => {
  it("totals the jobs and the results, and lists the most recent jobs", async () => {
    server.use(
      http.get("*/api/evals/jobs", () =>
        HttpResponse.json(jobList([jobRow({ id: "r1", job: "alpha-run", done: 2, total: 4, status: "IN_PROGRESS", score: null }), jobRow({ id: "r2", job: "beta-run", done: 3, total: 3 })])),
      ),
    );
    stubResults();
    renderApp("/evals/overview");

    expect(await screen.findByRole("link", { name: "alpha-run" })).toHaveAttribute("href", "/evals/jobs/r1");
    expect(within(tile("Jobs (running)")).getByText("2 (1)")).toBeInTheDocument();
    expect(within(tile("Tasks finished")).getByText("5 / 7")).toBeInTheDocument();
    expect(await within(tile("Tasks solved")).findByText("5 / 10")).toBeInTheDocument();
    expect(within(tile("Tasks solved")).getByText("50% of graded tasks")).toBeInTheDocument();
    expect(within(tile("Est. API spend")).getByText("$1.00")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("href", "/evals/overview");
  });

  it("still shows the job totals when the results cannot load", async () => {
    server.use(http.get("*/api/evals/leaderboard", () => apiError(503, "valkyrie_network", "Cannot reach Valkyrie")));
    renderApp("/evals/overview");
    expect(await screen.findByRole("link", { name: "smoke-run" })).toBeInTheDocument();
    expect(within(tile("Jobs (running)")).getByText("1 (0)")).toBeInTheDocument();
    expect((await within(tile("Tasks solved")).findAllByText("Couldn't load results")).length).toBeGreaterThan(0);
  });

  it("points at the leaderboard when the cost is only partly known", async () => {
    stubResults([leaderboardRow({ tasks_run: 4, solved: 4, cost_usd: 0.2, cost_known: 1 })]);
    renderApp("/evals/overview");
    const link = await screen.findByRole("link", { name: "Fetch the rest" });
    expect(link).toHaveAttribute("href", "/evals/leaderboard?smoke=true");
    expect(within(tile("Est. API spend")).getByText(/Known for 1 of 4 tasks/)).toBeInTheDocument();
  });

  it("explains an empty list", async () => {
    server.use(http.get("*/api/evals/jobs", () => HttpResponse.json(jobList([]))));
    stubResults([]);
    renderApp("/evals/overview");
    expect(await screen.findByText("No jobs yet")).toBeInTheDocument();
    expect(within(tile("Jobs (running)")).getByText("0 (0)")).toBeInTheDocument();
  });
});
