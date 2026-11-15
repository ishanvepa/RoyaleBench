import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

interface TaskChecklistProps {
  tasks: readonly string[];
  selected: readonly string[];
  onChange: (selected: string[]) => void;
}

/** Choose a subset of a benchmark's tasks. */
export function TaskChecklist({ tasks, selected, onChange }: TaskChecklistProps) {
  const prefix = useId();
  const chosen = new Set(selected);
  const toggle = (task: string, on: boolean) => onChange(tasks.filter((t) => (t === task ? on : chosen.has(t))));
  return (
    <div className="rounded-lg border border-line">
      <div className="flex items-center justify-between border-b border-line px-3 py-2 text-[13px]">
        <span className="text-subtle" aria-live="polite">
          {selected.length} of {tasks.length} selected
        </span>
        <span className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={() => onChange([...tasks])} disabled={selected.length === tasks.length}>
            Select all
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onChange([])} disabled={selected.length === 0}>
            Clear
          </Button>
        </span>
      </div>
      <ul className="max-h-64 divide-y divide-line overflow-y-auto" aria-label="Tasks">
        {tasks.map((task) => {
          const id = `${prefix}-${task}`;
          return (
            <li key={task} className="flex items-center gap-3 px-3 py-2 hover:bg-selected/50">
              <Checkbox id={id} checked={chosen.has(task)} onCheckedChange={(v) => toggle(task, v === true)} />
              <label htmlFor={id} className="flex-1 cursor-pointer font-mono text-[13px]">
                {task}
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
