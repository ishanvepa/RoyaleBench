import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface MetricProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  className?: string;
}

/** A labelled number in a bordered tile. */
export function Metric({ label, value, hint, className }: MetricProps) {
  return (
    <div className={cn("rounded-xl border border-line bg-surface px-4 py-3.5", className)}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 font-display text-2xl font-medium leading-none tabular-nums">{value}</dd>
      {hint ? <p className="mt-1.5 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}
