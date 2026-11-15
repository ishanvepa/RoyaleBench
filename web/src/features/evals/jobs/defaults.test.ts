import { describe, expect, it } from "vitest";
import { defaultLabel, defaultSecret, providerOf } from "./defaults";

const identity = (name: string | null, email: string | null) => ({ organization: "org", name, email, credential: "login" });

describe("defaultSecret", () => {
  const secrets = ["modal-credentials", "anthropic-api-key-ben", "anthropic-api-key-ishan", "openai-api-key-ishan"];

  it("prefers the secret that carries the user's name, for the right provider", () => {
    expect(defaultSecret(secrets, "anthropic", identity("Ishan", "ishanvepa171@gmail.com"))).toBe("anthropic-api-key-ishan");
    expect(defaultSecret(secrets, "anthropic", identity("Ben", null))).toBe("anthropic-api-key-ben");
    expect(defaultSecret(secrets, "openai", identity("Ishan", null))).toBe("openai-api-key-ishan");
  });

  it("uses the email name when the profile has no name, and never picks the Modal credentials", () => {
    expect(defaultSecret(secrets, "anthropic", identity(null, "ben@example.com"))).toBe("anthropic-api-key-ben");
    expect(defaultSecret(["modal-credentials"], "anthropic", null)).toBe("");
  });

  it("falls back to any non-Modal secret when none mention the provider", () => {
    expect(defaultSecret(["modal-credentials", "shared-key"], "acme", null)).toBe("shared-key");
  });
});

describe("defaultLabel and providerOf", () => {
  it("builds <benchmark>-<model>-<timestamp>", () => {
    expect(defaultLabel("smoke", "anthropic/claude-sonnet-4-6", new Date(2026, 10, 14, 9, 5))).toBe("smoke-claude-sonnet-4-6-20261114-0905");
    expect(defaultLabel("", "", new Date(2026, 0, 2, 3, 4))).toBe("job-model-20260102-0304");
  });
  it("reads the provider from a model key", () => {
    expect(providerOf("Anthropic/claude")).toBe("anthropic");
    expect(providerOf("no-slash")).toBe("");
  });
});
