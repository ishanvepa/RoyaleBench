import { Badge, type Tone } from "@/components/ui/badge";

const DIFFICULTY: Record<string, Tone> = {
  easy: "success",
  medium: "warning",
  hard: "danger",
};

export function DifficultyBadge({ difficulty }: { difficulty: string }) {
  const label = difficulty.trim();
  if (!label) return <span className="text-subtle">–</span>;
  return <Badge tone={DIFFICULTY[label.toLowerCase()] ?? "outline"}>{label}</Badge>;
}

const STATE: Record<string, { label: string; tone: Tone; title: string }> = {
  published: { label: "Published", tone: "success", title: "The local files match the latest published version." },
  modified: { label: "Modified", tone: "warning", title: "Local files differ from the latest published version. Publish to run the changes." },
  draft: { label: "Draft", tone: "warning", title: "Not published to Valkyrie yet, so it cannot run." },
  "remote only": { label: "Remote only", tone: "info", title: "Published on Valkyrie, but there is no local folder for it." },
};

/** Where a benchmark stands between the local folder and Valkyrie. */
export function BenchmarkStateBadge({ state }: { state: string }) {
  const s = STATE[state] ?? { label: state, tone: "outline" as Tone, title: state };
  return (
    <Badge tone={s.tone} title={s.title}>
      {s.label}
    </Badge>
  );
}

const SYNC: Record<string, { label: string; tone: Tone }> = {
  "in sync": { label: "In sync", tone: "success" },
  modified: { label: "Modified", tone: "warning" },
  "not published": { label: "Not published", tone: "warning" },
  "published only": { label: "Published only", tone: "info" },
};

/** One task: does the local copy match the published one? */
export function SyncBadge({ sync }: { sync: string }) {
  const s = SYNC[sync] ?? { label: sync, tone: "outline" as Tone };
  return <Badge tone={s.tone}>{s.label}</Badge>;
}
