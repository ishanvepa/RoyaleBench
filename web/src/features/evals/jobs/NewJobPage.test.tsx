import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { JobSpecIn } from "@/api/types";
import { benchmarkDetail, benchmarkList, benchmarkRow, environment, preview } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

const WAIT = { timeout: 3_000 };
let previews: JobSpecIn[];
let started: JobSpecIn[];

function useJobHandlers(options: { previewFor?: (body: JobSpecIn) => ReturnType<typeof preview>; startResponse?: () => Response } = {}) {
  server.use(
    http.get("*/api/evals/benchmarks", () =>
      HttpResponse.json(benchmarkList([benchmarkRow({ name: "alpha", title: "Alpha" }), benchmarkRow({ name: "draft", title: "Draft", versions: 0, latest_revision: null, state: "draft" })])),
    ),
    http.post("*/api/evals/jobs/preview", async ({ request }) => {
      const body = (await request.json()) as JobSpecIn;
      previews.push(body);
      return HttpResponse.json(options.previewFor ? options.previewFor(body) : preview({ task_count: body.task_ids ? body.task_ids.length : 3 }));
    }),
    http.post("*/api/evals/jobs", async ({ request }) => {
      started.push((await request.json()) as JobSpecIn);
      return options.startResponse ? options.startResponse() : HttpResponse.json({ run_id: "run-123", task_count: 3, warning: null }, { status: 201 });
    }),
  );
}

const review = () => screen.getByRole("complementary", { name: "Review" });
const startButton = () => within(review()).getByRole("button", { name: "Start job" });

beforeEach(() => {
  previews = [];
  started = [];
});

