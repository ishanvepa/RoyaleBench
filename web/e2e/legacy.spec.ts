import { expect, test } from "@playwright/test";

// These run against a throw-away arena database seeded by tests/seed_e2e_arena.py (see e2e/global-setup.ts):
// a running tournament "tourney" with one finished match, a finished "battle-1", and an empty "human-play" job.

test("the Legacy leaderboard ranks the seeded players", async ({ page }) => {
  await page.goto("/legacy/leaderboard");
  await expect(page.getByRole("heading", { name: "Leaderboard", level: 1 })).toBeVisible();
  const standings = page.getByRole("table", { name: "Standings" });
  await expect(standings.getByRole("row")).toHaveCount(3); // header, model-a, model-b
  await expect(standings.getByRole("row", { name: /model-a/ })).toContainText("100%");
});

test("the overview opens a job, and the job opens a match with its replay", async ({ page }) => {
  await page.goto("/legacy/overview");
  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "tourney" }).click();
  await expect(page).toHaveURL(/\/legacy\/jobs\/tourney$/);
  await expect(page.getByRole("heading", { name: /Job: tourney/ })).toBeVisible();

  await page.getByRole("tab", { name: "Matches" }).click();
  await expect(page).toHaveURL(/tab=matches/);
  await page.getByRole("link", { name: "a-b__s1" }).click();
  await expect(page).toHaveURL(/\/legacy\/matches\/tourney\/a-b__s1$/);
  await expect(page.getByRole("heading", { name: /model-a\s*vs\s*model-b/, level: 1 })).toBeVisible();
  await expect(page.getByRole("table", { name: "Decisions" })).toBeVisible();

  // The replay viewer runs script, so it loads in a sandboxed frame.
  await page.getByRole("button", { name: "Show replay" }).click();
  const frame = page.locator("iframe[title^='Replay of']");
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts");
  await expect(page.frameLocator("iframe[title^='Replay of']").locator("body")).toContainText("tick", { timeout: 20_000 });
});

test("the model list loads from the arena configuration", async ({ page }) => {
  await page.goto("/legacy/models");
  await expect(page.getByRole("heading", { name: "Models", level: 1 })).toBeVisible();
  await expect(page.getByRole("table", { name: "Configured models" }).getByRole("row").nth(1)).toBeVisible();
});

test("builds, saves and deletes a deck", async ({ page }) => {
  await page.goto("/legacy/decks");
  await page.getByLabel("Deck name").fill("e2e deck");
  await page.getByLabel("Start from a preset").click();
  await page.getByRole("option", { name: /giant-beatdown/ }).click();
  await expect(page.getByText("8 of 8 cards chosen")).toBeVisible();
  await page.getByRole("button", { name: "Save deck" }).click();
  await expect(page).toHaveURL(/\?deck=/);
  await expect(page.getByText("Edit deck")).toBeVisible();
  await expect(page.getByRole("region", { name: "Saved decks" })).toContainText("e2e deck");

  // Leave the shared test database as it was found.
  await page.getByRole("button", { name: "Delete deck" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete deck" }).click();
  await expect(page.getByText("No custom decks yet")).toBeVisible();
});

test("plays moves against the search bot, and a reload returns to the same game", async ({ page }) => {
  await page.goto("/legacy/play");
  await page.getByRole("button", { name: "Start game" }).click();
  const board = page.getByRole("img", { name: /^Arena\./ });
  await expect(board).toBeVisible({ timeout: 30_000 });
  await expect(page).toHaveURL(/\?game=/);
  await expect(page.getByRole("region", { name: "Your hand" })).toBeVisible();

  const clock = page.getByText("Time left").locator("xpath=following-sibling::*[1]");
  const before = await clock.innerText();
  await page.getByRole("button", { name: /Wait \(save elixir\)/ }).click();
  await expect(clock).not.toHaveText(before, { timeout: 30_000 });

  await page.reload();
  await expect(board).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "New game" })).toBeVisible();

  // Leave nothing behind on the server.
  await page.getByRole("button", { name: "New game" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Abandon game" }).click();
  await expect(page.getByRole("button", { name: "Start game" })).toBeVisible();
});

test("the battle form previews how many games it would play, without starting one", async ({ page }) => {
  await page.goto("/legacy/play?mode=battle");
  await expect(page.getByText(/\d+ games?, with the models swapping sides/)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Start battle" })).toBeEnabled();
});
