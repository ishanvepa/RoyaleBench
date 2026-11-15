import { createColumnHelper } from "@tanstack/react-table";
import { Play, UploadCloud } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import type { BenchmarkDetail, BenchmarkTask, BenchmarkVersion } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { RelativeTime } from "@/components/domain/values";
import { Badge } from "@/components/ui/badge";
import { Banner } from "@/components/ui/banner";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { Tooltip } from "@/components/ui/tooltip";
import { formatDuration, plural, shortId } from "@/lib/format";
import { useBenchmark } from "../api/benchmarks";
import { useCanStart } from "../useCanStart";
import { BenchmarkStateBadge, DifficultyBadge, SyncBadge } from "./badges";
import { PublishDialog } from "./PublishDialog";

const taskCol = createColumnHelper<BenchmarkTask>();
const versionCol = createColumnHelper<BenchmarkVersion>();

function useTaskColumns(benchmark: string) {
  return useMemo(
    () => [
      taskCol.accessor("id", {
        header: "Task",
        cell: (c) =>
          c.row.original.local ? (
            <Link to={`/evals/benchmarks/${benchmark}/tasks/${c.getValue()}`} className="font-mono text-[13px] font-medium underline-offset-4 hover:underline">
              {c.getValue()}
            </Link>
          ) : (
            <span className="font-mono text-[13px]">{c.getValue()}</span>
          ),
      }),
      taskCol.accessor("category", { header: "Category", cell: (c) => <span className="text-subtle">{c.getValue() || "–"}</span> }),
      taskCol.accessor("difficulty", { header: "Difficulty", cell: (c) => <DifficultyBadge difficulty={c.getValue()} /> }),
      taskCol.accessor((r) => r.agent_timeout_s ?? undefined, {
        id: "agent",
        header: "Agent limit",
        sortUndefined: "last",
        meta: { align: "right" },
        cell: (c) => formatDuration(c.row.original.agent_timeout_s),
      }),
      taskCol.accessor((r) => r.verifier_timeout_s ?? undefined, {
        id: "verifier",
        header: "Verifier limit",
        sortUndefined: "last",
        meta: { align: "right" },
        cell: (c) => formatDuration(c.row.original.verifier_timeout_s),
      }),
      taskCol.accessor("sync", { header: "Published copy", cell: (c) => <SyncBadge sync={c.getValue()} /> }),
      taskCol.accessor((r) => r.problems.length, {
        id: "problems",
        header: "Problems",
        meta: { align: "right" },
        sortDescFirst: true,
        cell: (c) =>
          c.getValue() > 0 ? (
            <Tooltip content={c.row.original.problems.join(" · ")}>
              <Badge tone="warning" tabIndex={0}>
                {c.getValue()}
              </Badge>
            </Tooltip>
          ) : (
            <span className="text-muted">–</span>
          ),
      }),
    ],
    [benchmark],
  );
}

const versionColumns = [
  versionCol.accessor("revision", { header: "Revision", sortDescFirst: true, cell: (c) => <span className="tabular-nums">r{c.getValue()}</span> }),
  versionCol.accessor("tags", {
    header: "Tags",
    enableSorting: false,
    cell: (c) => (
      <span className="flex flex-wrap gap-1.5">
        {c.getValue().map((t) => (
          <Badge key={t} tone="outline">
            {t}
          </Badge>
        ))}
      </span>
    ),
  }),
  versionCol.accessor("task_count", { header: "Tasks", meta: { align: "right" } }),
  versionCol.accessor("digest", { header: "Digest", enableSorting: false, cell: (c) => <code className="font-mono text-xs text-muted">{shortId(c.getValue().replace("sha256:", ""))}</code> }),
  versionCol.accessor((r) => r.created_by ?? "", { id: "by", header: "Published by", cell: (c) => <span className="text-subtle">{c.getValue().split("@")[0] || "–"}</span> }),
  versionCol.accessor((r) => (r.created_at ? Date.parse(r.created_at) : 0), {
    id: "created",
    header: "When",
    sortDescFirst: true,
    cell: (c) => <RelativeTime value={c.row.original.created_at} />,
  }),
];

