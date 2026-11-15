import { Brain, CheckCircle2, Cog, MessageSquare, Terminal, Wrench } from "lucide-react";
import { useState } from "react";
import type { Trace, TraceStep } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Money } from "@/components/domain/values";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/format";
import { useTaskTrace } from "../api/jobs";

const STEP_ICON: Record<string, typeof Brain> = {
  system: Cog,
  thinking: Brain,
  text: MessageSquare,
  tool_use: Wrench,
  tool_result: Terminal,
  result: CheckCircle2,
};

function Step({ step }: { step: TraceStep }) {
  const Icon = STEP_ICON[step.kind] ?? Cog;
  const firstLine = step.text.split("\n", 1)[0] ?? "";
  return (
    <li>
      <details open={step.kind === "result"} className="group rounded-lg border border-line bg-surface">
        <summary className="flex cursor-pointer list-none items-center gap-2.5 px-3 py-2 text-[13px] hover:bg-selected/50">
          <Icon className="size-4 shrink-0 text-muted" aria-hidden />
          <span className="font-medium">{step.title}</span>
          <span className="min-w-0 flex-1 truncate text-muted group-open:hidden">{firstLine}</span>
        </summary>
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words border-t border-line px-3 py-2.5 font-mono text-xs leading-relaxed">{step.text || "(empty)"}</pre>
      </details>
    </li>
  );
}

function TraceBody({ trace }: { trace: Trace }) {
  if (!trace.available) {
    return <p className="text-[13px] text-muted">No agent output was recorded for this task (it may have failed before the agent started).</p>;
  }
  return (
    <div className="space-y-3">
      <p className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-subtle">
        <span>
          Cost <Money usd={trace.cost_usd} />
        </span>
        <span>Input tokens {formatNumber(trace.input_tokens)}</span>
        <span>Output tokens {formatNumber(trace.output_tokens)}</span>
        <span>Cached tokens read {formatNumber(trace.cache_read_tokens)}</span>
      </p>
      {trace.steps.length === 0 ? (
        <p className="text-[13px] text-muted">The agent left no step-by-step trajectory.</p>
      ) : (
        <ol className="space-y-1.5" aria-label="Agent steps">
          {trace.steps.map((step, i) => (
            <Step key={i} step={step} />
          ))}
        </ol>
      )}
      {trace.steps_total > trace.steps.length ? (
        <p className="text-xs text-muted">Showing the first {trace.steps.length} of {trace.steps_total} steps.</p>
      ) : null}
    </div>
  );
}

/** The agent's trajectory for one task. Nothing is downloaded until the user asks (the first load fetches it from Valkyrie). */
export function TraceView({ runId, taskId, autoLoad = false }: { runId: string; taskId: string; autoLoad?: boolean }) {
  const [requested, setRequested] = useState(autoLoad);
  const trace = useTaskTrace(runId, taskId, requested);
  if (!requested) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" size="sm" onClick={() => setRequested(true)}>
          Load agent trace
        </Button>
        <span className="text-xs text-muted">Downloads the agent&apos;s output from Valkyrie the first time, then it is cached.</span>
      </div>
    );
  }
  return (
    <QueryBoundary query={trace} errorTitle="Couldn't load the trace" skeleton={<Skeleton className="h-24 w-full" />}>
      {(t) => <TraceBody trace={t} />}
    </QueryBoundary>
  );
}
