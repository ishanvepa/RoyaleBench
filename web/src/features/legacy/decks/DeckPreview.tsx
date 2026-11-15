import { X } from "lucide-react";
import type { CardInfo } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Metric } from "@/components/ui/metric";
import { averageElixir, DECK_SIZE } from "./deckStats";

interface DeckPreviewProps {
  pool: readonly CardInfo[];
  selected: readonly string[];
  onRemove?: (name: string) => void;
}

/** The chosen cards in the order they were picked, and what the deck costs on average. */
export function DeckPreview({ pool, selected, onRemove }: DeckPreviewProps) {
  const info = new Map(pool.map((card) => [card.name, card]));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Deck preview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {selected.length === 0 ? (
          <p className="text-[13px] text-muted">Choose cards to preview your deck and average elixir cost.</p>
        ) : (
          <>
            <dl>
              <Metric label="Average elixir" value={averageElixir(pool, selected).toFixed(1)} hint={`${selected.length} of ${DECK_SIZE} cards`} />
            </dl>
            <ul className="space-y-1.5" aria-label="Selected cards">
              {selected.map((name) => {
                const card = info.get(name);
                return (
                  <li key={name} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-[13px]">
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{name}</span>
                      <span className="block text-xs text-muted">{card ? `${card.kind} · ${card.elixir} elixir` : "Unknown card"}</span>
                    </span>
                    {onRemove ? (
                      <Button variant="ghost" size="icon" aria-label={`Remove ${name}`} onClick={() => onRemove(name)}>
                        <X className="size-4" aria-hidden />
                      </Button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
