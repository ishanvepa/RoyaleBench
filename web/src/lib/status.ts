import {
  CheckCircle2,
  CircleDashed,
  Clock,
  FlaskConical,
  Hammer,
  Loader2,
  PauseCircle,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { Tone } from "@/components/ui/badge";

export interface StatusMeta {
  label: string;
  tone: Tone;
  icon: LucideIcon;
  spin?: boolean;
  /** Tailwind background class for a progress segment. */
  bar: string;
}

export const RUN_STATUS_META: Record<string, StatusMeta> = {
  IN_PROGRESS: { label: "Running", tone: "info", icon: Loader2, spin: true, bar: "bg-info" },
  STOPPING: { label: "Stopping", tone: "warning", icon: PauseCircle, bar: "bg-warning/70" },
  STOPPED: { label: "Stopped", tone: "neutral", icon: PauseCircle, bar: "bg-warning/70" },
  FINISHED: { label: "Finished", tone: "success", icon: CheckCircle2, bar: "bg-success" },
  ERROR: { label: "Failed", tone: "danger", icon: XCircle, bar: "bg-danger" },
};

export const TASK_STATUS_META: Record<string, StatusMeta> = {
  PENDING: { label: "Queued", tone: "neutral", icon: Clock, bar: "bg-line" },
  BUILDING: { label: "Building", tone: "info", icon: Hammer, bar: "bg-info/55" },
  IN_PROGRESS: { label: "Running", tone: "info", icon: Loader2, spin: true, bar: "bg-info" },
  EVALUATING: { label: "Grading", tone: "info", icon: FlaskConical, bar: "bg-info/80" },
  FINISHED: { label: "Done", tone: "success", icon: CheckCircle2, bar: "bg-success" },
  ERROR: { label: "Error", tone: "danger", icon: XCircle, bar: "bg-danger" },
  STOPPED: { label: "Stopped", tone: "neutral", icon: PauseCircle, bar: "bg-warning/70" },
};

export const ARENA_STATUS_META: Record<string, StatusMeta> = {
  queued: { label: "Queued", tone: "neutral", icon: Clock, bar: "bg-line" },
  running: { label: "Running", tone: "info", icon: Loader2, spin: true, bar: "bg-info" },
  done: { label: "Done", tone: "success", icon: CheckCircle2, bar: "bg-success" },
  stopped: { label: "Stopped", tone: "warning", icon: PauseCircle, bar: "bg-warning/70" },
  crashed: { label: "Crashed", tone: "danger", icon: XCircle, bar: "bg-danger" },
  skipped: { label: "Skipped", tone: "outline", icon: CircleDashed, bar: "bg-line" },
};

const UNKNOWN: StatusMeta = { label: "Unknown", tone: "outline", icon: CircleDashed, bar: "bg-line" };

/** Never throws: a status Valkyrie adds later still renders, with its raw name. */
export function statusMeta(kind: "run" | "task" | "arena", status: string): StatusMeta {
  const table = kind === "run" ? RUN_STATUS_META : kind === "task" ? TASK_STATUS_META : ARENA_STATUS_META;
  return table[status] ?? { ...UNKNOWN, label: status || UNKNOWN.label };
}

/** Segments of a task progress bar, left to right. */
export const TASK_PROGRESS_ORDER = ["FINISHED", "EVALUATING", "IN_PROGRESS", "BUILDING", "PENDING", "ERROR", "STOPPED"] as const;
