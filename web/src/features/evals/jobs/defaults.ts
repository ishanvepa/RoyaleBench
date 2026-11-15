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

/** Model API keys, including the shared Modal proxy key; exclude other Modal configuration. */
export const usableSecrets = (secrets: readonly string[]) =>
  secrets.filter((s) => s === "modal-qwen-api-key" || !/modal/i.test(s));

// These configured endpoints share the Modal proxy credential.
const modalModels = new Set([
  "openai/Qwen/Qwen3.8-2.4T-A95B",
  "openai/inkling-2-small",
  "openai/deepseek-v4.1-flash-1017",
  "openai/kimi-k3.1-pro",
]);

export function defaultSecretForModel(secrets: readonly string[], model: string, identity: Environment["identity"]): string {
  if (modalModels.has(model)) return secrets.includes("modal-qwen-api-key") ? "modal-qwen-api-key" : "";
  return defaultSecret(secrets, providerOf(model), identity);
}

/** The stored secrets whose name mentions the provider (``anthropic-api-key-ishan`` for ``anthropic``). */
export function secretsForProvider(secrets: readonly string[], provider: string): string[] {
  const usable = usableSecrets(secrets);
  return provider ? usable.filter((s) => s.toLowerCase().includes(provider)) : usable;
}

/**
 * Pick the stored Valkyrie secret most likely to be the user's own key for a provider. Secrets are shared across
 * the organization and named like ``anthropic-api-key-ishan``, so prefer the one carrying the user's name.
 */
export function defaultSecret(secrets: readonly string[], provider: string, identity: Environment["identity"]): string {
  const usable = usableSecrets(secrets);
  const forProvider = secretsForProvider(secrets, provider);
  const pool = forProvider.length > 0 ? forProvider : usable;
  const tokens = [identity?.name?.split(/\s+/)[0], identity?.email?.split("@")[0]]
    .filter((t): t is string => Boolean(t))
    .map((t) => t.toLowerCase());
  const mine = pool.find((s) => tokens.some((t) => s.toLowerCase().endsWith(t) || s.toLowerCase().includes(`-${t}`)));
  return mine ?? pool[0] ?? "";
}
