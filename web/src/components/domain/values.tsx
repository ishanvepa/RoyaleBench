import { DASH, formatDateTime, formatDuration, formatMoney, formatRelative, formatScore, parseDate } from "@/lib/format";

export function Duration({ seconds }: { seconds: number | null | undefined }) {
  return <span className="tabular-nums">{formatDuration(seconds)}</span>;
}

export function Money({ usd }: { usd: number | null | undefined }) {
  return usd == null ? <span className="text-muted">{DASH}</span> : <span className="tabular-nums">{formatMoney(usd)}</span>;
}

export function Score({ value }: { value: number | null | undefined }) {
  return value == null ? <span className="text-muted">{DASH}</span> : <span className="tabular-nums">{formatScore(value)}</span>;
}

/** "5 min ago", with the exact time on hover. */
export function RelativeTime({ value }: { value: string | Date | null | undefined }) {
  const date = parseDate(value);
  if (!date) return <span className="text-muted">{DASH}</span>;
  return (
    <time dateTime={date.toISOString()} title={formatDateTime(date)} className="whitespace-nowrap">
      {formatRelative(date)}
    </time>
  );
}

/** A label/value list for detail panels. */
export function KeyValues({ items }: { items: { label: string; value: React.ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-[13px]">
      {items.map((item) => (
        <div key={item.label} className="contents">
          <dt className="text-muted">{item.label}</dt>
          <dd className="min-w-0 break-words">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
