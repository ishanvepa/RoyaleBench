import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import { fileURLToPath } from "node:url";

const repo = (path: string) => fileURLToPath(new URL(`../../${path}`, import.meta.url));

/**
 * Start every run from the same state: an empty result cache (so "cost data not downloaded yet" is something the tests
 * can rely on) and a freshly seeded throw-away arena database for the Legacy pages.
 */
export default function globalSetup() {
  rmSync(repo("runs/evals-e2e"), { recursive: true, force: true });
  // The server opens the arena database on the first Legacy request, which is after this has finished.
  execFileSync("uv", ["run", "python", "-m", "tests.seed_e2e_arena", "runs/e2e-arena/arena.db"], {
    cwd: repo(""),
    stdio: "inherit",
    shell: process.platform === "win32",
  });
}
