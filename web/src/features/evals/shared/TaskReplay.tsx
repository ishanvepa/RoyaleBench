import { Play } from "lucide-react";
import { useState } from "react";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useTaskReplay } from "../api/jobs";
import { useEnvironment } from "../api/environment";

function Playback({ runId, taskId }: { runId: string; taskId: string }) {
  const replay = useTaskReplay(runId, taskId);
  const environment = useEnvironment();
  return (
    <QueryBoundary
      query={replay}
      errorTitle="Couldn't load the replay"
      skeleton={
        <div role="status" className="space-y-3">
          <p className="text-sm text-muted">Loading replay…</p>
          <Skeleton className="h-96 w-full" />
        </div>
      }
    >
      {(data) =>
        data.available ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              {environment.data?.fake ? <Badge tone="warning">Sample gameplay</Badge> : null}
              {data.partial ? <Badge tone="warning">Partial replay</Badge> : null}
              <p>
                {environment.data?.fake
                  ? "Sample match used to demonstrate playback in simulated mode."
                  : data.partial
                    ? "This attempt ended before the match finished. Playback shows the recorded portion."
                    : "Recorded referee gameplay from this task attempt."}
              </p>
            </div>
            <iframe
              title={`Replay of ${taskId}`}
              srcDoc={data.html}
              sandbox="allow-scripts"
              className="h-[65vh] min-h-[540px] w-full rounded-lg border border-line bg-surface"
            />
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted">{data.message}</p>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void replay.refetch()}
              loading={replay.isFetching}
            >
              Check again
            </Button>
          </div>
        )
      }
    </QueryBoundary>
  );
}

/** Shared entry point on job task panels and benchmark result rows. */
export function TaskReplay({ runId, taskId }: { runId: string; taskId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        <Play className="size-3.5" aria-hidden /> Watch replay
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        {open ? (
          <DialogContent
            className="max-w-6xl"
            title={`Task replay: ${taskId}`}
            description="Play, pause, scrub the timeline, change speed or switch sides."
          >
            <Playback runId={runId} taskId={taskId} />
          </DialogContent>
        ) : null}
      </Dialog>
    </>
  );
}
