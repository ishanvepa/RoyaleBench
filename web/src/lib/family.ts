/** CSS colour (a theme-aware variable) for a provider family such as "claude" or "gpt". Unknown families fall back to neutral. */
const KNOWN = new Set(["claude", "gpt", "gemini", "grok", "deepseek", "mistral", "llama", "qwen", "bot", "other"]);

export function familyColor(family: string): string {
  return `var(--rb-f-${KNOWN.has(family) ? family : "other"})`;
}
