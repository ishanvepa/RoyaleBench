import { Link, useParams } from "react-router";
import { z } from "zod";
import type { JobDetail } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { SegmentedProgress } from "@/components/domain/SegmentedProgress";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration, Score } from "@/components/domain/values";
import { Banner } from "@/components/ui/banner";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { Metric } from "@/components/ui/metric";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { enumParam, stringParam, useSearchState } from "@/hooks/useSearchState";
import { useNow } from "@/hooks/useNow";
import { formatDuration, harnessName, plural, shortId } from "@/lib/format";
import { useJob } from "../api/jobs";
import { ConfigTab } from "./monitor/ConfigTab";
import { ErrorsTab } from "./monitor/ErrorsTab";
import { JobActions } from "./monitor/JobActions";
import { LogsTab } from "./monitor/LogsTab";
import { TasksTab } from "./monitor/TasksTab";

const TABS = ["tasks", "logs", "errors", "config"] as const;
const searchSchema = z.object({ tab: enumParam(TABS, "tasks"), task: stringParam() });

export function Component() {
  const { runId = "" } = useParams();
  const job = useJob(runId);
  return (
    <div>
      <Breadcrumbs items={[{ label: "Jobs", to: "/evals/jobs" }, { label: job.data?.job.job ?? shortId(runId) }]} />
      <QueryBoundary query={job} errorTitle="Couldn't load this job">
        {(detail) => <Monitor detail={detail} />}
      </QueryBoundary>
    </div>
  );
}

function Monitor({ detail }: { detail: JobDetail }) {
  const { job } = detail;
  const [state, setState] = useSearchState(searchSchema);
  const now = useNow(1000, detail.active);
  const started = job.started_at ? Date.parse(job.started_at) : null;
  const elapsed = detail.active && started !== null ? Math.max(0, (now - started) / 1000) : job.duration_s;

  const timeLeft = detail.active ? (detail.eta_s != null ? `~${formatDuration(detail.eta_s)}` : "Estimating…") : "–";
  const queueHint = detail.queue?.position
    ? `Next task is #${detail.queue.position} in the Modal queue`
    : detail.queue?.waiting
      ? `${plural(detail.queue.waiting, "task")} waiting for a sandbox`
      : undefined;

  return (
    <>
      <PageHeader
        title={job.job}
        meta={<StatusPill kind="run" status={job.status} />}
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <ModelLabel model={job.model} logoUrl={job.logo_url} />
            <span aria-hidden>·</span>
            <span>{harnessName(job.harness)}</span>
            <span aria-hidden>·</span>
            {job.dataset ? (
              <Link to={`/evals/benchmarks/${job.dataset}`} className="underline underline-offset-4 hover:text-ink">
                {detail.dataset_version || job.dataset}
              </Link>
            ) : null}
            <span aria-hidden>·</span>
            <span>Modal</span>
          </span>
        }
        actions={<JobActions detail={detail} />}
      />

      {job.status === "ERROR" && job.error ? (
        <Banner tone="danger" title="This run failed" className="mb-5">
          <span className="line-clamp-3 whitespace-pre-wrap">{job.error}</span>
        </Banner>
      ) : null}

      <dl className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Tasks done" value={`${job.done}/${job.total}`} hint={detail.concurrency ? `Concurrency ${detail.concurrency}` : undefined} />
        <Metric label="Score" value={<Score value={job.score} />} hint={job.score == null ? "Shown when the run finishes" : undefined} />
        <Metric label={detail.active ? "Elapsed" : "Duration"} value={<Duration seconds={elapsed} />} />
        <Metric label="Time left" value={timeLeft} hint={queueHint} />
      </dl>
      <SegmentedProgress counts={job.task_state_counts} total={job.total} legend className="mb-8" />

      <Tabs value={state.tab} onValueChange={(tab) => setState({ tab: tab as (typeof TABS)[number] })}>
        <TabsList aria-label="Job details">
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
          <TabsTrigger value="errors">Errors</TabsTrigger>
          <TabsTrigger value="config">Config</TabsTrigger>
        </TabsList>
        <TabsContent value="tasks">
          <TasksTab detail={detail} runId={job.id} selected={state.task} onSelect={(task) => setState({ task })} />
        </TabsContent>
        <TabsContent value="logs">
          <LogsTab runId={job.id} active={detail.active} />
        </TabsContent>
        <TabsContent value="errors">
          <ErrorsTab runId={job.id} />
        </TabsContent>
        <TabsContent value="config">
          <ConfigTab detail={detail} />
        </TabsContent>
      </Tabs>
    </>
  );
}
