import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";
import { leaderboard } from "@/test/fixtures";

describe("Modal compute billing", () => {
  it("shows actual charges, unknown costs, and retained data after a failed sync", async () => {
    server.use(http.get("*/api/evals/leaderboard", () => HttpResponse.json(leaderboard([]))));
    server.use(http.get("*/api/evals/modal-billing", () => HttpResponse.json({
      syncing: false, cost_usd: 1.25, error: "Billing access unavailable",
      start: "2026-11-01T00:00:00+00:00", end: "2026-11-14T17:00:00+00:00",
      updated_at: "2026-11-14T18:35:00+00:00",
      models: [
        { model: "Qwen", app: "ep-qwen", cost_usd: 1.25, cost_by_resource: { "Output Tokens": 1.2, "CPU": 0.05 } },
        { model: "DeepSeek", app: "ep-deepseek", cost_usd: 0 },
        { model: "Inkling", app: "ep-inkling", cost_usd: null },
      ],
    })));
    renderApp("/evals/overview");
    const table = await screen.findByRole("table", { name: "Modal endpoint costs by model" });
    expect(await within(table).findByText("Qwen")).toBeInTheDocument();
    expect(within(table).getAllByText("$1.25")).toHaveLength(2);
    expect(within(table).getByText("$0")).toBeInTheDocument();
    expect(screen.getByText(/Billing access unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/before credits and discounts/)).toBeInTheDocument();
    expect(screen.getByText(/latest completed UTC hour/)).toBeInTheDocument();
    expect(within(table).getByText(/Output Tokens/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sync billing" })).toBeEnabled();
  });
});
