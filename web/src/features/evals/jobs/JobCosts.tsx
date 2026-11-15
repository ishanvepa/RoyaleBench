import type { JobRow } from "@/api/types";
import { Money } from "@/components/domain/values";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { plural } from "@/lib/format";
import { ALL_RESULTS, useCostsDownload } from "../api/leaderboard";

export function RunCost({ job }: { job: JobRow }) {
  return (
    <span title={`API cost known for ${job.cost_known ?? 0} of ${job.total} tasks; excludes Modal charges`}>
      <Money usd={job.cost_usd} />
      {job.cost_usd != null && (job.cost_known ?? 0) < job.total ? <span className="text-muted">*</span> : null}
    </span>
  );
}

export function JobCosts({ jobs }: { jobs: JobRow[] }) {
  const costs = useCostsDownload(ALL_RESULTS, jobs.map((j) => j.id));
  const pending = jobs.reduce((sum, j) => sum + (j.costs_pending ?? 0), 0);
  const running = costs.status?.state === "running";
  const error = costs.start.error?.message ?? (costs.status?.state === "error" ? costs.status.error : null);
  if (!pending && !running && !error) return null;
  return (
    <Banner tone={error ? "danger" : "neutral"} title={running ? "Downloading cost data…" : error ? "Couldn't download cost data" : "API cost data available"} className="mb-4">
      {running ? `${costs.status?.done ?? 0} of ${costs.status?.total ?? 0} tasks processed.` : error ?? `Download outputs for ${plural(pending, "task")} in finished runs. Excludes Modal charges.`}
      {!running ? <Button size="sm" variant="secondary" className="ml-2" onClick={() => costs.start.mutate()} loading={costs.start.isPending}>
        {error ? "Retry cost download" : "Fetch cost data"}
      </Button> : null}
    </Banner>
  );
}
