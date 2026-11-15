import { ExternalLink, X } from "lucide-react";
import { Link } from "react-router";
import type { TaskRow } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration, KeyValues } from "@/components/domain/values";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { Skeleton } from "@/components/ui/skeleton";
import { formatReward } from "@/lib/format";
import { useTaskDetail } from "../../api/jobs";
import { TraceView } from "../../shared/TraceView";
import { TaskReplay } from "../../shared/TaskReplay";

const TERMINAL = ["FINISHED", "ERROR", "STOPPED"];

/** One task's grade, timings, errors, recorded gameplay, verifier output and agent trace. */
export function TaskPanel({ runId, dataset, task, onClose }: { runId: string; dataset: string; task: TaskRow; onClose: () => void }) {
  const detail = useTaskDetail(runId, task.task);
  return (
    <Card>
      <CardHeader>
        <div className="min-w-0">
          <CardTitle className="truncate font-mono">{task.task}</CardTitle>
          <div className="mt-1.5">
            <StatusPill kind="task" status={task.status} />
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close task details">
          <X className="size-4" aria-hidden />
        </Button>
      </CardHeader>
      <CardContent className="space-y-5">
        <QueryBoundary query={detail} errorTitle="Couldn't load this task" skeleton={<Skeleton className="h-32 w-full" />}>
          {(d) => (
            <>
              <KeyValues
                items={[
                  { label: "Reward", value: d.reward == null ? "Not graded yet" : `${formatReward(d.reward)}${d.solved ? " (solved)" : ""}` },
                  { label: "Agent time", value: <Duration seconds={d.agent_s} /> },
                  { label: "Sandbox time", value: <Duration seconds={d.sandbox_s} /> },
                  { label: "Build time", value: <Duration seconds={d.build_s} /> },
                  { label: "Grading time", value: <Duration seconds={d.eval_s} /> },
                ]}
              />
              {d.error ? (
                <div className="space-y-1.5">
                  <h3 className="text-[13px] font-medium text-danger">
                    Error{d.category ? ` (${d.category})` : ""}
                  </h3>
                  <CodeBlock code={d.error} wrap maxHeight="12rem" />
                </div>
              ) : null}
              {d.verifier_output ? (
                <div className="space-y-1.5">
                  <h3 className="text-[13px] font-medium">Verifier output</h3>
                  <CodeBlock code={d.verifier_output} wrap maxHeight="12rem" />
                </div>
              ) : null}
            </>
          )}
        </QueryBoundary>
        {TERMINAL.includes(task.status) ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <h3 className="text-[13px] font-medium">Game replay</h3>
              <TaskReplay key={`replay/${runId}/${task.task}`} runId={runId} taskId={task.task} />
            </div>
            <div className="space-y-2">
              <h3 className="text-[13px] font-medium">Agent trace</h3>
              <TraceView key={`${runId}/${task.task}`} runId={runId} taskId={task.task} />
            </div>
          </div>
        ) : (
          <p className="text-[13px] text-muted">
            The game replay and agent trace are available once the task has finished or stopped.
          </p>
        )}
        {dataset ? (
          <Link
            to={`/evals/benchmarks/${dataset}/tasks/${task.task}`}
            className="inline-flex items-center gap-1.5 text-[13px] text-subtle underline-offset-4 hover:text-ink hover:underline"
          >
            Open the task definition <ExternalLink className="size-3.5" aria-hidden />
          </Link>
        ) : null}
      </CardContent>
    </Card>
  );
}
