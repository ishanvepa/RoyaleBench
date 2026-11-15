import { Pause } from "lucide-react";
import { useMemo } from "react";
import type { PlayMove } from "@/api/types";
import { Button } from "@/components/ui/button";
import { groupMoves, type MovePreview } from "./moves";

interface MovePickerProps {
  moves: readonly PlayMove[];
  step: number;
  /** True while a move is being played; nothing can be chosen until the opponent has replied. */
  pending: boolean;
  onPlay: (index: number) => void;
  onPreview: (preview: MovePreview | null) => void;
}

/**
 * Every legal move, as buttons. This list is the real control: the board only shows where a move would land,
 * so the game is fully playable by keyboard and screen reader.
 */
export function MovePicker({ moves, step, pending, onPlay, onPreview }: MovePickerProps) {
  const { wait, groups } = useMemo(() => groupMoves(moves), [moves]);
  return (
    <section aria-label="Your move" className="space-y-3">
      <h2 className="text-base">Your move</h2>
      {wait ? (
        <Button variant="secondary" className="w-full" disabled={pending} onClick={() => onPlay(wait.index)}>
          <Pause className="size-4" aria-hidden /> Wait (save elixir)
        </Button>
      ) : null}
      {groups.map((group) => (
        <div key={group.card} role="group" aria-label={`${group.card} placements`} className="rounded-lg border border-line p-3">
          <p className="mb-2 text-[13px] font-medium">
            {group.card} <span className="font-normal text-muted">({group.cost}, {group.kind.toLowerCase()})</span>
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {group.moves.map((move) => {
              const preview = () => onPreview({ step, card: group.card, index: move.index });
              return (
                <Button
                  key={move.index}
                  size="sm"
                  variant="secondary"
                  disabled={pending}
                  aria-label={`${group.card}: ${move.target}`}
                  onClick={() => onPlay(move.index)}
                  onMouseEnter={preview}
                  onFocus={preview}
                  onMouseLeave={() => onPreview(null)}
                  onBlur={() => onPreview(null)}
                >
                  {move.target}
                </Button>
              );
            })}
          </div>
        </div>
      ))}
    </section>
  );
}
