import type { Environment } from "@/api/types";

/** Value of the model picker that means "type a model key yourself". */
export const CUSTOM_MODEL = "__custom__";

/** "anthropic/claude-sonnet-4-6" -> "anthropic" */
export function providerOf(model: string): string {
  const slash = model.indexOf("/");
  return slash > 0 ? model.slice(0, slash).toLowerCase() : "";
}

const pad = (n: number) => String(n).padStart(2, "0");

/** "<benchmark>-<model>-<YYYYMMDD-HHMM>", the name a job gets unless the user types one. */
export function defaultLabel(dataset: string, model: string, now: Date = new Date()): string {
  const short = (model.split("/").pop() ?? "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "model";
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
  return `${dataset || "job"}-${short}-${stamp}`;
}

/**
 * Pick the stored Valkyrie secret most likely to be the user's own key for a provider. Secrets are shared across
 * the organization and named like ``anthropic-api-key-ishan``, so prefer the one carrying the user's name.
 */
export function defaultSecret(secrets: readonly string[], provider: string, identity: Environment["identity"]): string {
  const usable = secrets.filter((s) => !/modal/i.test(s));
  const forProvider = provider ? usable.filter((s) => s.toLowerCase().includes(provider)) : usable;
  const pool = forProvider.length > 0 ? forProvider : usable;
  const tokens = [identity?.name?.split(/\s+/)[0], identity?.email?.split("@")[0]]
    .filter((t): t is string => Boolean(t))
    .map((t) => t.toLowerCase());
  const mine = pool.find((s) => tokens.some((t) => s.toLowerCase().endsWith(t) || s.toLowerCase().includes(`-${t}`)));
  return mine ?? pool[0] ?? "";
}
