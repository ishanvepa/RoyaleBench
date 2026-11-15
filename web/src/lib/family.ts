/** CSS colour (a theme-aware variable) for a provider family such as "claude" or "gpt". Unknown families fall back to neutral. */
const KNOWN = new Set(["claude", "gpt", "gemini", "grok", "deepseek", "mistral", "llama", "qwen", "inkling", "kimi", "bot", "other"]);

export function familyColor(family: string): string {
  return `var(--rb-f-${KNOWN.has(family) ? family : "other"})`;
}

const LABELS: Record<string, string> = {
  gpt: "GPT",
  claude: "Claude",
  gemini: "Gemini",
  grok: "Grok",
  deepseek: "DeepSeek",
  mistral: "Mistral",
  llama: "Llama",
  qwen: "Qwen",
  inkling: "Inkling",
  kimi: "Kimi",
  bot: "Baseline bots",
  other: "Other",
};

/** "claude" -> "Claude". Unknown families are shown as they are. */
export function familyLabel(family: string): string {
  return LABELS[family] ?? family;
}