describe("New job page", () => {
  it.each([
    ["/evals/jobs/new", "RoyaleBench v3", "royalebench-v3"],
    ["/evals/jobs/new?benchmark=alpha", "Alpha", "alpha"],
  ])("prefers the configured benchmark and respects explicit links: %s", async (path, title, dataset) => {
    useJobHandlers();
    server.use(
      http.get("*/api/evals/benchmarks", () => HttpResponse.json(benchmarkList([
        benchmarkRow({ name: "alpha", title: "Alpha" }),
        benchmarkRow({ name: "royalebench-v3", title: "RoyaleBench v3" }),
      ]))),
      http.get("*/api/evals/benchmarks/:name", ({ params }) =>
        HttpResponse.json(benchmarkDetail({ name: String(params.name) }))),
    );
    renderApp(path);
    expect(await screen.findByLabelText("Benchmark")).toHaveTextContent(title);
    await waitFor(() => expect(previews.at(-1)?.dataset).toBe(dataset), WAIT);
  });

  it("falls back to a published benchmark when the configured default is unpublished", async () => {
    useJobHandlers();
    server.use(http.get("*/api/evals/benchmarks", () => HttpResponse.json(benchmarkList([
      benchmarkRow({ name: "alpha", title: "Alpha" }),
      benchmarkRow({ name: "royalebench-v3", title: "RoyaleBench v3", versions: 0, latest_revision: null, state: "draft" }),
    ]))));
    renderApp("/evals/jobs/new");
    expect(await screen.findByLabelText("Benchmark")).toHaveTextContent("Alpha");
    await waitFor(() => expect(previews.at(-1)?.dataset).toBe("alpha"), WAIT);
  });

  it("starts with sensible defaults taken from the environment", async () => {
    useJobHandlers();
    renderApp("/evals/jobs/new?benchmark=alpha");
    expect(await screen.findByLabelText("Benchmark")).toHaveTextContent("Alpha");
    expect(screen.getByLabelText("Harness")).toHaveTextContent("claude_code");
    expect(screen.getByLabelText("Model")).toHaveTextContent("anthropic/claude-sonnet-4-6");
    expect(screen.getByLabelText("API key secret")).toHaveTextContent("anthropic-api-key-ishan"); // the user's own key, not Ben's
    expect((screen.getByLabelText("Job name") as HTMLInputElement).value).toMatch(/^alpha-claude-sonnet-4-6-\d{8}-\d{4}$/);
    expect(screen.getByLabelText("Sandbox provider")).toBeDisabled();
    expect(await within(review()).findByText("Ready", {}, WAIT)).toBeInTheDocument();
    expect(within(review()).getByText("royalebench/alpha@1")).toBeInTheDocument();
    expect(within(review()).getByText(/valkyrie run start/)).toBeInTheDocument();
  });

  it("does not offer unpublished benchmarks", async () => {
    useJobHandlers();
    const { user } = renderApp("/evals/jobs/new?benchmark=alpha");
    await user.click(await screen.findByLabelText("Benchmark"));
    const draft = await screen.findByRole("option", { name: /Draft/ });
    expect(draft).toHaveAttribute("aria-disabled", "true");
    expect(within(draft).getByText("Publish it first")).toBeInTheDocument();
  });

  it.each([
    "openai/Qwen/Qwen3.8-2.4T-A95B",
    "openai/inkling-2-small",
    "openai/deepseek-v4.1-flash-1017",
    "openai/kimi-k3.1-pro",
  ])("selects the shared Modal key when switching to %s after a manual key choice", async (model) => {
    useJobHandlers();
    const env = environment();
    server.use(http.get("*/api/evals/environment", () => HttpResponse.json(environment({
      secrets: [...env.secrets, "modal-qwen-api-key"],
      settings: { ...env.settings, models: [...env.settings.models, { id: model, secret_env: "OPENAI_API_KEY", family: "openai" }] },
    }))));
    const { user } = renderApp("/evals/jobs/new?benchmark=alpha");
    await user.click(await screen.findByLabelText("API key secret"));
    await user.click(await screen.findByRole("option", { name: "anthropic-api-key-ben" }));
    await user.click(screen.getByLabelText("Model"));
    await user.click(await screen.findByRole("option", { name: model }));
    expect(screen.getByLabelText("API key secret")).toHaveTextContent("modal-qwen-api-key");
    await waitFor(() => expect(previews.at(-1)).toMatchObject({ model, secret_name: "modal-qwen-api-key" }), WAIT);
  });

  it("starts the whole benchmark and opens the job monitor", async () => {
    useJobHandlers();
    const { router, user } = renderApp("/evals/jobs/new?benchmark=alpha");
    await within(await screen.findByRole("complementary", { name: "Review" })).findByText("Ready", {}, WAIT);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    await waitFor(() => expect(router.state.location.pathname).toBe("/evals/jobs/run-123"));
    expect(started).toHaveLength(1);
    expect(started[0]).toMatchObject({
      dataset: "alpha", revision: "latest", agent: "claude_code-v1.0.0", model: "anthropic/claude-sonnet-4-6",
      secret_name: "anthropic-api-key-ishan", concurrency: 1, task_ids: null, confirm: false,
    });
  });

  it("runs a chosen subset of tasks, and will not start with none chosen", async () => {
    useJobHandlers();
    const { user } = renderApp("/evals/jobs/new?benchmark=alpha");
    await within(await screen.findByRole("complementary", { name: "Review" })).findByText("Ready", {}, WAIT);
    await user.click(screen.getByText("Select tasks"));
    expect(await screen.findByText("0 of 3 selected")).toBeInTheDocument();
    expect(screen.getByText("Select at least one task, or run the whole benchmark")).toBeInTheDocument();
    await waitFor(() => expect(startButton()).toBeDisabled());

    await user.click(screen.getByRole("checkbox", { name: "t2" }));
    expect(screen.getByText("1 of 3 selected")).toBeInTheDocument();
    await waitFor(() => expect(previews.at(-1)?.task_ids).toEqual(["t2"]), WAIT);
    await within(review()).findByText("Ready", {}, WAIT);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    await waitFor(() => expect(started[0]?.task_ids).toEqual(["t2"]));
  });

  it("requires explicit confirmation for a large job", async () => {
    useJobHandlers({ previewFor: () => preview({ task_count: 8, needs_confirmation: true }) });
    const { user } = renderApp("/evals/jobs/new?benchmark=alpha");
    const confirm = await screen.findByRole("checkbox", { name: /I want to run it/ }, WAIT);
    await waitFor(() => expect(startButton()).toBeDisabled());
    await user.click(confirm);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    await waitFor(() => expect(started[0]?.confirm).toBe(true));
  });

  it("lists every reason a job cannot start, and blocks starting", async () => {
    useJobHandlers({ previewFor: () => preview({ valid: false, errors: ["Secret 'x' does not exist.", "Harness 'y' is not installed."], cli_command: null }) });
    renderApp("/evals/jobs/new?benchmark=alpha");
    expect(await screen.findByText("Secret 'x' does not exist.", {}, WAIT)).toBeInTheDocument();
    expect(screen.getByText("Harness 'y' is not installed.")).toBeInTheDocument();
    expect(startButton()).toBeDisabled();
    expect(within(review()).getByText("Needs attention")).toBeInTheDocument();
  });

  it("shows the server's reason when starting fails, and stays on the form", async () => {
    useJobHandlers({ startResponse: () => apiError(503, "valkyrie_network", "Cannot reach Valkyrie") as unknown as Response });
    const { router, user } = renderApp("/evals/jobs/new?benchmark=alpha");
    await within(await screen.findByRole("complementary", { name: "Review" })).findByText("Ready", {}, WAIT);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    expect(await screen.findByText("Couldn't start the job")).toBeInTheDocument();
    expect(screen.getByText("Cannot reach Valkyrie")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/evals/jobs/new");
  });

  it("validates a custom model key before it reaches the server", async () => {
    useJobHandlers();
    const { user } = renderApp("/evals/jobs/new?benchmark=alpha");
    await user.click(await screen.findByLabelText("Model"));
    await user.click(await screen.findByRole("option", { name: "Other model key…" }));
    const key = await screen.findByLabelText("Model key");
    await user.type(key, "gpt");
    expect(await screen.findByText(/Use a Valkyrie model key such as/)).toBeInTheDocument();
    await waitFor(() => expect(startButton()).toBeDisabled());
    await user.clear(key);
    await user.type(key, "openai/gpt-5");
    await waitFor(() => expect(screen.queryByText(/Use a Valkyrie model key such as/)).not.toBeInTheDocument());
    await waitFor(() => expect(previews.at(-1)?.model).toBe("openai/gpt-5"), WAIT);
  });

  it("cannot start on a read-only server", async () => {
    server.use(http.get("*/api/evals/environment", () => HttpResponse.json(environment({ read_only: true }))));
    useJobHandlers();
    renderApp("/evals/jobs/new?benchmark=alpha");
    await within(await screen.findByRole("complementary", { name: "Review" })).findByText("Ready", {}, WAIT);
    expect(startButton()).toBeDisabled();
    expect(within(review()).getByText("Starting is unavailable")).toBeInTheDocument();
  });

  it("points to publishing when no benchmark is published", async () => {
    server.use(http.get("*/api/evals/benchmarks", () => HttpResponse.json(benchmarkList([benchmarkRow({ name: "draft", title: "Draft", versions: 0, latest_revision: null, state: "draft" })]))));
    server.use(http.get("*/api/evals/benchmarks/:name", () => HttpResponse.json(benchmarkDetail())));
    renderApp("/evals/jobs/new");
    expect(await screen.findByText("No published benchmarks")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Benchmarks page" })).toHaveAttribute("href", "/evals/benchmarks");
  });
});
