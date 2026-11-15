import { Activity, BarChart3, Grid2x2 } from "lucide-react";
import { z } from "zod";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { boolParam, enumParam, stringParam, useSearchState } from "@/hooks/useSearchState";
import { useArenaResults, useArenaRuns } from "../api/results";
import { AboutView } from "./AboutView";
import { GamesView } from "./GamesView";
import { PerformanceView } from "./PerformanceView";
import { runLabel, type MetricKey } from "./stats";
import { StandingsView } from "./StandingsView";

const VIEWS = ["standings", "performance", "games", "about"] as const;
const searchSchema = z.object({
  kind: enumParam(["round_robin", "duel"] as const, "round_robin"),
  run: stringParam(),
  view: enumParam(VIEWS, "standings"),
  metric: enumParam(["wins", "win_rate", "crowns", "reliability"] as const, "wins"),
  q: stringParam(),
  details: boolParam(),
  player: stringParam(),
});

export function Component() {
  const [state, setState] = useSearchState(searchSchema);
  const runs = useArenaRuns();
  return (
    <div>
      <PageHeader title="Leaderboard" description="How language models rank playing Clash Royale against each other. Each tournament or battle has its own standings." />
      <QueryBoundary query={runs} errorTitle="Couldn't load results">
        {(data) => {
          if (data.runs.length === 0) {
            return <EmptyState title="No results yet" description="Start a model battle from Play, or run a tournament, and its standings appear here." />;
          }
          const available = data.runs.filter((r) => r.format === state.kind).sort((a, b) => Number(b.scored_games > 0) - Number(a.scored_games > 0));
          const selected = available.find((r) => r.name === state.run) ?? available[0];
          return (
            <div className="space-y-6">
              <div className="flex flex-wrap items-end gap-4">
                <SegmentedControl
                  aria-label="Competition"
                  value={state.kind}
                  onValueChange={(kind) => setState({ kind, run: "", player: "" })}
                  options={[{ value: "round_robin", label: "Round robin" }, { value: "duel", label: "1 v 1" }]}
                />
                {available.length > 0 ? (
                  <div className="min-w-[320px] flex-1 sm:max-w-xl">
                    <Select
                      aria-label={state.kind === "round_robin" ? "Tournament" : "Battle"}
                      value={selected?.name ?? ""}
                      onValueChange={(run) => setState({ run, player: "", q: "" })}
                      options={available.map((r) => ({ value: r.name, label: runLabel(r) }))}
                    />
                  </div>
                ) : null}
              </div>
              {!selected ? (
                <EmptyState title={state.kind === "duel" ? "No battles yet" : "No round-robin tournaments yet"} description="Individual battles are under 1 v 1." />
              ) : selected.scored_games === 0 ? (
                <EmptyState title="No finished games" description={`This ${state.kind === "duel" ? "battle" : "tournament"} has no finished games yet (${selected.status.replace(/_/g, " ")}), so there are no standings to display.`} />
              ) : (
                <ResultsTabs job={selected.name} state={state} setState={setState} />
              )}
            </div>
          );
        }}
      </QueryBoundary>
    </div>
  );
}

function ResultsTabs({ job, state, setState }: { job: string; state: z.infer<typeof searchSchema>; setState: (patch: Partial<z.infer<typeof searchSchema>>) => void }) {
  const results = useArenaResults(job);
  return (
    <QueryBoundary query={results} errorTitle="Couldn't load these standings">
      {(data) => (
        <Tabs value={state.view} onValueChange={(view) => setState({ view: view as (typeof VIEWS)[number] })}>
          <TabsList aria-label="Result views" className="justify-center">
            <TabsTrigger value="standings"><BarChart3 className="mr-2 inline size-4" aria-hidden />Standings</TabsTrigger>
            <TabsTrigger value="performance"><Activity className="mr-2 inline size-4" aria-hidden />Performance</TabsTrigger>
            <TabsTrigger value="games"><Grid2x2 className="mr-2 inline size-4" aria-hidden />Match history</TabsTrigger>
            <TabsTrigger value="about">About</TabsTrigger>
          </TabsList>
          <TabsContent value="standings"><StandingsView results={data} state={{ q: state.q, details: state.details }} onChange={setState} /></TabsContent>
          <TabsContent value="performance"><PerformanceView results={data} metric={state.metric as MetricKey} onMetricChange={(metric) => setState({ metric })} /></TabsContent>
          <TabsContent value="games"><GamesView results={data} player={state.player} onPlayerChange={(player) => setState({ player })} /></TabsContent>
          <TabsContent value="about"><AboutView /></TabsContent>
        </Tabs>
      )}
    </QueryBoundary>
  );
}
