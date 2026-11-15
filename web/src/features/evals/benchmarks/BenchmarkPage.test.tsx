import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { benchmarkDetail, benchmarkList, benchmarkRow } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

const publishResult = (revision: number, changed: boolean) => ({
  version: { revision, digest: "sha256:abc", task_count: 3, tags: ["latest"], created_by: "me@example.com", created_at: "2026-11-14T10:00:00Z" },
  changed, stored: [], created: [], warnings: [], left_out: {},
});

describe("Benchmarks page", () => {
  it("lists benchmarks with their publish state", async () => {
    server.use(
      http.get("*/api/evals/benchmarks", () =>
        HttpResponse.json(
          benchmarkList([
            benchmarkRow({ name: "alpha", title: "Alpha" }),
            benchmarkRow({ name: "wip", title: "Work in progress", state: "draft", versions: 0, latest_revision: null, tags: [], runs: 0, best_score: null }),
            benchmarkRow({ name: "smoke", title: "Smoke", kind: "smoke", problems: 2 }),
          ]),
        ),
      ),
    );
    renderApp("/evals/benchmarks");
    expect(await screen.findByRole("link", { name: "Alpha" })).toHaveAttribute("href", "/evals/benchmarks/alpha");
    const draft = screen.getByRole("row", { name: /Work in progress/ });
    expect(within(draft).getByText("Draft")).toBeInTheDocument();
    expect(within(draft).getByText("Never")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /Smoke/ })).getByText("Smoke test")).toBeInTheDocument();
  });

  it("explains the folder convention when there are no benchmarks", async () => {
    server.use(http.get("*/api/evals/benchmarks", () => HttpResponse.json(benchmarkList([]))));
    renderApp("/evals/benchmarks");
    expect(await screen.findByText("No benchmarks yet")).toBeInTheDocument();
    expect(screen.getByText(/benchmarks\/<name>\/<task-id>/)).toBeInTheDocument();
  });
});

