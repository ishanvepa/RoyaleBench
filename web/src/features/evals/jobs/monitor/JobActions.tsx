import { Gauge, Play, RotateCcw, Square } from "lucide-react";
import { useState } from "react";
import type { JobDetail } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useEnvironment } from "../../api/environment";
import { useJobAction, useSetConcurrency } from "../../api/jobs";
import { useCanStart } from "../../useCanStart";

/** Stop, resume, retry and concurrency. Each one that spends or cancels work asks first. */
export function JobActions({ detail }: { detail: JobDetail }) {
  const { job } = detail;
  const counts = job.task_state_counts;
  const canAct = useCanStart();
  const env = useEnvironment();
  const maxConcurrency = env.data?.settings.max_concurrency ?? 10;
  const action = useJobAction(job.id);
  const setConcurrency = useSetConcurrency(job.id);

  const [stopOpen, setStopOpen] = useState(false);
  const [force, setForce] = useState(false);
  const [concurrencyOpen, setConcurrencyOpen] = useState(false);
  const [concurrency, setConcurrencyValue] = useState(detail.concurrency ?? 1);

  const canResume = job.status === "STOPPED" || (!detail.active && (counts.STOPPED ?? 0) > 0);
  const canRetry = !detail.active && (counts.ERROR ?? 0) > 0;
  const disabled = !canAct.allowed;
  const why = canAct.reason ?? undefined;
  const validConcurrency = Number.isInteger(concurrency) && concurrency >= 1 && concurrency <= maxConcurrency;

  return (
    <>
      {detail.active ? (
        <>
          <Button variant="secondary" onClick={() => setConcurrencyOpen(true)} disabled={disabled} title={why}>
            <Gauge className="size-4" aria-hidden /> Concurrency
          </Button>
          <Button variant="danger-outline" onClick={() => setStopOpen(true)} disabled={disabled || job.status === "STOPPING"} title={why}>
            <Square className="size-4" aria-hidden /> Stop
          </Button>
        </>
      ) : null}
      {canResume ? (
        <Button variant="secondary" onClick={() => action.mutate({ action: "resume" })} loading={action.isPending} disabled={disabled} title={why}>
          <Play className="size-4" aria-hidden /> Resume
        </Button>
      ) : null}
      {canRetry ? (
        <Button variant="secondary" onClick={() => action.mutate({ action: "retry" })} loading={action.isPending} disabled={disabled} title={why}>
          <RotateCcw className="size-4" aria-hidden /> Retry failed ({counts.ERROR})
        </Button>
      ) : null}

      <ConfirmDialog
        open={stopOpen}
        onOpenChange={setStopOpen}
        title="Stop this job?"
        description="Running and queued tasks are cancelled. Finished tasks keep their results, and you can resume the run later."
        confirmLabel="Stop job"
        destructive
        loading={action.isPending}
        onConfirm={() => action.mutate({ action: "stop", force }, { onSettled: () => setStopOpen(false) })}
      >
        <label className="flex items-start gap-2.5 text-[13px]">
          <Checkbox checked={force} onCheckedChange={(v) => setForce(v === true)} className="mt-0.5" />
          <span>
            Force stop <span className="text-muted">(don&apos;t wait for running tasks to clean up)</span>
          </span>
        </label>
      </ConfirmDialog>

      <ConfirmDialog
        open={concurrencyOpen}
        onOpenChange={setConcurrencyOpen}
        title="Change concurrency"
        description="How many tasks of this run may execute at once. The change applies to tasks that have not started."
        confirmLabel="Update"
        loading={setConcurrency.isPending}
        onConfirm={() => {
          if (validConcurrency) setConcurrency.mutate(concurrency, { onSettled: () => setConcurrencyOpen(false) });
        }}
      >
        <Field label="Concurrency" error={validConcurrency ? undefined : `Enter a whole number from 1 to ${maxConcurrency}`}>
          {(c) => (
            <Input
              id={c.id}
              type="number"
              min={1}
              max={maxConcurrency}
              value={Number.isFinite(concurrency) ? concurrency : ""}
              aria-invalid={c.invalid}
              aria-describedby={c.describedBy}
              onChange={(e) => setConcurrencyValue(e.target.valueAsNumber)}
            />
          )}
        </Field>
      </ConfirmDialog>
    </>
  );
}
