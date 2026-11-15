import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { z } from "zod";
import type { JobReport } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration, Money } from "@/components/domain/values";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { Metric } from "@/components/ui/metric";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { enumParam, listParam, stringParam, useSearchState } from "@/hooks/useSearchState";
import { formatDuration } from "@/lib/format";
import { useJobReport, useJobSummaries } from "../api/jobs";
import { HeadToHeadGrid } from "./HeadToHeadGrid";
import { MatchesTab } from "./MatchesTab";
import { EndingBars, MetricsTable, StandingsTable, WinTable } from "./JobTables";

const TABS = ["leaderboard", "winrates", "metrics", "matches", "config"] as const;
const searchSchema = z.object({
  tab: enumParam(TABS, "leaderboard"),
  status: listParam(),
  player: stringParam(),
  page: z.coerce.number().int().min(1).optional().catch(1).transform((v) => v ?? 1),
});

export function Component() {
  const { job = "" } = useParams();
  const [live, setLive] = useState(true);
  const report = useJobReport(job, live);
  const summaries = useJobSummaries();
  const navigate = useNavigate();
  return (
    <div>
      <Breadcrumbs items={[{ label: "Overview", to: "/legacy/overview" }, { label: job }]} />
      <PageHeader
        title={`Job: ${job}`}
        description={report.data?.notes || undefined}
        meta={report.data ? <StatusPill kind="arena" status={report.data.status} /> : null}
        actions={
          <>
            <div className="w-64">
              <Select
                aria-label="Switch job"
                value={job}
                onValueChange={(name) => void navigate(`/legacy/jobs/${name}`)}
                options={(summaries.data?.jobs ?? [{ name: job, status: "", created_at: null, total_matches: 0 }]).map((j) => ({ value: j.name, label: j.name }))}
              />
            </div>
            <label className="flex items-center gap-2 text-[13px] text-subtle">
              <Switch checked={live} onCheckedChange={setLive} /> Live updates
            </label>
          </>
        }
      />
      <QueryBoundary query={report} errorTitle="Couldn't load this job">
        {(data) => <JobView data={data} job={job} live={live} />}
      </QueryBoundary>
    </div>
  );
}

function JobView({ data, job, live }: { data: JobReport; job: string; live: boolean }) {
  const [state, setState] = useSearchState(searchSchema);
  const eta = data.eta_s != null ? ` · ETA ~${formatDuration(data.eta_s)}` : "";
  return (
    <div className="space-y-6">
      <div>
        <div className="mb-2 flex justify-between text-[13px] text-subtle">
          <span aria-live="polite">
            {data.done}/{data.total} matches{eta}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-selected" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(data.progress * 100)} aria-label="Matches done">
          <div className="h-full bg-success transition-[width] duration-500" style={{ width: `${data.progress * 100}%` }} />
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Running now" value={data.running} />
        <Metric label="Queued" value={data.queued} />
        <Metric label="Crashed" value={data.crashed} />
        <Metric label="Est. spend" value={<Money usd={data.est_spend_usd} />} />
        <Metric label="Elapsed" value={<Duration seconds={data.elapsed_s} />} />
      </dl>
      <Tabs value={state.tab} onValueChange={(tab) => setState({ tab: tab as (typeof TABS)[number] })}>
        <TabsList aria-label="Job details">
          <TabsTrigger value="leaderboard">Leaderboard</TabsTrigger>
          <TabsTrigger value="winrates">Win rates &amp; endings</TabsTrigger>
          <TabsTrigger value="metrics">Per-model metrics</TabsTrigger>
          <TabsTrigger value="matches">Matches</TabsTrigger>
          <TabsTrigger value="config">Config</TabsTrigger>
        </TabsList>
        <TabsContent value="leaderboard">
          <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
            <section className="space-y-2">
              <h2 className="text-base">Standings</h2>
              <p className="text-xs text-muted">Ranked by games won.</p>
              <StandingsTable rows={data.standings} />
            </section>
            <section className="space-y-2">
              <h2 className="text-base">Head to head</h2>
              <p className="text-xs text-muted">Row player&apos;s points / games.</p>
              <HeadToHeadGrid cells={data.head_to_head} />
            </section>
          </div>
        </TabsContent>
        <TabsContent value="winrates">
          <div className="space-y-8">
            <WinTable rows={data.win_table} />
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <Card>
                <CardHeader>
                  <CardTitle>How matches ended</CardTitle>
                </CardHeader>
                <CardContent>
                  <EndingBars endings={data.endings} />
                </CardContent>
              </Card>
              <p className="text-xs leading-relaxed text-muted">
                Regulation is 3:00 and overtime adds up to 2:00 (sudden death: the first crown wins); if still tied, the engine&apos;s tower-HP tiebreak decides.
              </p>
            </div>
          </div>
        </TabsContent>
        <TabsContent value="metrics">
          <MetricsTable rows={data.metrics} />
        </TabsContent>
        <TabsContent value="matches">
          <MatchesTab job={job} live={live && data.status === "running"} filters={{ status: state.status, player: state.player, page: state.page }} onChange={setState} />
        </TabsContent>
        <TabsContent value="config">
          <CodeBlock label="config.toml" code={data.config_toml || "(no config recorded)"} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
