import { createColumnHelper } from "@tanstack/react-table";
import { FolderOpen } from "lucide-react";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router";
import type { BenchmarkRow } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Score } from "@/components/domain/values";
import { Badge } from "@/components/ui/badge";
import { Banner } from "@/components/ui/banner";
import { DataTable } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { plural } from "@/lib/format";
import { useBenchmarks } from "../api/benchmarks";
import { BenchmarkStateBadge } from "./badges";

const col = createColumnHelper<BenchmarkRow>();

function useColumns() {
  return useMemo(
    () => [
      col.accessor("title", {
        header: "Benchmark",
        cell: (c) => (
          <div className="min-w-0">
            <Link to={`/evals/benchmarks/${c.row.original.name}`} className="font-medium underline-offset-4 hover:underline">
              {c.getValue()}
            </Link>
            <div className="font-mono text-xs text-muted">{c.row.original.name}</div>
          </div>
        ),
      }),
      col.accessor("kind", {
        header: "Kind",
        cell: (c) => (c.getValue() === "smoke" ? <Badge title="Infrastructure check; excluded from the leaderboard by default.">Smoke test</Badge> : <span className="text-subtle">Eval</span>),
      }),
      col.accessor("state", { header: "Status", cell: (c) => <BenchmarkStateBadge state={c.getValue()} /> }),
      col.accessor("task_count", { header: "Tasks", meta: { align: "right" }, sortDescFirst: true }),
      col.accessor((r) => r.latest_revision ?? 0, {
        id: "published",
        header: "Published",
        cell: (c) => {
          const row = c.row.original;
          if (row.latest_revision == null) return <span className="text-muted">Never</span>;
          return (
            <span className="flex flex-wrap items-center gap-1.5">
              <span className="tabular-nums">r{row.latest_revision}</span>
              {row.tags.filter((t) => t !== "latest").map((t) => (
                <Badge key={t} tone="outline">
                  {t}
                </Badge>
              ))}
            </span>
          );
        },
      }),
      col.accessor("runs", { header: "Runs", meta: { align: "right" }, sortDescFirst: true }),
      col.accessor((r) => r.best_score ?? undefined, {
        id: "best",
        header: "Best score",
        sortUndefined: "last",
        sortDescFirst: true,
        meta: { align: "right" },
        cell: (c) => <Score value={c.row.original.best_score} />,
      }),
      col.accessor("problems", {
        header: "Problems",
        meta: { align: "right" },
        cell: (c) => (c.getValue() > 0 ? <Badge tone="warning">{c.getValue()}</Badge> : <span className="text-muted">–</span>),
      }),
    ],
    [],
  );
}

export function Component() {
  const navigate = useNavigate();
  const benchmarks = useBenchmarks();
  const columns = useColumns();
  return (
    <div>
      <PageHeader
        title="Benchmarks"
        description="Harbor task sets we are drafting. Each folder under benchmarks/ is one benchmark; publish it to Valkyrie to run it."
      />
      <QueryBoundary query={benchmarks} errorTitle="Couldn't load benchmarks">
        {(data) => (
          <div className="space-y-4">
            {data.valkyrie_error ? (
              <Banner tone="warning" title="Showing local folders only">
                Valkyrie could not be queried, so publish status is unknown: {data.valkyrie_error}
              </Banner>
            ) : null}
            <DataTable
              caption="Benchmarks"
              columns={columns}
              data={data.benchmarks}
              getRowId={(r) => r.name}
              initialSorting={[{ id: "title", desc: false }]}
              onRowClick={(row) => void navigate(`/evals/benchmarks/${row.name}`)}
              empty={
                <EmptyState
                  icon={<FolderOpen className="size-6" aria-hidden />}
                  title="No benchmarks yet"
                  description="Create benchmarks/<name>/<task-id>/ with a Harbor task.toml, instruction.md, tests/test.sh and environment/Dockerfile. It shows up here."
                  className="border-0"
                />
              }
            />
            <p className="text-xs text-muted">{plural(data.benchmarks.length, "benchmark")}</p>
          </div>
        )}
      </QueryBoundary>
    </div>
  );
}
