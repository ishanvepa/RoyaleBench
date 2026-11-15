import { useMemo, useState } from "react";
import type { CardInfo } from "@/api/types";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { DECK_SIZE, filterCards, toggleCard, type KindFilter } from "./deckStats";

const KINDS: readonly { value: KindFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "Troop", label: "Troops" },
  { value: "Building", label: "Buildings" },
  { value: "Spell", label: "Spells" },
];

interface CardPickerProps {
  cards: readonly CardInfo[];
  selected: readonly string[];
  onChange: (names: string[]) => void;
  max?: number;
  /** Ids of elements that describe the picker (hints, errors). */
  describedBy?: string;
  disabled?: boolean;
}

/**
 * Pick cards from the pool: search, filter by type, click to add or remove. Once ``max`` cards are chosen the
 * rest are disabled, so a deck can never hold more than the engine allows. Every card is a real toggle button,
 * so the whole picker works from the keyboard and with a screen reader.
 */
export function CardPicker({ cards, selected, onChange, max = DECK_SIZE, describedBy, disabled = false }: CardPickerProps) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");
  const shown = useMemo(() => filterCards(cards, query, kind), [cards, query, kind]);
  const chosen = useMemo(() => new Set(selected), [selected]);
  const full = selected.length >= max;

  return (
    <fieldset className="space-y-3" aria-describedby={describedBy} disabled={disabled}>
      <legend className="sr-only">Cards</legend>
      <div className="flex flex-wrap items-center gap-3">
        <Input type="search" aria-label="Search cards" placeholder="Search for a card…" value={query} onChange={(e) => setQuery(e.target.value)} className="w-56" />
        <SegmentedControl aria-label="Card type" value={kind} onValueChange={setKind} options={KINDS} />
        <span className="ml-auto text-[13px] tabular-nums text-subtle" aria-live="polite">
          {selected.length} / {max} selected
        </span>
      </div>
      <ul className="grid max-h-[26rem] grid-cols-2 gap-2 overflow-y-auto pr-1 sm:grid-cols-3 xl:grid-cols-4" aria-label="Card pool">
        {shown.map((card) => {
          const on = chosen.has(card.name);
          return (
            <li key={card.name}>
              <button
                type="button"
                aria-pressed={on}
                aria-label={`${card.name}, ${card.elixir} elixir, ${card.kind.toLowerCase()}`}
                disabled={full && !on}
                onClick={() => onChange(toggleCard(selected, card.name, max))}
                className="flex w-full items-center justify-between gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-left text-[13px] transition-colors hover:border-focus aria-pressed:border-ink aria-pressed:bg-selected disabled:cursor-not-allowed disabled:opacity-40"
              >
                <span className="min-w-0">
                  <span className="block truncate font-medium">{card.name}</span>
                  <span className="block text-xs text-muted">{card.kind}</span>
                </span>
                <span aria-hidden className="grid size-6 shrink-0 place-items-center rounded-full bg-ink text-xs font-semibold text-background">
                  {card.elixir}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {shown.length === 0 ? <p className="text-[13px] text-muted">No cards match your search.</p> : null}
    </fieldset>
  );
}
