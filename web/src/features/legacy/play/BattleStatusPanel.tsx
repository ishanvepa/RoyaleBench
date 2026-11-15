import { Link } from "react-router";
import { ApiError } from "@/api/client";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Badge } from "@/components/ui/badge";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { EmptyState } from "@/components/ui/empty-state";
import { useBattle } from "../api/play";

/** The launched battle, followed live: its state, the runner's log, and links to the job once it exists. */
export function BattleStatusPanel({ name }: { name: string }) {
  const battle = useBattle(name);
  if (battle.error instanceof ApiError && battle.error.code === "not_found") {
    return <EmptyState title="This server has no record of that battle" description={battle.error.message} />;
  }
  return (
    <QueryBoundary query={battle} errorTitle="Couldn't load the battle">
      {(status) => (
        <Card aria-label={`Battle ${status.name}`}>
          <CardHeader>
            <div>
              <CardTitle>{status.name}</CardTitle>
              {status.players.length ? <p className="mt-0.5 text-[13px] text-muted">{status.players.join(" vs ")}</p> : null}
            </div>
            {status.state === "running" ? <Badge tone="info">running</Badge> : status.state === "done" ? <Badge tone="success">finished</Badge> : <Badge tone="danger">failed</Badge>}
          </CardHeader>
          <CardContent className="space-y-4">
            {status.state === "running" ? (
              <Banner tone="info" title="The battle runner is active">
                This page updates by itself. Keep the server running while the battle plays.
              </Banner>
            ) : status.state === "done" ? (
              <Banner tone="info" title="The battle runner finished">
                Open the job to see the results and any games that need a retry.
              </Banner>
            ) : (
              <Banner tone="danger" title={`The battle runner exited with code ${status.exit_code ?? "?"}`}>
                Check the log below.
              </Banner>
            )}
            {status.job_exists ? (
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="secondary">
                  <Link to={`/legacy/jobs/${status.name}`}>View progress and results</Link>
                </Button>
                <Button asChild variant="secondary">
                  <Link to={`/legacy/jobs/${status.name}?tab=matches`}>View matches and replays</Link>
                </Button>
              </div>
            ) : null}
            <details open={status.state === "failed"} className="text-[13px]">
              <summary className="cursor-pointer text-subtle">Battle log</summary>
              <div className="mt-3">
                <CodeBlock code={status.output || "Starting the runner…"} maxHeight="20rem" wrap />
              </div>
            </details>
          </CardContent>
        </Card>
      )}
    </QueryBoundary>
  );
}
