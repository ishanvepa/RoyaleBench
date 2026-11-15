import { useEffect, useRef, useState } from "react";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Input } from "@/components/ui/input";
import { ALL, Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { parseDate } from "@/lib/format";
import { useJobLogs, useJobTasks } from "../../api/jobs";

function clock(timestamp: string): string {
  const d = parseDate(timestamp);
  return d ? d.toLocaleTimeString("en-US", { hour12: false }) : "";
}

export function LogsTab({ runId, active }: { runId: string; active: boolean }) {
  const tasks = useJobTasks(runId, false);
  const [taskId, setTaskId] = useState("");
  const [text, setText] = useState("");
  const [live, setLive] = useState(active);
  const q = useDebouncedValue(text, 300);
  const logs = useJobLogs(runId, { taskId, q }, live && active);

  const box = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const count = logs.data?.lines.length ?? 0;
  useEffect(() => {
    // Follow new lines only while the reader is at the bottom; scrolling up pauses following.
    if (pinned.current && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [count]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-56">
          <Select
            aria-label="Filter logs by task"
            value={taskId || ALL}
            onValueChange={(v) => setTaskId(v === ALL ? "" : v)}
            options={[{ value: ALL, label: "All tasks" }, ...(tasks.data?.tasks ?? []).map((t) => ({ value: t.task, label: t.task }))]}
          />
        </div>
        <Input aria-label="Search the logs" placeholder="Search log lines…" value={text} onChange={(e) => setText(e.target.value)} className="w-64" />
        {active ? (
          <label className="flex items-center gap-2 pb-2 text-[13px] text-subtle">
            <Switch checked={live} onCheckedChange={setLive} /> Live
          </label>
        ) : null}
      </div>
      <QueryBoundary query={logs} errorTitle="Couldn't load logs">
        {(data) => (
          <div
            ref={box}
            onScroll={(e) => {
              const el = e.currentTarget;
              pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
            }}
            tabIndex={0}
            role="log"
            aria-label="Run logs"
            className="h-[28rem] overflow-auto rounded-xl border border-line bg-surface p-3 font-mono text-xs leading-relaxed"
          >
            {data.lines.length === 0 ? (
              <p className="text-muted">{q || taskId ? "No log lines match." : "No log lines yet."}</p>
            ) : (
              data.lines.map((line, i) => (
                <div key={i} className="flex gap-3 py-px">
                  <span className="shrink-0 text-muted">{clock(line.timestamp)}</span>
                  {line.task_id && !taskId ? <span className="shrink-0 text-info">{line.task_id}</span> : null}
                  <span className="min-w-0 whitespace-pre-wrap break-all">{line.message}</span>
                </div>
              ))
            )}
          </div>
        )}
      </QueryBoundary>
      <p className="text-xs text-muted">Showing the most recent lines (up to 500).</p>
    </div>
  );
}
