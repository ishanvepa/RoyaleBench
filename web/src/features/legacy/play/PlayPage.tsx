import { z } from "zod";
import { ApiError } from "@/api/client";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { enumParam, stringParam, useSearchState } from "@/hooks/useSearchState";
import { useGame, usePlayOptions } from "../api/play";
import { BattlePanel } from "./BattlePanel";
import { GameView } from "./GameView";
import { SetupForm } from "./SetupForm";

const MODES = ["human", "battle"] as const;
const searchSchema = z.object({
  mode: enumParam(MODES, "human"),
  /** The game being played; keeping it in the URL lets a reload pick the game up where it was. */
  game: stringParam(),
  battle: stringParam(),
});

function BoardSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]" role="status" aria-label="Loading the game">
      <Skeleton className="aspect-[9/16] w-full max-w-[380px]" />
      <Skeleton className="h-96 w-full" />
    </div>
  );
}

function GameLoader({ id, onExit }: { id: string; onExit: () => void }) {
  const game = useGame(id);
  if (game.error instanceof ApiError && game.error.code === "not_found") {
    return (
      <EmptyState
        title="This game is no longer available"
        description="The server forgot it. Games are kept in memory, so a restart or two idle hours ends them. Finished games are saved and stay under Overview."
        action={<Button variant="primary" onClick={onExit}>Start a new game</Button>}
      />
    );
  }
  return (
    <QueryBoundary query={game} errorTitle="Couldn't load the game" skeleton={<BoardSkeleton />}>
      {(state) => <GameView state={state} onExit={onExit} />}
    </QueryBoundary>
  );
}

function HumanPlay({ game, onStarted, onExit }: { game: string; onStarted: (id: string) => void; onExit: () => void }) {
  const options = usePlayOptions();
  return (
    <div className="space-y-6">
      {game ? null : (
        <p className="text-[13px] text-muted">
          You play blue, at the bottom, through exactly the interface the models get: every few seconds of game time you pick one move from the legal-move list, and the game pauses while you decide.
          Finished games are saved under the job <b className="font-medium text-subtle">human-play</b>.
        </p>
      )}
      <Banner tone="info" title="Want real time?">
        For a real-time game against the planner bot (no pausing, drag cards onto the arena), run <code className="font-mono text-xs">uv run python -m cr_arena.live</code> and open{" "}
        <a className="underline underline-offset-4" href="http://localhost:8600" target="_blank" rel="noreferrer">
          http://localhost:8600
        </a>
        .
      </Banner>
      {game ? (
        <GameLoader id={game} onExit={onExit} />
      ) : (
        <QueryBoundary query={options} errorTitle="Couldn't load the play options">
          {(data) => <SetupForm options={data} onStarted={onStarted} />}
        </QueryBoundary>
      )}
    </div>
  );
}

export function Component() {
  const [{ mode, game, battle }, setState] = useSearchState(searchSchema);
  return (
    <div>
      <PageHeader title="Play" description="Play a game yourself against a bot or a model, or set two models against each other." />
      <Tabs value={mode} onValueChange={(next) => setState({ mode: next as (typeof MODES)[number] })}>
        <TabsList aria-label="Play modes">
          <TabsTrigger value="human">Play a game</TabsTrigger>
          <TabsTrigger value="battle">Model battle</TabsTrigger>
        </TabsList>
        <TabsContent value="human">
          <HumanPlay game={game} onStarted={(id) => setState({ game: id }, { replace: false })} onExit={() => setState({ game: "" })} />
        </TabsContent>
        <TabsContent value="battle">
          <BattlePanel battle={battle} onSelect={(name) => setState({ battle: name })} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
