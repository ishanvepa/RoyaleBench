import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { z } from "zod";
import type { BenchmarkTaskDetail, TaskResultRow, TaskResults } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Duration, KeyValues, Money, RelativeTime } from "@/components/domain/values";
import { Badge } from "@/components/ui/badge";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { DataTable } from "@/components/ui/data-table";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Markdown } from "@/components/ui/markdown";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { enumParam, useSearchState } from "@/hooks/useSearchState";
import { formatBytes, formatDuration, formatPercent, formatReward, harnessName } from "@/lib/format";
import { useBenchmarkTask, useTaskResults } from "../api/benchmarks";
import { TraceView } from "../shared/TraceView";
import { TaskReplay } from "../shared/TaskReplay";
import { DifficultyBadge, SyncBadge } from "./badges";

const TABS = ["overview", "files", "results"] as const;
const searchSchema = z.object({ tab: enumParam(TABS, "overview") });

export function Component() {
  const { name = "", taskId = "" } = useParams();
  const task = useBenchmarkTask(name, taskId);
  return (
    <div>
      <Breadcrumbs
        items={[{ label: "Benchmarks", to: "/evals/benchmarks" }, { label: name, to: `/evals/benchmarks/${name}` }, { label: taskId }]}
      />
      <QueryBoundary query={task} errorTitle="Couldn't load this task">
        {(detail) => <TaskView detail={detail} />}
      </QueryBoundary>
    </div>
  );
}

function TaskView({ detail }: { detail: BenchmarkTaskDetail }) {
  const [state, setState] = useSearchState(searchSchema);
  const { task } = detail;
  return (
    <>
      <PageHeader
        title={<span className="font-mono text-2xl">{task.id}</span>}
        meta={
          <>
            <SyncBadge sync={task.sync} />
            {task.category ? <Badge tone="outline">{task.category}</Badge> : null}
            {task.difficulty ? <DifficultyBadge difficulty={task.difficulty} /> : null}
          </>
        }
        description={task.description || undefined}
      />
      <Tabs value={state.tab} onValueChange={(tab) => setState({ tab: tab as (typeof TABS)[number] })}>
        <TabsList aria-label="Task details">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="files">Files</TabsTrigger>
          <TabsTrigger value="results">Results</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <Overview detail={detail} />
        </TabsContent>
        <TabsContent value="files">
          <Files detail={detail} />
        </TabsContent>
        <TabsContent value="results">
          <Results benchmark={detail.benchmark} taskId={task.id} />
        </TabsContent>
      </Tabs>
    </>
  );
}

