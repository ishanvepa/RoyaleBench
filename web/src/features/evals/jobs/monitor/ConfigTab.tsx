import { Link } from "react-router";
import type { JobDetail } from "@/api/types";
import { KeyValues } from "@/components/domain/values";
import { Card, CardContent } from "@/components/ui/card";
import { formatDateTime, plural } from "@/lib/format";

/** How the run was launched, as Valkyrie recorded it. Secrets appear by name only. */
export function ConfigTab({ detail }: { detail: JobDetail }) {
  const { job } = detail;
  const secrets = Object.entries(detail.secrets);
  return (
    <Card>
      <CardContent>
        <KeyValues
          items={[
            { label: "Run id", value: <code className="font-mono text-xs">{job.id}</code> },
            { label: "Job name", value: job.job },
            { label: "Benchmark", value: job.dataset ? <Link className="underline underline-offset-4" to={`/evals/benchmarks/${job.dataset}`}>{detail.dataset_version || job.dataset}</Link> : "–" },
            { label: "Tasks", value: detail.task_ids ? `${plural(detail.task_ids.length, "selected task")}: ${detail.task_ids.join(", ")}` : "Whole benchmark" },
            { label: "Harness", value: job.harness },
            { label: "Model", value: <code className="font-mono text-xs">{job.model}</code> },
            { label: "Sandbox provider", value: detail.provider },
            { label: "Concurrency", value: detail.concurrency ?? "–" },
            {
              label: "API key secrets",
              value: secrets.length ? secrets.map(([env, name]) => `${name} → ${env}`).join(", ") : "–",
            },
            { label: "Valkyrie project", value: detail.project ?? "–" },
            { label: "Started by", value: job.started_by || "–" },
            { label: "Started", value: formatDateTime(job.started_at) },
          ]}
        />
      </CardContent>
    </Card>
  );
}
