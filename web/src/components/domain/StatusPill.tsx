import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { statusMeta } from "@/lib/status";

/** A run, task or arena job/match status as an icon + word (never colour alone). */
export function StatusPill({ kind, status, className }: { kind: "run" | "task" | "arena"; status: string; className?: string }) {
  const meta = statusMeta(kind, status);
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} className={className}>
      <Icon className={cn("size-3", meta.spin && "animate-spin")} aria-hidden />
      {meta.label}
    </Badge>
  );
}
