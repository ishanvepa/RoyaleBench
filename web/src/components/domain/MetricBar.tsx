import { DASH } from "@/lib/format";

/** A number with a small proportional bar beside it. ``max`` is the value that fills the bar. */
export function MetricBar({ value, max, color, text }: { value: number | null | undefined; max: number; color: string; text: string }) {
  if (value === null || value === undefined) return <span className="text-muted">{DASH}</span>;
  const width = Math.max(0, Math.min(1, max > 0 ? value / max : 0)) * 100;
  return (
    <span className="inline-flex items-center gap-2">
      <span className="min-w-[44px] text-right tabular-nums">{text}</span>
      <span aria-hidden className="relative h-2 w-16 overflow-hidden rounded bg-line">
        <span className="absolute inset-y-0 left-0 block rounded" style={{ width: `${width}%`, background: `color-mix(in srgb, ${color} 65%, transparent)` }} />
      </span>
    </span>
  );
}
