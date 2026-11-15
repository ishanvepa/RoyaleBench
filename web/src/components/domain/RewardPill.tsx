import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { formatReward } from "@/lib/format";

/** Shows binary task outcomes as an at-a-glance verdict while preserving partial rewards. */
export function RewardPill({ reward, className }: { reward: number | null | undefined; className?: string }) {
  if (reward === 1) return <Badge tone="success" className={className}>Pass</Badge>;
  if (reward === 0) return <Badge tone="danger" className={className}>Fail</Badge>;
  return <span className={cn("tabular-nums", className)}>{formatReward(reward)}</span>;
}
