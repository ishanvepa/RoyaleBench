import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { environment, jobList, jobRow } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

describe("Jobs page", () => {
  it("lists jobs and sends a status filter to the API and the URL", async () => {
    const requests: URL[] = [];
    server.use(
      http.get("*/api/evals/jobs", ({ request }) => {
        requests.push(new URL(request.url));
        return HttpResponse.json(jobList([jobRow({ id: "r1", job: "alpha-run" }), jobRow({ id: "r2", job: "beta-run", status: "ERROR", score: null })]));
      }),
    );
    const { router, user } = renderApp("/evals/jobs");
    expect(await screen.findByRole("link", { name: "alpha-run" })).toHaveAttribute("href", "/evals/jobs/r1");
    expect(screen.getByText("2 jobs")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Failed" }));
    await waitFor(() => expect(router.state.location.search).toBe("?status=ERROR"));
    await waitFor(() => expect(requests.at(-1)?.searchParams.getAll("status")).toEqual(["ERROR"]));
    expect(screen.getByRole("button", { name: "Failed" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
  });

  it("restores filters from the URL on load", async () => {
    const requests: URL[] = [];
    server.use(
      http.get("*/api/evals/jobs", ({ request }) => {
        requests.push(new URL(request.url));
        return HttpResponse.json(jobList());
      }),
    );
    renderApp("/evals/jobs?status=IN_PROGRESS,STOPPING&mine=true&dataset=smoke");
    await screen.findByRole("link", { name: "smoke-run" });
    expect(screen.getByRole("button", { name: "Running" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("switch", { name: /started by me/i })).toBeChecked();
    const q = requests[0]!.searchParams;
    expect([q.getAll("status"), q.get("dataset"), q.get("mine")]).toEqual([["IN_PROGRESS", "STOPPING"], "smoke", "true"]);
  });

  it("explains an empty list and offers the next step", async () => {
    server.use(http.get("*/api/evals/jobs", () => HttpResponse.json(jobList([]))));
    renderApp("/evals/jobs");
    expect(await screen.findByText("No jobs yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /new job/i })).toHaveAttribute("href", "/evals/jobs/new");
  });

  it("shows an error with a working retry when the list cannot load", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/evals/jobs", () => (++calls === 1 ? apiError(503, "valkyrie_network", "Cannot reach Valkyrie") : HttpResponse.json(jobList()))),
    );
    const { user } = renderApp("/evals/jobs");
    expect(await screen.findByText("Couldn't load jobs")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("link", { name: "smoke-run" })).toBeInTheDocument();
  });

  it("disables New job, with the reason, when this server is read-only", async () => {
    server.use(http.get("*/api/evals/environment", () => HttpResponse.json(environment({ read_only: true }))));
    renderApp("/evals/jobs");
    await screen.findByRole("link", { name: "smoke-run" });
    await waitFor(() => expect(screen.getByRole("button", { name: /new job/i })).toBeDisabled());
    expect(screen.getByText("Read-only")).toBeInTheDocument();
  });

  it("warns that Valkyrie is unreachable and still shows what it can", async () => {
    server.use(
      http.get("*/api/evals/environment", () =>
        HttpResponse.json(environment({ valkyrie_ok: false, valkyrie_error: "Not signed in to Valkyrie.", valkyrie_error_kind: "auth", identity: null, modal_configured: false })),
      ),
    );
    renderApp("/evals/jobs");
    const banner = await screen.findByText("Not signed in to Valkyrie");
    expect(within(banner.closest("[role=alert]") as HTMLElement).getByText("Not signed in to Valkyrie.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: /new job/i })).toBeDisabled());
  });
});
