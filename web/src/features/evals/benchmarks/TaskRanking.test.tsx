import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { TaskRankingRow } from "@/api/types";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

const row = (overrides: Partial<TaskRankingRow>): TaskRankingRow => ({
  task: "t1", rank: 1, attempts: 4, solved: 1, pass_rate: 0.25, cost_per_task: 0.2, cost_known: 3,
  infra_errors: 1, ...overrides,
});

describe("Benchmark task ranking", () => {
  it("shows pass rates, known-cost coverage, zero and missing costs and sorts both metrics", async () => {
    server.use(http.get("*/api/evals/benchmarks/:name/ranking", () => HttpResponse.json({
      rows: [row({}), row({ task: "t2", rank: 2, solved: 3, pass_rate: 0.75, cost_per_task: 0, cost_known: 4 }),
        row({ task: "t3", rank: null, attempts: 0, solved: 0, pass_rate: null, cost_per_task: null, cost_known: 0, infra_errors: 0 })],
      runs_considered: 5, costs_pending: 2,
    })));
    const { user } = renderApp("/evals/benchmarks/alpha");
    const table = await screen.findByRole("table", { name: "Task ranking" });
    expect(screen.getByText("5 finished runs", { exact: false })).toHaveTextContent("Cost data pending for 2 task attempts");
    const t1 = within(table).getByRole("row", { name: /t1/ });
    expect(within(t1).getByText("25%")).toBeInTheDocument();
    expect(within(t1).getByText("$0.200")).toBeInTheDocument();
    expect(within(t1).getByText("3 / 4")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "Results for t1" })).toHaveAttribute("href", "/evals/benchmarks/alpha/tasks/t1?tab=results");
    expect(within(within(table).getByRole("row", { name: /t2/ })).getByText("$0")).toBeInTheDocument();
    expect(within(within(table).getByRole("row", { name: /t3/ })).getAllByText("–")).toHaveLength(3);
    const order = () => within(table).getAllByRole("row").slice(1).map((r) => r.textContent?.match(/t\d/)?.[0]);
    expect(order()).toEqual(["t1", "t2", "t3"]);
    await user.click(within(table).getByRole("button", { name: "Avg pass rate" }));
    expect(order()).toEqual(["t1", "t2", "t3"]);
    await user.click(within(table).getByRole("button", { name: "Avg pass rate" }));
    expect(order()).toEqual(["t2", "t1", "t3"]);
    await user.click(within(table).getByRole("button", { name: "Avg cost / task" }));
    expect(order()).toEqual(["t1", "t2", "t3"]);
    await user.click(within(table).getByRole("button", { name: "Avg cost / task" }));
    expect(order()).toEqual(["t2", "t1", "t3"]);
  });

  it("keeps the benchmark's task list available if ranking data fails", async () => {
    server.use(http.get("*/api/evals/benchmarks/:name/ranking", () => apiError(502, "bad_gateway", "Valkyrie unavailable")));
    renderApp("/evals/benchmarks/alpha");
    expect(await screen.findByText("Couldn't load the task ranking")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Tasks in this benchmark" })).toBeInTheDocument();
  });
});
