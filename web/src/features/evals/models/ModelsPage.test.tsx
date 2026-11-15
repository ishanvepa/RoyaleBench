import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { environment, jobList, jobRow, leaderboard, leaderboardRow } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { server } from "@/test/server";

const preset = (id: string, secret_env: string, family: string) => ({ id, secret_env, family, logo_url: `/api/assets/logos/${family}` });

function stub({ secrets = ["anthropic-api-key-ishan", "modal-credentials"], valkyrie_ok = true } = {}) {
  server.use(
    http.get("*/api/evals/environment", () =>
      HttpResponse.json(
        environment({
          valkyrie_ok,
          secrets,
          settings: {
            ...environment().settings,
            models: [preset("anthropic/claude-sonnet-4-6", "ANTHROPIC_API_KEY", "claude"), preset("openai/gpt-5", "OPENAI_API_KEY", "gpt")],
          },
        }),
      ),
    ),
    http.get("*/api/evals/jobs", () =>
      HttpResponse.json(
        jobList([
          jobRow({ id: "r1", model: "anthropic/claude-sonnet-4-6", status: "IN_PROGRESS" }),
          jobRow({ id: "r2", model: "anthropic/claude-sonnet-4-6" }),
          jobRow({ id: "r3", model: "acme/model-x", family: "other", logo_url: null }),
        ]),
      ),
    ),
    http.get("*/api/evals/leaderboard", () => HttpResponse.json(leaderboard([leaderboardRow({ model: "anthropic/claude-sonnet-4-6", tasks_run: 4, solved: 3 })]))),
  );
}

const rowFor = (model: string) => within(screen.getByRole("table", { name: "Models" })).getByRole("row", { name: new RegExp(model) });
/** What a cell reads as: without the logo tiles, whose fallback letter is decorative. */
const readable = (cell: HTMLElement) => {
  const copy = cell.cloneNode(true) as HTMLElement;
  copy.querySelectorAll("[aria-hidden]").forEach((n) => n.remove());
  return copy.textContent;
};
const cells = (row: HTMLElement) => within(row).getAllByRole("cell").map(readable);
const logosIn = (el: HTMLElement) => [...el.querySelectorAll("img")].map((i) => i.getAttribute("src"));

describe("Evals models", () => {
  it("lists configured models and models only a job used, with their keys and totals", async () => {
    stub();
    renderApp("/evals/models");
    await screen.findByRole("table", { name: "Models" });

    // Model, family, provider, in evals.toml, key variable, key secret, jobs, tasks run, solved. Tasks run and
    // solved come from the leaderboard, so wait for them.
    await waitFor(() => expect(cells(rowFor("claude-sonnet-4-6"))[8]).toBe("3"));
    expect(cells(rowFor("claude-sonnet-4-6")).slice(0, 9)).toEqual(["claude-sonnet-4-6", "Claude", "anthropic", "yes", "ANTHROPIC_API_KEY", "found", "2 · 1 running", "4", "3"]);
    expect(cells(rowFor("gpt-5")).slice(0, 8)).toEqual(["gpt-5", "GPT", "openai", "yes", "OPENAI_API_KEY", "no openai secret", "0", "0"]);
    expect(cells(rowFor("model-x")).slice(0, 5)).toEqual(["model-x", "Other", "acme", "no", "–"]);
  });

  it("shows the family's logo beside its name, in the table and in the family filter", async () => {
    stub();
    const { user } = renderApp("/evals/models");
    await screen.findByRole("table", { name: "Models" });

    const familyCell = within(rowFor("gpt-5")).getAllByRole("cell")[1] as HTMLElement;
    expect(logosIn(familyCell)).toEqual(["/api/assets/logos/gpt"]);
    // A family without a logo (the model-x job's) falls back to its initial instead of a broken image.
    const other = within(rowFor("model-x")).getAllByRole("cell")[1] as HTMLElement;
    expect(logosIn(other)).toEqual([]);
    expect(other).toHaveTextContent("OOther");

    await user.click(screen.getByRole("combobox", { name: "Model family" }));
    const option = await screen.findByRole("option", { name: "Claude" });
    expect(logosIn(option)).toEqual(["/api/assets/logos/claude"]);
  });

  it("links a model's job count to the jobs filtered by that model", async () => {
    stub();
    renderApp("/evals/models");
    const link = await screen.findByRole("link", { name: "2 jobs for anthropic/claude-sonnet-4-6" });
    expect(link).toHaveAttribute("href", "/evals/jobs?model=anthropic%2Fclaude-sonnet-4-6");
  });

  it("filters by family and keeps the choice in the URL", async () => {
    stub();
    const { router, user } = renderApp("/evals/models");
    await screen.findByRole("table", { name: "Models" });
    await user.click(screen.getByRole("combobox", { name: "Model family" }));
    await user.click(await screen.findByRole("option", { name: "GPT" }));
    await waitFor(() => expect(router.state.location.search).toBe("?family=gpt"));
    const table = screen.getByRole("table", { name: "Models" });
    expect(within(table).getByRole("row", { name: /gpt-5/ })).toBeInTheDocument();
    expect(within(table).queryByRole("row", { name: /claude-sonnet-4-6/ })).toBeNull();
  });

  it("shows no verdict on keys when Valkyrie cannot be asked", async () => {
    stub({ valkyrie_ok: false, secrets: [] });
    renderApp("/evals/models");
    await screen.findByRole("table", { name: "Models" });
    expect(cells(rowFor("claude-sonnet-4-6"))[5]).toBe("–");
  });
});
