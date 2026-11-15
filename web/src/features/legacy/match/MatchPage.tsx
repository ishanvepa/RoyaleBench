import { useState } from "react";
import { useParams } from "react-router";
import type { MatchReport } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { StatusPill } from "@/components/domain/StatusPill";
import { Duration } from "@/components/domain/values";
import { Banner } from "@/components/ui/banner";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { Button } from "@/components/ui/button";
import { Metric } from "@/components/ui/metric";
import { PageHeader } from "@/components/ui/page-header";
import { DASH } from "@/lib/format";
import { useMatch } from "../api/jobs";
import { DecisionsTable } from "./DecisionsTable";
import { MatchCharts } from "./MatchCharts";

export function Component() {
  const { job = "", matchId = "" } = useParams();
  const match = useMatch(job, matchId);
  return (
    <div>
      <Breadcrumbs items={[{ label: "Overview", to: "/legacy/overview" }, { label: job, to: `/legacy/jobs/${job}` }, { label: matchId }]} />
      <QueryBoundary query={match} errorTitle="Couldn't load this match">
        {(data) => <MatchView data={data} job={job} />}
      </QueryBoundary>
    </div>
  );
}

function Replay({ job, matchId, hasReplay, done }: { job: string; matchId: string; hasReplay: boolean; done: boolean }) {
  const [open, setOpen] = useState(false);
  if (!hasReplay) {
    return (
      <p className="text-[13px] text-muted">
        {done
          ? "No replay was saved for this game: only the first few games of each pairing keep one (replays_per_pair in the config). The decisions above are always logged."
          : "A replay is saved when the match finishes."}
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {open ? null : (
        <Button variant="secondary" onClick={() => setOpen(true)}>
          Show replay
        </Button>
      )}
      {open ? (
        // The viewer is generated from our own trace file, but it runs script: sandbox it so it cannot reach this app.
        <iframe
          title={`Replay of ${matchId}`}
          src={`/api/legacy/jobs/${job}/matches/${matchId}/replay`}
          sandbox="allow-scripts"
          className="h-[900px] w-full rounded-xl border border-line bg-surface"
        />
      ) : null}
    </div>
  );
}

function MatchView({ data, job }: { data: MatchReport; job: string }) {
  const crowns = data.crowns ? `${data.crowns[0]}-${data.crowns[1]}` : DASH;
  return (
    <div className="space-y-8">
      <PageHeader
        title={
          <span className="flex flex-wrap items-center gap-x-3">
            <span className="inline-flex items-center gap-2"><span aria-hidden className="size-2.5 rounded-full" style={{ background: "var(--rb-side-blue)" }} />{data.blue}</span>
            <span className="text-muted">vs</span>
            <span className="inline-flex items-center gap-2"><span aria-hidden className="size-2.5 rounded-full" style={{ background: "var(--rb-side-red)" }} />{data.red}</span>
          </span>
        }
        meta={<StatusPill kind="arena" status={data.status} />}
        description={data.match_id}
      />
      {data.error ? (
        <Banner tone="danger" title="This match crashed">
          <span className="whitespace-pre-wrap">{data.error}</span>
        </Banner>
      ) : null}
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Status" value={<span className="text-xl">{data.status}</span>} />
        <Metric label="Winner" value={data.winner && data.winner !== "draw" ? <span className="text-xl"><ModelLabel model={data.winner} /></span> : <span className="text-xl">{data.winner ?? DASH}</span>} />
        <Metric label="Crowns (blue-red)" value={crowns} />
        <Metric label="Wall time" value={<Duration seconds={data.wall_s} />} />
      </dl>
      {data.decks ? (
        <p className="text-[13px] text-subtle">
          <b>Decks</b> · blue: {data.decks.blue.join(", ")} · red: {data.decks.red.join(", ")}
        </p>
      ) : data.deck ? (
        <p className="text-[13px] text-subtle">
          <b>Deck (mirror)</b> · {data.deck.join(", ")}
        </p>
      ) : null}
      {data.decisions.length === 0 ? (
        <Banner tone="neutral" title="No decisions logged yet" />
      ) : (
        <>
          <MatchCharts decisions={data.decisions} blue={data.blue} red={data.red} />
          <DecisionsTable job={job} matchId={data.match_id} decisions={data.decisions} />
        </>
      )}
      <section className="space-y-3">
        <h2 className="text-lg">Replay</h2>
        <Replay job={job} matchId={data.match_id} hasReplay={data.has_replay} done={data.status === "done"} />
      </section>
    </div>
  );
}
