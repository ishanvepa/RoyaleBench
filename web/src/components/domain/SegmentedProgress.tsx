import { cn } from "@/lib/cn";
import { statusMeta, TASK_PROGRESS_ORDER } from "@/lib/status";

interface SegmentedProgressProps {
  /** Task counts by status, as the API reports them. */
  counts: Record<string, number>;
  /** Defaults to the sum of the counts. */
  total?: number;
  /** List each status with its count under the bar. */
  legend?: boolean;
  className?: string;
}

/** A bar split by task status: how much is done, in flight, waiting, and failed. */
export function SegmentedProgress({ counts, total, legend = false, className }: SegmentedProgressProps) {
  const sum = Object.values(counts).reduce((a, b) => a + b, 0);
  const denominator = Math.max(total ?? sum, sum, 1);
  const known = TASK_PROGRESS_ORDER.filter((s) => (counts[s] ?? 0) > 0);
  const others = Object.keys(counts).filter((s) => !(TASK_PROGRESS_ORDER as readonly string[]).includes(s) && (counts[s] ?? 0) > 0);
  const order = [...known, ...others];
  const description = order.map((s) => `${counts[s]} ${statusMeta("task", s).label.toLowerCase()}`).join(", ") || "no tasks";

  return (
    <div className={className}>
      <div role="img" aria-label={`Tasks: ${description}`} className="flex h-2 w-full gap-px overflow-hidden rounded-full bg-selected">
        {order.map((status) => (
          <div key={status} className={cn("h-full transition-[width] duration-500", statusMeta("task", status).bar)} style={{ width: `${((counts[status] ?? 0) / denominator) * 100}%` }} />
        ))}
      </div>
      {legend ? (
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {order.map((status) => (
            <li key={status} className="flex items-center gap-1.5">
              <span aria-hidden className={cn("size-2 rounded-full", statusMeta("task", status).bar)} />
              <span className="tabular-nums text-subtle">{counts[status]}</span> {statusMeta("task", status).label.toLowerCase()}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** A compact bar with "3/10" beside it, for table cells. */
export function ProgressCell({ done, total, counts }: { done: number; total: number; counts: Record<string, number> }) {
  return (
    <div className="flex min-w-[130px] items-center gap-2">
      <SegmentedProgress counts={counts} total={total} className="w-20 shrink-0" />
      <span className="tabular-nums text-xs text-subtle">
        {done}/{total}
      </span>
    </div>
  );
}
