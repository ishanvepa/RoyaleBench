import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { benchmarkDetail, benchmarkList, environment, jobDetail, jobList, taskList } from "./fixtures";

/** Baseline handlers every test starts from; individual tests override what they care about with server.use(). */
export const handlers = [
  http.get("*/api/health", () => HttpResponse.json({ status: "ok", read_only: false, fake: false })),
  http.get("*/api/evals/environment", () => HttpResponse.json(environment())),
  http.get("*/api/evals/modal-billing", () => HttpResponse.json({ syncing: false, models: [], cost_usd: null, error: null })),
  http.get("*/api/evals/jobs", () => HttpResponse.json(jobList())),
  http.get("*/api/evals/leaderboard/costs", () => HttpResponse.json({ state: "idle", done: 0, total: 0, error: null })),
  http.get("*/api/evals/jobs/:runId", () => HttpResponse.json(jobDetail())),
  http.get("*/api/evals/jobs/:runId/tasks", () => HttpResponse.json(taskList())),
  http.get("*/api/evals/benchmarks", () => HttpResponse.json(benchmarkList())),
  http.get("*/api/evals/benchmarks/:name", () => HttpResponse.json(benchmarkDetail())),
];

export const server = setupServer(...handlers);

/** An API error in the server's envelope shape. */
export const apiError = (status: number, code: string, message: string, detail: unknown = null) =>
  HttpResponse.json({ error: { code, message, detail } }, { status });
