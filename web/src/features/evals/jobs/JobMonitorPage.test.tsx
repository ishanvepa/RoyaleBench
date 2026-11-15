import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TaskRow } from "@/api/types";
import { benchmarkDetail, environment, jobDetail, taskList } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const task = (status: string, overrides: Partial<TaskRow> = {}): TaskRow => ({
  task: "t1", status, category: "", error: "", duration_s: 5, started_at: "2026-11-14T10:00:00Z", finished_at: null, reward: null, solved: false, ...overrides,
});

afterEach(() => vi.useRealTimers());

describe("Job monitor", () => {
  it("downloads this run's costs and refreshes the metrics when complete", async () => {
    let downloaded = false;
    let state = "idle";
    let requested: unknown;
    server.use(
      http.get("*/api/evals/jobs/:runId", () => HttpResponse.json(jobDetail({}, {
        total: 2, cost_usd: downloaded ? 0.6 : null, cost_per_task: downloaded ? 0.3 : null,
        cost_known: downloaded ? 2 : 0, costs_pending: downloaded ? 0 : 2,
      }))),
      http.get("*/api/evals/jobs/:runId/tasks", () => HttpResponse.json({
        tasks: [task("FINISHED", { cost_usd: downloaded ? 0.2 : null })], counts: { FINISHED: 1 },
      })),
      http.get("*/api/evals/leaderboard/costs", () => {
        const current = state;
        if (state === "running") { state = "done"; downloaded = true; }
        return HttpResponse.json({ state: current, done: downloaded ? 2 : 0, total: 2, error: null });
      }),
      http.post("*/api/evals/jobs/costs", async ({ request }) => {
        requested = await request.json();
        state = "running";
        return HttpResponse.json({ state, done: 0, total: 2, error: null });
      }),
    );
    const { user } = renderApp("/evals/jobs/run-1");
    await user.click(await screen.findByRole("button", { name: "Fetch cost data" }));
    expect(requested).toEqual(["run-1"]);
    expect(await screen.findByText("$0.600", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText("$0.300")).toBeInTheDocument();
    expect(screen.getByText("Known for 2 of 2 tasks; excludes infrastructure charges")).toBeInTheDocument();
    expect(await within(screen.getByRole("table", { name: "Tasks in this run" })).findByText("$0.200")).toBeInTheDocument();
  }, 10_000);

  it("shows and sorts individual task costs, keeping unknown costs last", async () => {
    server.use(http.get("*/api/evals/jobs/:runId/tasks", () => HttpResponse.json({
      tasks: [
        task("FINISHED", { task: "unknown", cost_usd: null }),
        task("FINISHED", { task: "free", cost_usd: 0 }),
        task("FINISHED", { task: "expensive", cost_usd: 0.45 }),
      ], counts: { FINISHED: 3 },
    })));
    const { user } = renderApp("/evals/jobs/run-1");
    const table = await screen.findByRole("table", { name: "Tasks in this run" });
    expect(await within(table).findByText("$0.450")).toBeInTheDocument();
    expect(within(within(table).getByRole("row", { name: /free/ })).getByText("$0")).toBeInTheDocument();
    expect(within(within(table).getByRole("row", { name: /unknown/ })).queryByText(/\$/)).not.toBeInTheDocument();
    await user.click(within(table).getByRole("button", { name: /API cost/ }));
    expect(within(table).getAllByRole("row").slice(1).map((r) => r.textContent)).toEqual([
      expect.stringContaining("expensive"), expect.stringContaining("free"), expect.stringContaining("unknown"),
    ]);
    await user.click(within(table).getByRole("button", { name: /API cost/ }));
    expect(within(table).getAllByRole("row").slice(1).map((r) => r.textContent)).toEqual([
      expect.stringContaining("free"), expect.stringContaining("expensive"), expect.stringContaining("unknown"),
    ]);
  });

  it("shows a finished job: status, counts, score and the tasks", async () => {
    renderApp("/evals/jobs/run-1");
    expect(await screen.findByRole("heading", { name: "smoke-run", level: 1 })).toBeInTheDocument();
    expect(screen.getAllByText("Finished").length).toBeGreaterThan(0);
    expect(screen.getByText("1/1")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(await screen.findByRole("row", { name: /elixir-check/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).not.toBeInTheDocument(); // nothing to stop
  });

  it("keeps polling while the run is active and stops once it has finished", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let jobCalls = 0;
    server.use(
      http.get("*/api/evals/jobs/:runId", () => {
        jobCalls += 1;
        const done = jobCalls >= 3; // the third answer says the run is over
        return HttpResponse.json(jobDetail({ active: !done }, { status: done ? "FINISHED" : "IN_PROGRESS", task_state_counts: done ? { FINISHED: 1 } : { IN_PROGRESS: 1 } }));
      }),
      http.get("*/api/evals/jobs/:runId/tasks", () => HttpResponse.json({ tasks: [task("FINISHED", { reward: 1, solved: true })], counts: { FINISHED: 1 } })),
    );
    renderApp("/evals/jobs/run-1");
    await screen.findByRole("heading", { name: "smoke-run", level: 1 });
    expect(jobCalls).toBe(1);

    await act(() => vi.advanceTimersByTimeAsync(3_200));
    await waitFor(() => expect(jobCalls).toBe(2));
    await act(() => vi.advanceTimersByTimeAsync(3_200));
    await waitFor(() => expect(jobCalls).toBe(3));

    await act(() => vi.advanceTimersByTimeAsync(30_000)); // finished: no more requests
    expect(jobCalls).toBe(3);
  });

  it("does not leave the task table showing a task as running after the run has finished", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let taskCalls = 0;
    server.use(
      http.get("*/api/evals/jobs/:runId", () => HttpResponse.json(jobDetail({ active: false }))), // the run is already over...
      http.get("*/api/evals/jobs/:runId/tasks", () => {
        taskCalls += 1;
        // ...but the first task poll still saw the task running (the race this guards against).
        return HttpResponse.json({ tasks: [taskCalls === 1 ? task("IN_PROGRESS") : task("FINISHED", { reward: 1, solved: true })], counts: {} });
      }),
    );
    renderApp("/evals/jobs/run-1");
    expect(await screen.findByText("Running")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(3_200));
    expect(await screen.findByText("Done")).toBeInTheDocument();
    const settled = taskCalls;
    await act(() => vi.advanceTimersByTimeAsync(20_000));
    expect(taskCalls).toBe(settled); // and it stops asking once every task is final
  });

  it("offers Stop and Concurrency for an active run, and stops it after confirmation", async () => {
    const stops: URL[] = [];
    server.use(
      http.get("*/api/evals/jobs/:runId", () => HttpResponse.json(jobDetail({ active: true, queue: { waiting: 2, active: 1, position: 3 } }, { status: "IN_PROGRESS", task_state_counts: { IN_PROGRESS: 1, PENDING: 2 }, total: 3, done: 0 }))),
      http.post("*/api/evals/jobs/:runId/stop", ({ request }) => {
        stops.push(new URL(request.url));
        return HttpResponse.json({ status: "stopping" });
      }),
    );
    const { user } = renderApp("/evals/jobs/run-1");
    expect(await screen.findByRole("button", { name: "Concurrency" })).toBeEnabled();
    expect(screen.getByText("Next task is #3 in the Modal queue")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Stop" }));
    const dialog = await screen.findByRole("dialog", { name: "Stop this job?" });
    await user.click(within(dialog).getByRole("checkbox", { name: /force stop/i }));
    await user.click(within(dialog).getByRole("button", { name: "Stop job" }));
    await waitFor(() => expect(stops).toHaveLength(1));
    expect(stops[0]!.searchParams.get("force")).toBe("true");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("does not stop anything when the confirmation is cancelled", async () => {
    let stopped = false;
    server.use(
      http.get("*/api/evals/jobs/:runId", () => HttpResponse.json(jobDetail({ active: true }, { status: "IN_PROGRESS" }))),
      http.post("*/api/evals/jobs/:runId/stop", () => {
        stopped = true;
        return HttpResponse.json({ status: "stopping" });
      }),
    );
    const { user } = renderApp("/evals/jobs/run-1");
    await user.click(await screen.findByRole("button", { name: "Stop" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(stopped).toBe(false);
  });

  it("offers Resume for a stopped run and Retry for failed tasks", async () => {
    server.use(http.get("*/api/evals/jobs/:runId", () => HttpResponse.json(jobDetail({}, { status: "STOPPED", task_state_counts: { STOPPED: 2, ERROR: 1, FINISHED: 1 } }))));
    renderApp("/evals/jobs/run-1");
    expect(await screen.findByRole("button", { name: "Resume" })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Retry failed \(1\)/ })).toBeEnabled();
  });

  it("disables run controls on a read-only server", async () => {
    server.use(
      http.get("*/api/evals/environment", () => HttpResponse.json(environment({ read_only: true }))),
      http.get("*/api/evals/jobs/:runId", () => HttpResponse.json(jobDetail({ active: true }, { status: "IN_PROGRESS" }))),
    );
    renderApp("/evals/jobs/run-1");
    await waitFor(() => expect(screen.getByRole("button", { name: "Stop" })).toBeDisabled());
  });

  it("shows why a run failed", async () => {
    server.use(
      http.get("*/api/evals/jobs/:runId", () => HttpResponse.json(jobDetail({}, { status: "ERROR", error: "No tasks were completed successfully.", score: null }))),
      http.get("*/api/evals/jobs/:runId/tasks", () => HttpResponse.json({ tasks: [task("ERROR", { error: "Sandbox error", category: "agent" })], counts: { ERROR: 1 } })),
    );
    renderApp("/evals/jobs/run-1");
    expect(await screen.findByText("This run failed")).toBeInTheDocument();
    expect(screen.getByText("No tasks were completed successfully.")).toBeInTheDocument();
  });

  it("opens a task's panel from the table and records the choice in the URL", async () => {
    let resolutionRequests = 0;
    server.use(
      http.get("*/api/evals/benchmarks/:name", () => HttpResponse.json({
        ...benchmarkDetail(), tasks: [{ ...benchmarkDetail().tasks[0], id: "elixir-check" }],
      })),
      http.get("*/api/evals/jobs/:runId/tasks/:taskId", () =>
        HttpResponse.json({ task: "elixir-check", status: "FINISHED", category: "", error: "", reward: 1, solved: true, rewards: { reward: 1 }, verifier_output: "reward: 1", agent_s: 5, sandbox_s: 20, build_s: 1, eval_s: 1, exit_reason: null }),
      ),
      http.get("*/api/evals/jobs/:runId/tasks/:taskId/trace", () => HttpResponse.json({
        available: true, final_message: "", steps: [], steps_total: 0,
        cost_usd: 0.00123413, cost_source: "modal_token_usage", inference_cost_usd_exact: "0.00123413",
        cost_note: "Modal inference tokens only; excludes infrastructure.",
      })),
      http.get("*/api/evals/benchmarks/:name/tasks/:taskId/resolution", () => {
        resolutionRequests += 1;
        return HttpResponse.json({ available: true, html: "<html>reference game</html>", partial: false, message: "" });
      }),
    );
    const { router, user } = renderApp("/evals/jobs/run-1");
    await user.click(await screen.findByRole("row", { name: /elixir-check/ }));
    expect(await screen.findByText("Verifier output")).toBeInTheDocument();
    expect(screen.getByText("1.0 (solved)")).toBeInTheDocument();
    expect(router.state.location.search).toBe("?task=elixir-check");
    expect(screen.getByRole("button", { name: "Load agent trace" })).toBeInTheDocument(); // not downloaded until asked
    await user.click(screen.getByRole("button", { name: "Load agent trace" }));
    expect(await screen.findByText("Exact inference cost: $0.00123413")).toBeInTheDocument();
    const resolution = await screen.findByRole("button", { name: "View resolution" });
    expect(resolutionRequests).toBe(0);
    await user.click(resolution);
    expect(await screen.findByTitle("Resolution of elixir-check")).toHaveAttribute("sandbox", "allow-scripts");
    expect(resolutionRequests).toBe(1);
    expect(taskList().tasks).toHaveLength(1);
  });
});
