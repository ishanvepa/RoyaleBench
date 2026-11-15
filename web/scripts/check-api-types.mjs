// Fails when src/api/schema.d.ts is out of date with rb_server/openapi.json.
// Regenerate with `npm run gen:api` (after `uv run python -m rb_server.export_openapi` when the API changed).
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const tmp = mkdtempSync(join(tmpdir(), "rb-api-"));
const out = join(tmp, "schema.d.ts");
const bin = join(root, "node_modules", "openapi-typescript", "bin", "cli.js");
const normalize = (text) => text.replace(/\r\n/g, "\n");

try {
  execFileSync(process.execPath, [bin, join(root, "..", "rb_server", "openapi.json"), "-o", out], { stdio: "pipe" });
  const fresh = normalize(readFileSync(out, "utf8"));
  const committed = normalize(readFileSync(join(root, "src", "api", "schema.d.ts"), "utf8"));
  if (fresh !== committed) {
    console.error("src/api/schema.d.ts is stale. Run `npm run gen:api`.");
    process.exit(1);
  }
  console.log("API types are up to date.");
} finally {
  rmSync(tmp, { recursive: true, force: true });
}
