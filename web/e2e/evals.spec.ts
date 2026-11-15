import { expect, test, type Page } from "@playwright/test";

const SHOTS = process.env.RB_SCREENSHOTS === "1";
async function shot(page: Page, name: string) {
  if (SHOTS) await page.screenshot({ path: `test-results/screens/${name}.png`, fullPage: true });
}

test("opens on the Jobs page and lists the seeded runs", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/evals\/jobs$/);
  await expect(page.getByRole("heading", { name: "Jobs", level: 1 })).toBeVisible();
  await expect(page.getByText("Simulated Valkyrie")).toBeVisible();
  const rows = page.getByRole("table", { name: "Jobs" }).getByRole("row");
  await expect(rows).toHaveCount(8); // header + 7 seeded runs
  await expect(page.getByRole("link", { name: "royalebench-connection-smoke" })).toBeVisible();
  await shot(page, "01-jobs");

  await page.getByRole("link", { name: "royalebench-connection-smoke" }).click();
  await page.getByRole("button", { name: "Fetch cost data" }).click();
  await expect(page.getByText("Known for 1 of 1 tasks; excludes Modal charges")).toBeVisible();
  await expect(page.getByRole("button", { name: "Fetch cost data" })).toBeHidden();
  await shot(page, "01-job-costs");
  await page.getByRole("link", { name: "Jobs", exact: true }).last().click();
  const costedRun = page.getByRole("row", { name: /royalebench-connection-smoke/ });
  await expect(costedRun.getByTitle(/API cost known for 1 of 1 tasks/)).toContainText("$");

  // A filter lives in the URL, so it survives a reload.
  await page.getByRole("button", { name: "Failed" }).click();
  await expect(page).toHaveURL(/status=ERROR/);
  await expect(page.getByRole("table", { name: "Jobs" }).getByRole("row")).toHaveCount(2);
  await page.reload();
  await expect(page.getByRole("button", { name: "Failed" })).toHaveAttribute("aria-pressed", "true");
});

test("starts a job from the form and watches it finish", async ({ page }) => {
  await page.goto("/evals/jobs");
  await page.getByRole("link", { name: "New job" }).click();
  await expect(page).toHaveURL(/\/evals\/jobs\/new$/);
  await expect(page.getByRole("heading", { name: "New job", level: 1 })).toBeVisible();

  // Choose the published, remote-only benchmark with four tasks and run a subset.
  await page.getByLabel("Benchmark", { exact: true }).click();
  await page.getByRole("option", { name: /arena-lite/ }).click();
  await page.getByText("Select tasks").click();
  await page.getByLabel("lane-defense").check();
  await page.getByLabel("spell-timing").check();
  await expect(page.getByText("2 of 4 selected")).toBeVisible();
  await page.getByLabel("Job name").fill("e2e job");

  const review = page.getByRole("complementary", { name: "Review" });
  await expect(review.getByText("Ready")).toBeVisible();
  await expect(review.getByText("royalebench/arena-lite@1", { exact: true })).toBeVisible();
  await expect(review.getByText("valkyrie run start")).toBeVisible();
  await shot(page, "02-new-job");

  await review.getByRole("button", { name: "Start job" }).click();
  await expect(page).toHaveURL(/\/evals\/jobs\/[\w-]+$/);
  await expect(page.getByRole("heading", { name: "e2e job", level: 1 })).toBeVisible();
  await expect(page.getByText("Running", { exact: true }).first()).toBeVisible();
  await shot(page, "03-monitor-running");

  // Two tasks run side by side (concurrency 1 default is lifted by the form); the monitor polls to the end.
  await expect(page.getByText("Finished", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("table", { name: "Tasks in this run" }).getByText("lane-defense")).toBeVisible();
  await shot(page, "04-monitor-finished");

  // Selecting a task opens its panel, and the trace loads on request.
  await page.getByRole("row", { name: /lane-defense/ }).click();
  await expect(page.getByText("Verifier output")).toBeVisible();
  await page.getByRole("button", { name: "Load agent trace" }).click();
  await expect(page.getByRole("list", { name: "Agent steps" })).toBeVisible();
  await shot(page, "05-monitor-task");

  // Logs and config tabs render real content.
  await page.getByRole("tab", { name: "Logs" }).click();
  await expect(page.getByRole("log", { name: "Run logs" })).toContainText("agent started");
  await page.getByRole("tab", { name: "Config" }).click();
  await expect(page.getByText("anthropic-api-key-demo → ANTHROPIC_API_KEY")).toBeVisible();
});

test("benchmarks lead to a task page with its instruction and results", async ({ page }) => {
  await page.goto("/evals/benchmarks");
  await expect(page.getByRole("heading", { name: "Benchmarks", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Connection smoke test" })).toBeVisible();
  await expect(page.getByText("Remote only")).toBeVisible();
  await shot(page, "06-benchmarks");

  await page.getByRole("link", { name: "Connection smoke test" }).click();
  await expect(page.getByRole("heading", { name: "Connection smoke test", level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: "Publish", exact: true })).toBeVisible();
  await shot(page, "07-benchmark");

  await page.getByRole("link", { name: "elixir-check" }).first().click();
  await expect(page.getByText("Compute the remaining elixir")).toBeVisible();
  await shot(page, "08-task");
  await page.getByRole("tab", { name: "Files" }).click();
  await expect(page.getByText("tests/test.sh").first()).toBeVisible();
  await page.getByRole("tab", { name: "Results" }).click();
  await expect(page.getByRole("table", { name: "Results of every finished run on this task" })).toBeVisible();
  await shot(page, "09-task-results");
});

test("publishing an unchanged benchmark creates no new revision", async ({ page }) => {
  await page.goto("/evals/benchmarks/smoke");
  await page.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText("Nothing has changed since the latest published version")).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText(/Nothing changed: revision 1 is already up to date/)).toBeVisible();
});

test("the leaderboard sorts by any column and keeps the sort in the URL", async ({ page }) => {
  await page.goto("/evals/leaderboard");
  await expect(page.getByRole("heading", { name: "Leaderboard", level: 1 })).toBeVisible();
  const table = page.getByRole("table", { name: "Model leaderboard" });
  await expect(table.getByRole("row")).toHaveCount(5); // header + 4 models; smoke tests are hidden by default
  await shot(page, "10-leaderboard");

  await table.getByRole("button", { name: "Avg time" }).click();
  await expect(page).toHaveURL(/sort=avg_agent_s/);
  await expect(table.getByRole("columnheader", { name: /Avg time/ })).toHaveAttribute("aria-sort", /ascending|descending/);

  await page.getByRole("combobox", { name: "Sort by" }).click();
  await page.getByRole("option", { name: "Solved" }).click();
  await expect(page).toHaveURL(/sort=solved/);
  await expect(page).toHaveURL(/dir=desc/);

  await page.getByText("Include smoke tests").click();
  await expect(page).toHaveURL(/smoke=true/);

  await page.getByRole("button", { name: "Fetch cost data" }).click();
  await expect(page.getByText(/Cost data for .* hasn't been downloaded/)).toBeHidden({ timeout: 20_000 });
  await shot(page, "11-leaderboard-costs");
});

test("an unknown address shows a not-found page instead of a blank screen", async ({ page }) => {
  await page.goto("/evals/nothing-here");
  await expect(page.getByText("Page not found")).toBeVisible();
  await page.goto("/evals/jobs/00000000-0000-4000-8000-ffffffffffff");
  await expect(page.getByText(/Not found on Valkyrie/)).toBeVisible();
});
