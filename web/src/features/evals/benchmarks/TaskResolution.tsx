import { Play } from "lucide-react";
import { useState } from "react";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useTaskResolution } from "../api/benchmarks";

function Playback({ benchmark, taskId }: { benchmark: string; taskId: string }) {
  const resolution = useTaskResolution(benchmark, taskId);
  return (
    <QueryBoundary
      query={resolution}
      errorTitle="Couldn't load the resolution"
      skeleton={
        <div role="status" className="space-y-3">
          <p className="text-sm text-muted">Loading resolution…</p>
          <Skeleton className="h-96 w-full" />
        </div>
      }
    >
      {(data) =>
        data.available ? (
          <div className="space-y-3">
            <p className="text-xs text-muted">Docker-validated reference gameplay for the current local task version. Older run revisions may differ. The agent does not see this solution.</p>
            <iframe
              title={`Resolution of ${taskId}`}
              srcDoc={data.html}
              sandbox="allow-scripts"
              className="h-[65vh] min-h-[540px] w-full rounded-lg border border-line bg-surface"
            />
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted">{data.message}</p>
            <Button variant="secondary" size="sm" onClick={() => void resolution.refetch()} loading={resolution.isFetching}>
              Check again
            </Button>
          </div>
        )
      }
    </QueryBoundary>
  );
}

export function TaskResolution({ benchmark, taskId }: { benchmark: string; taskId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        <Play className="size-3.5" aria-hidden /> View resolution
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        {open ? (
          <DialogContent
            className="max-w-6xl"
            title={`Task resolution: ${taskId}`}
            description="Play, pause, scrub the timeline, change speed or switch sides."
          >
            <Playback benchmark={benchmark} taskId={taskId} />
          </DialogContent>
        ) : null}
      </Dialog>
    </>
  );
}
