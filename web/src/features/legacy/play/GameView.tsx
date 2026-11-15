import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import type { PlayState } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CodeBlock } from "@/components/ui/code-block";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Metric } from "@/components/ui/metric";
import { useAbandonGame, usePlayMove } from "../api/play";
import { Board } from "./Board";
import { clock } from "./geometry";
import { MovePicker } from "./MovePicker";
import { markersFor, type MovePreview } from "./moves";

const OUTCOME: Record<number, string> = { 0: "You win!", 2: "Draw." };

function Hand({ state }: { state: PlayState }) {
  return (
    <section aria-label="Your hand" className="space-y-2">
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {state.hand.map((card) => (
          <li key={card.slot} className="flex items-center justify-between gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-[13px]">
            <span className="min-w-0">
              <span className="block truncate font-medium">{card.name}</span>
              <span className="block text-xs text-muted">{card.kind.toLowerCase()}</span>
            </span>
            <span aria-label={`${card.cost} elixir`} className="grid size-6 shrink-0 place-items-center rounded-full bg-ink text-xs font-semibold text-background">
              {card.cost}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">Next card: {state.next_card}</p>
    </section>
  );
}

function ElixirBar({ elixir }: { elixir: number }) {
  return (
    <div
      role="progressbar"
      aria-label="Your elixir"
      aria-valuemin={0}
      aria-valuemax={10}
      aria-valuenow={Math.round(elixir * 10) / 10}
      className="h-2 overflow-hidden rounded-full bg-selected"
    >
      <div className="h-full rounded-full transition-[width] duration-300" style={{ width: `${Math.min(100, elixir * 10)}%`, background: "var(--rb-side-blue)" }} />
    </div>
  );
}

function GameOver({ state, onAgain }: { state: PlayState; onAgain: () => void }) {
  const outcome = state.winner === 1 ? `${state.opponent} wins.` : (OUTCOME[state.winner ?? -1] ?? "Game over.");
  return (
    <Card>
      <CardContent className="space-y-3">
        <h2 className="text-xl">
          {outcome} <span className="text-muted">{state.crowns[0]}–{state.crowns[1]}</span>
        </h2>
        {state.saved_as ? (
          <p className="text-[13px] text-subtle">
            Saved as <code className="font-mono text-xs">{state.saved_as}</code>.{" "}
            <Link className="underline underline-offset-4" to={`/legacy/matches/human-play/${state.saved_as}`}>
              Open the replay and the opponent&rsquo;s reasoning
            </Link>
            .
          </p>
        ) : null}
        {state.save_error ? (
          <Banner tone="warning" title="The game finished but could not be saved">
            {state.save_error}
          </Banner>
        ) : null}
        <Button variant="primary" onClick={onAgain}>
          Play again
        </Button>
      </CardContent>
    </Card>
  );
}

interface GameViewProps {
  state: PlayState;
  /** Leave this game (the server forgets it) and return to the setup form. */
  onExit: () => void;
}

export function GameView({ state, onExit }: GameViewProps) {
  const move = usePlayMove(state.id);
  const abandon = useAbandonGame();
  const [preview, setPreview] = useState<MovePreview | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);

  const leave = () => {
    onExit(); // leave first, so the player never waits on the cleanup
    // Best effort: the server also drops idle games by itself, so a failed delete is not worth interrupting anyone for.
    abandon.mutate(state.id);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex flex-wrap items-center gap-2 text-[15px]">
          <b className="inline-flex items-center gap-2"><span aria-hidden className="size-2.5 rounded-full" style={{ background: "var(--rb-side-blue)" }} />You</b>
          <span className="text-muted">vs</span>
          <span className="inline-flex items-center gap-2"><span aria-hidden className="size-2.5 rounded-full" style={{ background: "var(--rb-side-red)" }} /><ModelLabel model={state.opponent} /></span>
        </p>
        <Button variant="secondary" size="sm" onClick={() => (state.over ? leave() : setConfirmLeave(true))}>
          New game
        </Button>
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <div className="mx-auto w-full max-w-[380px] lg:sticky lg:top-6">
          <Board state={state} markers={state.over ? [] : markersFor(state.moves, preview, state.step)} />
        </div>

        <div className="space-y-6">
          <div className="space-y-3">
            <dl className="grid grid-cols-3 gap-3">
              <Metric label="Time left" value={`${clock(state.time_left_s)}${state.overtime ? " OT" : ""}`} />
              <Metric label="Crowns (you–opponent)" value={`${state.crowns[0]}–${state.crowns[1]}`} />
              <Metric label="Your elixir" value={state.elixir.toFixed(1)} />
            </dl>
            <ElixirBar elixir={state.elixir} />
          </div>

          {state.over ? (
            <GameOver state={state} onAgain={leave} />
          ) : (
            <>
              <Hand state={state} />
              {state.events.length > 0 ? <p className="text-[13px] text-subtle">Since your last move: {state.events.join("; ")}</p> : null}
              <MovePicker moves={state.moves} step={state.step} pending={move.isPending} onPlay={(index) => move.mutate(index)} onPreview={setPreview} />
              <div aria-live="polite">
                {move.isPending ? (
                  <p className="flex items-center gap-2 text-[13px] text-subtle">
                    <Loader2 className="size-4 animate-spin" aria-hidden /> Waiting for the opponent&rsquo;s move…
                  </p>
                ) : null}
              </div>
              {move.isError ? (
                <Banner tone="danger" title="That move was not played">
                  {move.error.message} The game has not advanced, so you can choose again.
                </Banner>
              ) : null}
            </>
          )}

          <details className="rounded-lg border border-line bg-surface px-4 py-3 text-[13px]">
            <summary className="cursor-pointer text-subtle">Game log</summary>
            <div className="mt-3">
              <CodeBlock code={state.log.join("\n") || "Nothing yet."} maxHeight="14rem" wrap />
            </div>
          </details>
          {state.opponent_thinking ? (
            <details className="rounded-lg border border-line bg-surface px-4 py-3 text-[13px]">
              <summary className="cursor-pointer text-subtle">{state.opponent}&rsquo;s reasoning (last move)</summary>
              <div className="mt-3 space-y-2">
                <p className="text-xs text-muted">At {state.opponent_thinking.time}</p>
                <CodeBlock code={state.opponent_thinking.text} maxHeight="18rem" wrap />
              </div>
            </details>
          ) : null}
        </div>
      </div>

      <ConfirmDialog
        open={confirmLeave}
        onOpenChange={setConfirmLeave}
        title="Abandon this game?"
        description="It is not saved, and it cannot be resumed."
        confirmLabel="Abandon game"
        destructive
        onConfirm={leave}
      />
    </div>
  );
}