function Overview({ detail }: { detail: BenchmarkTaskDetail }) {
  const { task } = detail;
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Card>
        <CardHeader>
          <CardTitle>Instruction</CardTitle>
          <span className="text-xs text-muted">What the agent is told. instruction.md</span>
        </CardHeader>
        <CardContent>{detail.instruction.trim() ? <Markdown>{detail.instruction}</Markdown> : <p className="text-muted">instruction.md is empty.</p>}</CardContent>
      </Card>
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Limits and resources</CardTitle>
          </CardHeader>
          <CardContent>
            <KeyValues
              items={[
                { label: "Agent time limit", value: formatDuration(task.agent_timeout_s) },
                { label: "Verifier time limit", value: formatDuration(task.verifier_timeout_s) },
                ...Object.entries(task.resources).map(([k, v]) => ({ label: k.replace(/_/g, " "), value: String(v) })),
              ]}
            />
          </CardContent>
        </Card>
        {task.problems.length > 0 ? (
          <Card className="border-warning/40">
            <CardHeader>
              <CardTitle>Problems</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="list-disc space-y-1.5 pl-4 text-[13px]">
                {task.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function Files({ detail }: { detail: BenchmarkTaskDetail }) {
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Files</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-1.5 text-[13px]">
            {detail.files.map((f) => (
              <li key={f.path} className="flex justify-between gap-3">
                <span className="truncate font-mono">{f.path}</span>
                <span className="shrink-0 tabular-nums text-muted">{formatBytes(f.size)}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
      <div className="space-y-6">
        <Section title="task.toml" note="Metadata, limits and resources">
          <CodeBlock label="task.toml" code={detail.config_toml || "(empty)"} />
        </Section>
        {detail.test_script !== null && detail.test_script !== undefined ? (
          <Section title="How it is graded" note="tests/test.sh runs after the agent and writes the reward">
            <CodeBlock label="tests/test.sh" code={detail.test_script} />
          </Section>
        ) : (
          <p className="text-[13px] text-warning">There is no tests/test.sh, so nothing grades this task.</p>
        )}
        {detail.dockerfile ? (
          <Section title="Environment" note="The sandbox image">
            <CodeBlock label="environment/Dockerfile" code={detail.dockerfile} />
          </Section>
        ) : null}
        {detail.solution_script ? (
          <Section title="Reference solution" note="Not shown to the agent">
            <CodeBlock label="solution/solve.sh" code={detail.solution_script} />
          </Section>
        ) : null}
      </div>
    </div>
  );
}

function Section({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-2 flex items-baseline gap-3">
        <h2 className="text-base">{title}</h2>
        <span className="text-xs text-muted">{note}</span>
      </div>
      {children}
    </section>
  );
}

// --------------------------------------------------------------------------------------------- results
const summaryCol = createColumnHelper<TaskResults["summary"][number]>();
const resultCol = createColumnHelper<TaskResultRow>();

function Results({ benchmark, taskId }: { benchmark: string; taskId: string }) {
  const results = useTaskResults(benchmark, taskId);
  const [tracing, setTracing] = useState<TaskResultRow | null>(null);

  const summaryColumns = useMemo(
    () => [
      summaryCol.accessor("model", { header: "Model", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      summaryCol.accessor((r) => harnessName(r.harness), { id: "harness", header: "Harness", cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
      summaryCol.accessor("attempts", { header: "Attempts", meta: { align: "right" }, sortDescFirst: true }),
      summaryCol.accessor("solved", { header: "Solved", meta: { align: "right" }, sortDescFirst: true }),
      summaryCol.accessor((r) => r.pass_rate ?? undefined, {
        id: "rate",
        header: "Pass rate",
        sortUndefined: "last",
        sortDescFirst: true,
        meta: { align: "right" },
        cell: (c) => formatPercent(c.row.original.pass_rate),
      }),
    ],
    [],
  );

  const resultColumns = useMemo(
    () => [
      resultCol.accessor("job", {
        header: "Run",
        cell: (c) => (
          <Link to={`/evals/jobs/${c.row.original.run_id}`} className="underline-offset-4 hover:underline">
            {c.getValue() || "(no label)"}
          </Link>
        ),
      }),
      resultCol.accessor("model", { header: "Model", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      resultCol.accessor((r) => harnessName(r.harness), { id: "harness", header: "Harness", cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
      resultCol.accessor("revision", { header: "Rev", cell: (c) => `r${c.getValue()}` }),
      resultCol.accessor((r) => r.reward ?? undefined, {
        id: "reward",
        header: "Reward",
        sortUndefined: "last",
        sortDescFirst: true,
        meta: { align: "right" },
        cell: (c) => (
          <span className="inline-flex items-center gap-2">
            <span className="tabular-nums">{formatReward(c.row.original.reward)}</span>
            {c.row.original.solved ? <Badge tone="success">Solved</Badge> : c.row.original.error ? <Badge tone="danger">Error</Badge> : <Badge>Not solved</Badge>}
          </span>
        ),
      }),
      resultCol.accessor((r) => r.agent_s ?? undefined, {
        id: "time",
        header: "Agent time",
        sortUndefined: "last",
        meta: { align: "right" },
        cell: (c) => <Duration seconds={c.row.original.agent_s} />,
      }),
      resultCol.accessor((r) => r.cost ?? undefined, {
        id: "cost",
        header: "Cost",
        sortUndefined: "last",
        meta: { align: "right" },
        cell: (c) => <Money usd={c.row.original.cost} />,
      }),
      resultCol.accessor((r) => (r.started_at ? Date.parse(r.started_at) : 0), {
        id: "when",
        header: "When",
        sortDescFirst: true,
        cell: (c) => <RelativeTime value={c.row.original.started_at} />,
      }),
      resultCol.display({
        id: "replay",
        header: () => <span className="sr-only">Replay</span>,
        cell: (c) => <TaskReplay runId={c.row.original.run_id} taskId={taskId} />,
      }),
      resultCol.display({
        id: "trace",
        header: () => <span className="sr-only">Trace</span>,
        cell: (c) => (
          <Button variant="ghost" size="sm" onClick={() => setTracing(c.row.original)}>
            Trace
          </Button>
        ),
      }),
    ],
    [taskId],
  );

  return (
    <QueryBoundary query={results} errorTitle="Couldn't load results">
      {(data) =>
        data.results.length === 0 ? (
          <EmptyState title="No results yet" description="No finished run has attempted this task. Start a job on this benchmark to see how models do." />
        ) : (
          <div className="space-y-8">
            <section>
              <h2 className="mb-3 text-base">By model</h2>
              <DataTable
                caption="Pass rate on this task by model"
                columns={summaryColumns}
                data={data.summary}
                getRowId={(r) => `${r.model}|${r.harness}`}
                initialSorting={[{ id: "rate", desc: true }]}
              />
            </section>
            <section>
              <h2 className="mb-3 text-base">Every finished run</h2>
              <DataTable
                caption="Results of every finished run on this task"
                columns={resultColumns}
                data={data.results}
                getRowId={(r) => r.run_id}
                initialSorting={[{ id: "when", desc: true }]}
              />
            </section>
            <Dialog open={tracing !== null} onOpenChange={(open) => (open ? undefined : setTracing(null))}>
              {tracing ? (
                <DialogContent className="max-w-3xl" title={`Agent trace: ${taskId}`} description={`${tracing.model} in ${tracing.job || "run"}`}>
                  <TraceView runId={tracing.run_id} taskId={taskId} autoLoad />
                </DialogContent>
              ) : null}
            </Dialog>
          </div>
        )
      }
    </QueryBoundary>
  );
}
