import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderApp } from "@/test/render";
import { server, apiError } from "@/test/server";

function taskPanel() {
  server.use(
    http.get("*/api/evals/jobs/:runId/tasks/:taskId", () =>
      HttpResponse.json({
        task: "elixir-check",
        status: "FINISHED",
        reward: 1,
        solved: true,
        rewards: {},
        verifier_output: "",
      }),
    ),
  );
  return renderApp("/evals/jobs/run-1?task=elixir-check");
}

describe("Task replay", () => {
  it("downloads only after opening and confines playback to a sandboxed frame", async () => {
    let requests = 0;
    server.use(
      http.get("*/api/evals/jobs/:runId/tasks/:taskId/replay", () => {
        requests++;
        return HttpResponse.json({
          available: true,
          html: "<html>gameplay</html>",
          partial: true,
          message: "",
        });
      }),
    );
    const { user } = taskPanel();
    const watch = await screen.findByRole("button", { name: "Watch replay" });
    expect(requests).toBe(0);
    await user.click(watch);
    const dialog = await screen.findByRole("dialog", { name: "Task replay: elixir-check" });
    expect(await within(dialog).findByText("Partial replay")).toBeInTheDocument();
    const frame = screen.getByTitle("Replay of elixir-check");
    expect(frame).toHaveAttribute("sandbox", "allow-scripts");
    expect(frame).toHaveAttribute("srcdoc", "<html>gameplay</html>");
    expect(requests).toBe(1);
    await user.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(screen.queryByTitle("Replay of elixir-check")).not.toBeInTheDocument();
  });

  it("explains missing gameplay and lets the user check again", async () => {
    let requests = 0;
    server.use(
      http.get("*/api/evals/jobs/:runId/tasks/:taskId/replay", () => {
        requests++;
        return HttpResponse.json(
          requests === 1
            ? {
                available: false,
                html: "",
                partial: false,
                message: "No game replay was saved for this task attempt.",
              }
            : { available: true, html: "gameplay", partial: false, message: "" },
        );
      }),
    );
    const { user } = taskPanel();
    await user.click(await screen.findByRole("button", { name: "Watch replay" }));
    expect(await screen.findByText("No game replay was saved for this task attempt.")).toBeInTheDocument();
    expect(screen.queryByTitle("Replay of elixir-check")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByTitle("Replay of elixir-check")).toBeInTheDocument();
    expect(requests).toBe(2);
  });

  it("shows download failures and retries them", async () => {
    let requests = 0;
    server.use(
      http.get("*/api/evals/jobs/:runId/tasks/:taskId/replay", () => {
        requests++;
        return requests === 1
          ? apiError(503, "valkyrie_network", "Transfer interrupted")
          : HttpResponse.json({ available: true, html: "gameplay", partial: false, message: "" });
      }),
    );
    const { user } = taskPanel();
    await user.click(await screen.findByRole("button", { name: "Watch replay" }));
    expect(await screen.findByText("Couldn't load the replay")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByTitle("Replay of elixir-check")).toBeInTheDocument());
  });
});
