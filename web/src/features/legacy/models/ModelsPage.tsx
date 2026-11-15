import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import { z } from "zod";
import type { ModelRow } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { RelativeTime } from "@/components/domain/values";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { DataTable } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { ALL, Select } from "@/components/ui/select";
import { stringParam, useSearchState } from "@/hooks/useSearchState";
import { useReadOnly } from "@/hooks/useServerInfo";
import { familyLabel } from "@/lib/family";
import { DASH } from "@/lib/format";
import { useModelCheck, useModels } from "../api/models";

const searchSchema = z.object({ family: stringParam() });
const col = createColumnHelper<ModelRow>();

export function Component() {
  const [{ family }, setState] = useSearchState(searchSchema);
  const models = useModels();
  const { status, start } = useModelCheck();
  const readOnly = useReadOnly();
  const columns = useMemo(
    () => [
      col.accessor("name", { header: "Player", cell: (c) => <ModelLabel model={c.getValue()} logoUrl={c.row.original.logo_url} /> }),
      col.accessor((r) => familyLabel(r.family), { id: "family", header: "Family" }),
      col.accessor("type", { header: "Type", cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
      col.accessor("provider", { header: "Provider", cell: (c) => <span className="text-subtle">{c.getValue()}</span> }),
      col.accessor("model", { header: "Model id", cell: (c) => <code className="font-mono text-xs">{c.getValue() || DASH}</code> }),
      col.accessor("effort", { header: "Effort", cell: (c) => <span className="text-subtle">{c.getValue() || DASH}</span> }),
      col.accessor("enabled", { header: "Enabled", cell: (c) => (c.getValue() ? "yes" : <span className="text-muted">no</span>) }),
      col.accessor((r) => (r.key_ok === null ? 2 : r.key_ok ? 1 : 0), {
        id: "key",
        header: "Key",
        cell: (c) => {
          const m = c.row.original;
          return m.key_ok === null ? <span className="text-muted">{DASH}</span> : m.key_ok ? <Badge tone="success">set</Badge> : <Badge tone="danger">{m.key_env} missing</Badge>;
        },
      }),
      col.accessor((r) => (r.check_ok === null ? 2 : r.check_ok ? 1 : 0), {
        id: "check",
        header: "Last check",
        cell: (c) => {
          const m = c.row.original;
          if (m.check_ok === null) return <span className="text-muted">{DASH}</span>;
          return (
            <span title={m.check_detail}>
              {m.check_ok ? <Badge tone="success">ok</Badge> : <Badge tone="danger">failed</Badge>}{" "}
              <span className="text-xs text-muted"><RelativeTime value={m.checked_at ? new Date(m.checked_at * 1000) : null} /></span>
            </span>
          );
        },
      }),
      col.accessor((r) => (r.price_in == null ? undefined : r.price_in), {
        id: "price",
        header: "Price in/out ($/M)",
        sortUndefined: "last",
        meta: { align: "right" },
        cell: (c) => (c.row.original.price_in == null ? DASH : `${c.row.original.price_in}/${c.row.original.price_out ?? 0}`),
      }),
      col.accessor("games", { header: "Games (all jobs)", meta: { align: "right" }, sortDescFirst: true }),
      col.accessor("wins", { header: "Wins (all jobs)", meta: { align: "right" }, sortDescFirst: true }),
    ],
    [],
  );

  const running = status?.state === "running";
  return (
    <div>
      <PageHeader
        title="Models"
        description="The players in the arena configuration, whether their keys are set, and how each last answered a connectivity check."
        actions={
          <Button variant="secondary" loading={running || start.isPending} onClick={() => start.mutate()} disabled={readOnly} title={readOnly ? "This server is read-only" : "Makes one cheap call to every configured model"}>
            Run model check
          </Button>
        }
      />
      <QueryBoundary query={models} errorTitle="Couldn't load the models">
        {(data) => {
          const families = [...new Set(data.models.map((m) => m.family))].sort();
          const shown = family ? data.models.filter((m) => m.family === family) : data.models;
          return (
            <div className="space-y-4">
              <div className="w-60">
                <Select
                  aria-label="Model family"
                  value={family || ALL}
                  onValueChange={(v) => setState({ family: v === ALL ? "" : v })}
                  options={[{ value: ALL, label: "All families" }, ...families.map((f) => ({ value: f, label: familyLabel(f) }))]}
                />
              </div>
              <DataTable caption="Configured models" columns={columns} data={shown} getRowId={(m) => m.name} initialSorting={[{ id: "name", desc: false }]} empty="No players in the configuration." />
              <p className="text-xs text-muted">From {data.config_name}. Keys are read from the environment or .env. “Games” and “wins” pool every finished match in the database.</p>
            </div>
          );
        }}
      </QueryBoundary>
      {status && status.state !== "idle" ? (
        <section className="mt-8 space-y-2" aria-live="polite">
          <h2 className="text-base">
            Model check {running ? "(running…)" : status.state === "done" ? "(finished)" : "(failed)"}
          </h2>
          <CodeBlock code={status.output || "Starting…"} maxHeight="18rem" wrap />
        </section>
      ) : null}
    </div>
  );
}
