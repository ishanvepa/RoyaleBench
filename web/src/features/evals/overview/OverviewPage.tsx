import { ArrowRight, Rocket } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { isActiveRun, type JobRow, type LeaderboardRow } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Money } from "@/components/domain/values";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { Metric } from "@/components/ui/metric";
import { PageHeader } from "@/components/ui/page-header";
import { DASH, formatNumber, formatPercent, plural } from "@/lib/format";
import { ALL_JOBS, useJobs } from "../api/jobs";
import { ALL_RESULTS, useLeaderboard } from "../api/leaderboard";
import { jobColumns } from "../jobs/columns";
import { ModalBilling } from "./ModalBilling";

/** How many jobs the table below the totals shows; the Jobs page has the rest. */
const RECENT = 10;

const COLUMNS = [jobColumns.status, jobColumns.job, jobColumns.benchmark, jobColumns.model, jobColumns.progress, jobColumns.score, jobColumns.cost, jobColumns.started, jobColumns.duration];

const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);
const startedAt = (job: JobRow) => (job.started_at ? Date.parse(job.started_at) : 0);

/** What the finished runs scored, summed over every (model, harness) row of the leaderboard. */
function resultTotals(rows: LeaderboardRow[]) {
  const withCost = rows.filter((r) => r.cost_usd != null);
  return {
    tasks: sum(rows.map((r) => r.tasks_run)),
    solved: sum(rows.map((r) => r.solved)),
    cost: withCost.length > 0 ? sum(withCost.map((r) => r.cost_usd ?? 0)) : null,
    costKnown: sum(rows.map((r) => r.cost_known)),
  };
}

export function Component() {
  const jobs = useJobs(ALL_JOBS);
  const results = useLeaderboard(ALL_RESULTS);

  return (
    <div>
      <PageHeader title="Overview" description="Every Valkyrie run on this benchmark: how far they have got, how many tasks they solved, and what the models cost." />
      <QueryBoundary query={jobs} errorTitle="Couldn't load the overview">
        {(data) => <Body jobs={data.jobs} results={results} />}
      </QueryBoundary>
    </div>
  );
}

function Body({ jobs, results }: { jobs: JobRow[]; results: ReturnType<typeof useLeaderboard> }) {
  const navigate = useNavigate();
  const running = jobs.filter((j) => isActiveRun(j.status)).length;
  const totals = results.data ? resultTotals(results.data.rows) : null;
  const recent = [...jobs].sort((a, b) => startedAt(b) - startedAt(a)).slice(0, RECENT);

  // The solved and spend tiles come from the leaderboard, a heavier request than the job list, so they fill in
  // when it arrives (or say why they cannot) instead of holding the whole page back.
  let solvedHint: ReactNode = "Graded tasks in finished runs, smoke tests included";
  let costHint: ReactNode = "Harness API costs and Modal inference tokens; excludes infrastructure charges";
  if (!totals) {
    solvedHint = costHint = results.isError ? "Couldn't load results" : "Loading results…";
  } else if (totals.tasks === 0) {
    solvedHint = "No finished runs yet";
  } else {
    solvedHint = `${formatPercent(totals.solved / totals.tasks)} of graded tasks`;
    if (totals.costKnown < totals.tasks) {
      costHint = (
        <>
          Known for {totals.costKnown} of {totals.tasks} tasks.{" "}
          <Link to="/evals/leaderboard?smoke=true" className="underline underline-offset-4 hover:text-ink">
            Fetch the rest
          </Link>
        </>
      );
    }
  }

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Jobs (running)" value={`${jobs.length} (${running})`} />
        <Metric label="Tasks finished" value={`${formatNumber(sum(jobs.map((j) => j.done)))} / ${formatNumber(sum(jobs.map((j) => j.total)))}`} hint="Across every job, including ones still running" />
        <Metric label="Tasks solved" value={totals ? `${formatNumber(totals.solved)} / ${formatNumber(totals.tasks)}` : DASH} hint={solvedHint} />
        <Metric label="Est. API spend" value={<Money usd={totals?.cost} />} hint={costHint} />
      </dl>
      <ModalBilling />
      <section aria-labelledby="recent-jobs" className="space-y-3">
        <div className="flex items-baseline justify-between gap-4">
          <h2 id="recent-jobs" className="text-base">
            Recent jobs
          </h2>
          {jobs.length > RECENT ? (
            <Link to="/evals/jobs" className="inline-flex items-center gap-1 text-[13px] text-subtle underline-offset-4 hover:text-ink hover:underline">
              All {plural(jobs.length, "job")} <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          ) : null}
        </div>
        <DataTable
          caption="Recent jobs"
          columns={COLUMNS}
          data={recent}
          getRowId={(r) => r.id}
          initialSorting={[{ id: "started", desc: true }]}
          onRowClick={(row) => void navigate(`/evals/jobs/${row.id}`)}
          empty={
            <EmptyState
              icon={<Rocket className="size-6" aria-hidden />}
              title="No jobs yet"
              description="Start a job to run a model on a benchmark through Valkyrie. It appears here and updates live."
              action={
                <Link to="/evals/jobs/new" className="text-[13px] underline underline-offset-4">
                  New job
                </Link>
              }
              className="border-0"
            />
          }
        />
      </section>
    </div>
  );
}
