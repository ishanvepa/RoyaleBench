import { Brain, CheckCircle2, Cog, MessageSquare, Terminal, Wrench } from "lucide-react";
import { useState } from "react";
import type { Trace, TraceStep } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Money } from "@/components/domain/values";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleChip } from "@/components/ui/toggle-chip";
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

const KIND_LABEL: Record<string, string> = {
  text: "Messages",
  tool_use: "Tool calls",
  tool_result: "Tool results",
  result: "Final result",
  thinking: "Thinking",
  system: "Session",
  other: "Other",
};
const KIND_ORDER = Object.keys(KIND_LABEL);
/** What the agent said and did matters most; session bookkeeping and raw reasoning are opt-in. */
const DEFAULT_KINDS = ["text", "tool_use", "tool_result", "result"];

/** Bash calls are mostly shell plumbing, so they (and their results) start hidden; every other tool starts visible. */
const DEFAULT_HIDDEN_TOOLS = ["Bash"];

function withMember(set: Set<string>, value: string, present: boolean) {
  const next = new Set(set);
  if (present) next.add(value);
  else next.delete(value);
  return next;
}

function TraceBody({ trace }: { trace: Trace }) {
  const [shown, setShown] = useState<Set<string>>(() => new Set(DEFAULT_KINDS));
  const [hiddenTools, setHiddenTools] = useState<Set<string>>(() => new Set(DEFAULT_HIDDEN_TOOLS));
  if (!trace.available) {
    return <p className="text-[13px] text-muted">No agent output was recorded for this task (it may have failed before the agent started).</p>;
  }
  const kindOf = (s: TraceStep) => (s.kind in KIND_LABEL ? s.kind : "other");
  const counts = new Map<string, number>();
  const toolCalls = new Map<string, number>();
  for (const step of trace.steps) {
    counts.set(kindOf(step), (counts.get(kindOf(step)) ?? 0) + 1);
    if (step.kind === "tool_use" && step.tool) toolCalls.set(step.tool, (toolCalls.get(step.tool) ?? 0) + 1);
  }
  const kinds = KIND_ORDER.filter((k) => counts.has(k));
  const tools = [...toolCalls.keys()].sort();
  const visible = trace.steps.filter((s) => shown.has(kindOf(s)) && !(s.tool && hiddenTools.has(s.tool)));
  return (
    <div className="space-y-3">
      <p className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-subtle">
        <span>
          Cost <Money usd={trace.cost_usd} />
        </span>
        <span>Input tokens {formatNumber(trace.input_tokens)}</span>
        <span>Output tokens {formatNumber(trace.output_tokens)}</span>
        <span>Cached tokens read {formatNumber(trace.cache_read_tokens)}</span>
        {trace.api_calls != null && <span>Model calls {formatNumber(trace.api_calls)}</span>}
        {trace.reasoning_tokens != null && <span>Reasoning tokens {formatNumber(trace.reasoning_tokens)} (included in output)</span>}
      </p>
      {trace.cost_note && <p className="text-[13px] text-muted">{trace.cost_note}</p>}
      {trace.steps.length === 0 ? (
        <p className="text-[13px] text-muted">The agent left no step-by-step trajectory.</p>
      ) : (
        <>
          <div role="group" aria-label="Show step types" className="flex flex-wrap items-center gap-1.5">
            {kinds.map((kind) => (
              <ToggleChip key={kind} pressed={shown.has(kind)} onPressedChange={(on) => setShown((prev) => withMember(prev, kind, on))}>
                {KIND_LABEL[kind]} <span className="opacity-70">{counts.get(kind)}</span>
              </ToggleChip>
            ))}
          </div>
          {tools.length > 0 ? (
            <div role="group" aria-label="Show tools" className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-xs text-muted">Tools</span>
              {tools.map((tool) => (
                <ToggleChip key={tool} pressed={!hiddenTools.has(tool)} onPressedChange={(on) => setHiddenTools((prev) => withMember(prev, tool, !on))}>
                  {tool} <span className="opacity-70">{toolCalls.get(tool)}</span>
                </ToggleChip>
              ))}
            </div>
          ) : null}
          {visible.length === 0 ? (
            <p className="text-[13px] text-muted">No steps match the selected types.</p>
          ) : (
            <ol className="space-y-1.5" aria-label="Agent steps">
              {visible.map((step, i) => (
                <Step key={i} step={step} />
              ))}
            </ol>
          )}
        </>
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