describe("Benchmark page", () => {
  it("shows tasks, versions and a Run button for a published benchmark", async () => {
    renderApp("/evals/benchmarks/alpha");
    expect(await screen.findByRole("heading", { name: "Alpha", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "t1" })).toHaveAttribute("href", "/evals/benchmarks/alpha/tasks/t1");
    expect(screen.getAllByText("In sync")).toHaveLength(3);
    expect(screen.getByRole("link", { name: /Run this benchmark/ })).toHaveAttribute("href", "/evals/jobs/new?benchmark=alpha");
    expect(screen.getByText("r1")).toBeInTheDocument();
  });

  it("warns that local edits are not what a job would run", async () => {
    server.use(http.get("*/api/evals/benchmarks/:name", () => HttpResponse.json(benchmarkDetail({ state: "modified" }))));
    renderApp("/evals/benchmarks/alpha");
    expect(await screen.findByText("Local changes aren't published")).toBeInTheDocument();
  });

  it("cannot run a draft: it must be published first", async () => {
    server.use(http.get("*/api/evals/benchmarks/:name", () => HttpResponse.json(benchmarkDetail({ state: "draft", versions: 0, latest_revision: null, tags: [] }))));
    renderApp("/evals/benchmarks/alpha");
    expect(await screen.findByText("This benchmark isn't published")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Run this benchmark/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run this benchmark/ })).toBeDisabled();
  });

  it("publishes with tags and says when nothing changed", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/evals/benchmarks/:name/publish", async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(publishResult(1, false));
      }),
    );
    const { user } = renderApp("/evals/benchmarks/alpha");
    await user.click(await screen.findByRole("button", { name: "Publish", exact: true } as never));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Nothing has changed since the latest published version/)).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText(/Tags/), "v2, release");
    await user.click(within(dialog).getByRole("button", { name: "Publish" }));
    expect(await screen.findByText(/Nothing changed: revision 1 is already up to date/)).toBeInTheDocument();
    expect(bodies).toEqual([{ tags: ["v2", "release"], allow_problems: false }]);
  });

  it("makes the user acknowledge task problems before publishing anyway", async () => {
    const detail = benchmarkDetail({ state: "modified", problems: 1 });
    detail.tasks[1] = { ...detail.tasks[1]!, sync: "modified", problems: ["tests/test.sh is missing, so nothing grades this task"] };
    const bodies: { allow_problems: boolean }[] = [];
    server.use(
      http.get("*/api/evals/benchmarks/:name", () => HttpResponse.json(detail)),
      http.post("*/api/evals/benchmarks/:name/publish", async ({ request }) => {
        const body = (await request.json()) as { allow_problems: boolean };
        bodies.push(body);
        return body.allow_problems ? HttpResponse.json(publishResult(2, true)) : apiError(409, "has_problems", "Some tasks have problems", [{ task: "t2", problems: ["x"] }]);
      }),
    );
    const { user } = renderApp("/evals/benchmarks/alpha");
    await user.click(await screen.findByRole("button", { name: "Publish", exact: true } as never));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Some tasks have problems")).toBeInTheDocument();
    expect(within(dialog).getByText(/tests\/test.sh is missing/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Publish" })).toBeDisabled(); // until acknowledged
    await user.click(within(dialog).getByRole("checkbox", { name: "Publish anyway" }));
    await user.click(within(dialog).getByRole("button", { name: "Publish" }));
    expect(await screen.findByText(/as revision 2/)).toBeInTheDocument();
    await waitFor(() => expect(bodies).toEqual([{ tags: [], allow_problems: true }]));
  });

  it("shows a bad tag next to the tag field", async () => {
    server.use(
      http.post("*/api/evals/benchmarks/:name/publish", () => apiError(422, "validation_error", "Invalid tag(s): 12", [{ field: "tags", message: "12" }])),
    );
    const { user } = renderApp("/evals/benchmarks/alpha");
    await user.click(await screen.findByRole("button", { name: "Publish", exact: true } as never));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText(/Tags/), "12");
    await user.click(within(dialog).getByRole("button", { name: "Publish" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("12");
    expect(dialog).toBeInTheDocument(); // stays open so the tag can be fixed
  });
});

describe("Task page", () => {
  it("renders the instruction and loads results lazily on the Results tab", async () => {
    let resultCalls = 0;
    server.use(
      http.get("*/api/evals/benchmarks/:name/tasks/:taskId", () =>
        HttpResponse.json({
          benchmark: "alpha", task: benchmarkDetail().tasks[0], instruction: "# Do the thing\n\nWrite `answer.json`.", config_toml: "[task]\nname = 'x'",
          files: [{ path: "instruction.md", size: 40 }], dockerfile: "FROM python", test_script: "echo 1 > /logs/verifier/reward.txt", solution_script: null,
        }),
      ),
      http.get("*/api/evals/benchmarks/:name/tasks/:taskId/results", () => {
        resultCalls += 1;
        return HttpResponse.json({ results: [], summary: [] });
      }),
    );
    const { user } = renderApp("/evals/benchmarks/alpha/tasks/t1");
    expect(await screen.findByRole("heading", { name: "Do the thing" })).toBeInTheDocument();
    expect(screen.getByText("answer.json")).toBeInTheDocument();
    expect(resultCalls).toBe(0);
    await user.click(screen.getByRole("tab", { name: "Files" }));
    expect(await screen.findByText("How it is graded")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Results" }));
    expect(await screen.findByText("No results yet")).toBeInTheDocument();
    expect(resultCalls).toBe(1);
  });

  it("does not render HTML from an instruction file", async () => {
    server.use(
      http.get("*/api/evals/benchmarks/:name/tasks/:taskId", () =>
        HttpResponse.json({
          benchmark: "alpha", task: benchmarkDetail().tasks[0], instruction: 'Hello <img src=x onerror="window.__pwned=1"> <script>window.__pwned=1</script>',
          config_toml: "", files: [], dockerfile: null, test_script: null, solution_script: null,
        }),
      ),
    );
    renderApp("/evals/benchmarks/alpha/tasks/t1");
    await screen.findByText(/Hello/);
    expect(document.querySelector("img[src='x']")).toBeNull();
    expect(document.querySelector("script[data-x], .prose-rb script")).toBeNull();
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
  });
});
