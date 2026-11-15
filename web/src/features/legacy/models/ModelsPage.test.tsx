import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { CommandStatus, ModelRow } from "@/api/types";
import { modelRow } from "@/test/legacyFixtures";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

const idle: CommandStatus = { name: "models", state: "idle", exit_code: null, output: "" };
let models: ModelRow[];
let check: CommandStatus;
let starts: number;
let modelFetches: number;

function useModelHandlers() {
  server.use(
    http.get("*/api/legacy/models", () => {
      modelFetches += 1;
      return HttpResponse.json({ models, config_name: "config.toml" });
    }),
    http.get("*/api/legacy/models/check", () => HttpResponse.json(check)),
    http.post("*/api/legacy/models/check", () => {
      starts += 1;
      check = { name: "models", state: "running", exit_code: null, output: "checking gpt-5 …\n" };
      return HttpResponse.json(check);
    }),
  );
}

beforeEach(() => {
  models = [
    modelRow({ name: "gpt-5", family: "gpt" }),
    modelRow({ name: "claude-opus-5.5", family: "claude", provider: "anthropic", model: "claude-opus-5-5", key_env: "ANTHROPIC_API_KEY", price_in: 4, price_out: 20, games: 0, wins: 0 }),
    modelRow({ name: "gemini-4", family: "gemini", provider: "openai_compat", model: "google/gemini-4", key_env: "OPENROUTER_API_KEY", key_ok: false, effort: "" }),
    modelRow({ name: "heuristic-bot", family: "bot", type: "heuristic", provider: "", model: "", effort: "", key_env: null, key_ok: null, price_in: null, price_out: null, games: 0, wins: 0 }),
  ];
  check = idle;
  starts = 0;
  modelFetches = 0;
});

const rowOf = (name: string) => screen.getByRole("row", { name: new RegExp(`^${name}\\b`) });

describe("Models page", () => {
  it("lists every configured player with its provider, key state and price", async () => {
    useModelHandlers();
    renderApp("/legacy/models");
    expect(await screen.findByRole("row", { name: /^gpt-5/ })).toBeInTheDocument();
    expect(within(rowOf("gpt-5")).getByText("set")).toBeInTheDocument();
    expect(within(rowOf("gpt-5")).getByText("1.25/10")).toBeInTheDocument();
    expect(within(rowOf("claude-opus-5.5")).getByText("4/20")).toBeInTheDocument();
    expect(within(rowOf("gemini-4")).getByText("OPENROUTER_API_KEY missing")).toBeInTheDocument();
    expect(within(rowOf("heuristic-bot")).getAllByText("–").length).toBeGreaterThan(2); // no key, price or model id for a bot
    expect(screen.getByText(/From config\.toml/)).toBeInTheDocument();
  });

  it("filters by model family, and keeps the filter in the address", async () => {
    useModelHandlers();
    const { router, user } = renderApp("/legacy/models");
    await screen.findByRole("row", { name: /^gpt-5/ });
    await user.click(screen.getByRole("combobox", { name: "Model family" }));
    await user.click(await screen.findByRole("option", { name: "Claude" }));
    await waitFor(() => expect(screen.queryByRole("row", { name: /^gpt-5/ })).not.toBeInTheDocument());
    expect(screen.getByRole("row", { name: /^claude-opus-5\.5/ })).toBeInTheDocument();
    expect(router.state.location.search).toBe("?family=claude");

    await user.click(screen.getByRole("combobox", { name: "Model family" }));
    await user.click(await screen.findByRole("option", { name: "All families" }));
    expect(await screen.findByRole("row", { name: /^gpt-5/ })).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
  });

  it("opens already filtered from a shared link", async () => {
    useModelHandlers();
    renderApp("/legacy/models?family=bot");
    expect(await screen.findByRole("row", { name: /^heuristic-bot/ })).toBeInTheDocument();
    expect(screen.queryByRole("row", { name: /^gpt-5/ })).not.toBeInTheDocument();
  });

  it("shows how each model last answered a check", async () => {
    models = [
      modelRow({ name: "gpt-5", check_ok: true, check_detail: "replied in 0.8s", checked_at: Date.now() / 1000 - 120 }),
      modelRow({ name: "gemini-4", family: "gemini", check_ok: false, check_detail: "401 Unauthorized", checked_at: Date.now() / 1000 - 7200 }),
    ];
    useModelHandlers();
    renderApp("/legacy/models");
    const ok = await screen.findByRole("row", { name: /^gpt-5/ });
    expect(within(ok).getByText("ok")).toBeInTheDocument();
    expect(within(ok).getByText("2 min ago")).toBeInTheDocument();
    expect(within(ok).getByText("ok").closest("span[title]")).toHaveAttribute("title", "replied in 0.8s");
    const bad = rowOf("gemini-4");
    expect(within(bad).getByText("failed")).toBeInTheDocument();
    expect(within(bad).getByText("2 h ago")).toBeInTheDocument();
  });

  it("runs a model check, follows its output, and refreshes the table when it finishes", async () => {
    useModelHandlers();
    const { user } = renderApp("/legacy/models");
    await screen.findByRole("row", { name: /^gpt-5/ });
    expect(within(rowOf("gpt-5")).queryByText("ok")).not.toBeInTheDocument();
    const before = modelFetches;

    await user.click(screen.getByRole("button", { name: "Run model check" }));
    expect(await screen.findByText("Model check (running…)")).toBeInTheDocument();
    expect(screen.getByText(/checking gpt-5/)).toBeInTheDocument();
    expect(starts).toBe(1);
    expect(screen.getByRole("button", { name: "Run model check" })).toBeDisabled(); // no second check while one runs

    // The next poll finds it finished, with new results in the table.
    models = [modelRow({ name: "gpt-5", check_ok: true, check_detail: "replied", checked_at: Date.now() / 1000 })];
    check = { name: "models", state: "done", exit_code: 0, output: "checking gpt-5 …\ngpt-5: ok\n" };
    expect(await screen.findByText("Model check (finished)", {}, { timeout: 5_000 })).toBeInTheDocument();
    expect(screen.getByText(/gpt-5: ok/)).toBeInTheDocument();
    await waitFor(() => expect(within(rowOf("gpt-5")).getByText("ok")).toBeInTheDocument());
    expect(modelFetches).toBeGreaterThan(before);
    expect(screen.getByRole("button", { name: "Run model check" })).toBeEnabled();
  }, 12_000);

  it("reports a check that failed", async () => {
    check = { name: "models", state: "failed", exit_code: 1, output: "Traceback: boom" };
    useModelHandlers();
    renderApp("/legacy/models");
    expect(await screen.findByText("Model check (failed)")).toBeInTheDocument();
    expect(screen.getByText("Traceback: boom")).toBeInTheDocument();
  });

  it("cannot start a check on a read-only server", async () => {
    useModelHandlers();
    server.use(http.get("*/api/health", () => HttpResponse.json({ status: "ok", read_only: true, fake: false })));
    renderApp("/legacy/models");
    await screen.findByRole("row", { name: /^gpt-5/ });
    await waitFor(() => expect(screen.getByRole("button", { name: "Run model check" })).toBeDisabled());
  });

  it("explains an unreachable arena database instead of showing an empty table", async () => {
    useModelHandlers();
    server.use(http.get("*/api/legacy/models", () => apiError(503, "database_unavailable", "Cannot open the arena database")));
    renderApp("/legacy/models");
    expect(await screen.findByText("Couldn't load the models")).toBeInTheDocument();
    expect(screen.getByText(/Cannot open the arena database/)).toBeInTheDocument();
  });
});
