/** Display formatting. Every function accepts null/undefined and returns the "no value" dash for it. */

export const DASH = "–";

type Maybe<T> = T | null | undefined;

export function formatDuration(seconds: Maybe<number>): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return DASH;
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m ${String(s).padStart(2, "0")}s`;
  return `${s}s`;
}

/** USD with enough precision for model costs, which are usually cents or fractions of a cent. */
export function formatMoney(usd: Maybe<number>): string {
  if (usd == null || !Number.isFinite(usd)) return DASH;
  if (usd === 0) return "$0";
  const digits = Math.abs(usd) < 0.01 ? 4 : Math.abs(usd) < 1 ? 3 : 2;
  return `$${usd.toFixed(digits)}`;
}

/** A 0..1 fraction as a percentage. Decimals appear only when needed, so 0.75 is "75%" and 2/3 is "66.7%". */
export function formatPercent(fraction: Maybe<number>): string {
  if (fraction == null || !Number.isFinite(fraction)) return DASH;
  const pct = Math.round(fraction * 1000) / 10;
  return `${Number.isInteger(pct) ? pct : pct.toFixed(1)}%`;
}

/** A score that is already 0..100 (Valkyrie's final_score). */
export function formatScore(score: Maybe<number>): string {
  if (score == null || !Number.isFinite(score)) return DASH;
  return `${Number.isInteger(score) ? score : score.toFixed(1)}%`;
}

/** A task reward (0..1): "1.0", "0.5", "0.25". */
export function formatReward(reward: Maybe<number>): string {
  if (reward == null || !Number.isFinite(reward)) return DASH;
  return Number.isInteger(reward) ? reward.toFixed(1) : String(Number(reward.toFixed(3)));
}

export function formatNumber(n: Maybe<number>): string {
  if (n == null || !Number.isFinite(n)) return DASH;
  return n.toLocaleString("en-US");
}

export function formatBytes(bytes: Maybe<number>): string {
  if (bytes == null || !Number.isFinite(bytes)) return DASH;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function parseDate(value: Maybe<string | Date>): Date | null {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** "just now", "5 min ago", "3 h ago", "2 d ago", then a calendar date. */
export function formatRelative(value: Maybe<string | Date>, now: number = Date.now()): string {
  const d = parseDate(value);
  if (!d) return DASH;
  const diff = now - d.getTime();
  if (diff < 0) return formatDateTime(d);
  if (diff < 45_000) return "just now";
  if (diff < HOUR) return `${Math.max(1, Math.round(diff / MINUTE))} min ago`;
  if (diff < DAY) return `${Math.round(diff / HOUR)} h ago`;
  if (diff < 7 * DAY) return `${Math.round(diff / DAY)} d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatDateTime(value: Maybe<string | Date>): string {
  const d = parseDate(value);
  if (!d) return DASH;
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** The tail of an id that is long enough to tell runs apart. */
export function shortId(id: string): string {
  return id.length > 12 ? id.slice(0, 8) : id;
}

/** "anthropic/claude-sonnet-4-6" -> "claude-sonnet-4-6" */
export function modelName(model: string): string {
  const i = model.lastIndexOf("/");
  return i >= 0 ? model.slice(i + 1) : model;
}

/** "claude_code-v1.0.0" -> "claude_code" */
export function harnessName(harness: string): string {
  return harness.replace(/-v\d[\w.]*$/, "");
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
}