export function Component() {
  const { name = "" } = useParams();
  const benchmark = useBenchmark(name);
  return (
    <div>
      <Breadcrumbs items={[{ label: "Benchmarks", to: "/evals/benchmarks" }, { label: benchmark.data?.benchmark.title ?? name }]} />
      <QueryBoundary query={benchmark} errorTitle="Couldn't load this benchmark">
        {(detail) => <BenchmarkView detail={detail} />}
      </QueryBoundary>
    </div>
  );
}

function BenchmarkView({ detail }: { detail: BenchmarkDetail }) {
  const navigate = useNavigate();
  const [publishOpen, setPublishOpen] = useState(false);
  const canAct = useCanStart();
  const b = detail.benchmark;
  const columns = useTaskColumns(b.name);
  const runnable = b.versions > 0;

  return (
    <>
      <PageHeader
        title={b.title}
        meta={
          <>
            <BenchmarkStateBadge state={b.state} />
            {b.kind === "smoke" ? <Badge title="Infrastructure check; excluded from the leaderboard by default.">Smoke test</Badge> : null}
          </>
        }
        description={
          <>
            {b.description ? <span className="mb-1 block">{b.description}</span> : null}
            <span className="font-mono text-xs">{detail.dataset_ref}</span>
            {detail.folder ? <span className="font-mono text-xs"> · {detail.folder}/</span> : null}
          </>
        }
        actions={
          <>
            {b.local ? (
              <Button variant="secondary" onClick={() => setPublishOpen(true)} disabled={!canAct.allowed} title={canAct.reason ?? undefined}>
                <UploadCloud className="size-4" aria-hidden /> Publish
              </Button>
            ) : null}
            <Button asChild variant="primary" disabled={!runnable || !canAct.allowed}>
              {runnable && canAct.allowed ? (
                <Link to={`/evals/jobs/new?benchmark=${b.name}`}>
                  <Play className="size-4" aria-hidden /> Run this benchmark
                </Link>
              ) : (
                <button type="button" disabled title={!runnable ? "Publish it first" : (canAct.reason ?? undefined)}>
                  <Play className="size-4" aria-hidden /> Run this benchmark
                </button>
              )}
            </Button>
          </>
        }
      />

      <div className="space-y-4">
        {detail.valkyrie_error ? (
          <Banner tone="warning" title="Publish status unavailable">
            {detail.valkyrie_error}
          </Banner>
        ) : null}
        {detail.errors.length > 0 ? (
          <Banner tone="danger" title="Problems reading this folder">
            <ul className="list-disc pl-4">
              {detail.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </Banner>
        ) : null}
        {b.state === "draft" ? (
          <Banner tone="info" title="This benchmark isn't published">
            Jobs run published versions of a benchmark. Use Publish to upload it to Valkyrie first.
          </Banner>
        ) : null}
        {b.state === "modified" ? (
          <Banner tone="warning" title="Local changes aren't published">
            Jobs started now run the latest <em>published</em> version (r{b.latest_revision}), not your local edits. Publish to include them.
          </Banner>
        ) : null}
      </div>

      <section className="mt-8">
        <h2 className="mb-3 text-lg">Tasks ({detail.tasks.length})</h2>
        <DataTable
          caption="Tasks in this benchmark"
          columns={columns}
          data={detail.tasks}
          getRowId={(t) => t.id}
          initialSorting={[{ id: "id", desc: false }]}
          onRowClick={(t) => (t.local ? void navigate(`/evals/benchmarks/${b.name}/tasks/${t.id}`) : undefined)}
          empty="This benchmark has no tasks."
        />
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-lg">Published versions</h2>
        <DataTable
          caption="Published versions"
          columns={versionColumns}
          data={detail.versions}
          getRowId={(v) => String(v.revision)}
          initialSorting={[{ id: "revision", desc: true }]}
          empty={`Not published yet. ${plural(detail.tasks.length, "task")} will be uploaded the first time you publish.`}
        />
      </section>

      <PublishDialog detail={detail} open={publishOpen} onOpenChange={setPublishOpen} />
    </>
  );
}
