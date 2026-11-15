import { z } from "zod";
import type { DeckList, DeckOut } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { stringParam, useSearchState } from "@/hooks/useSearchState";
import { useReadOnly } from "@/hooks/useServerInfo";
import { useDecks } from "../api/decks";
import { DeckBuilder } from "./DeckBuilder";

/** Stands for "no saved deck": the editor builds a new one. Radix cannot hold an empty option value. */
const NEW_DECK = "__new__";
const searchSchema = z.object({ deck: stringParam() });

export function Component() {
  const decks = useDecks();
  return (
    <div>
      <PageHeader title="Decks" description="Build an eight-card deck, save it, and choose it in Play. Saved decks are shared across this arena." />
      <QueryBoundary query={decks} errorTitle="Couldn't load the decks">
        {(data) => <DecksView data={data} />}
      </QueryBoundary>
    </div>
  );
}

function DeckSummary({ deck, onEdit }: { deck: DeckOut; onEdit?: () => void }) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-[15px]">{deck.name}</h3>
          <p className="mt-1 text-[13px] text-subtle">{deck.cards.join(", ")}</p>
          <p className="mt-1 text-xs text-muted">Average elixir {deck.avg_elixir.toFixed(1)}</p>
        </div>
        {onEdit ? (
          <Button variant="secondary" size="sm" onClick={onEdit} aria-label={`Edit ${deck.name}`}>
            Edit
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

function DecksView({ data }: { data: DeckList }) {
  const [{ deck: deckParam }, setState] = useSearchState(searchSchema);
  const readOnly = useReadOnly();
  const saved = data.decks.filter((d) => !d.preset);
  const presets = data.decks.filter((d) => d.preset);
  const editing = saved.find((d) => d.id === deckParam) ?? null;
  const vanished = deckParam !== "" && editing === null;

  return (
    <div className="space-y-10">
      <section className="space-y-4" aria-label="Build a deck">
        <div className="w-full max-w-sm">
          <Select
            aria-label="Edit a deck"
            value={editing?.id ?? NEW_DECK}
            onValueChange={(v) => setState({ deck: v === NEW_DECK ? "" : v }, { replace: false })}
            options={[{ value: NEW_DECK, label: "Create a new deck" }, ...saved.map((d) => ({ value: d.id ?? "", label: d.name, hint: `average elixir ${d.avg_elixir.toFixed(1)}` }))]}
          />
        </div>
        {vanished ? (
          <Banner tone="warning" title="That deck no longer exists">
            It was deleted, possibly by someone else. You are building a new one instead.
          </Banner>
        ) : null}
        {/* Changing the key remounts the builder, so switching decks starts from that deck's saved values. */}
        <DeckBuilder
          key={editing?.id ?? NEW_DECK}
          deck={editing}
          presets={presets}
          pool={data.cards}
          readOnly={readOnly}
          onSaved={(saved) => setState({ deck: saved.id ?? "" })}
          onDeleted={() => setState({ deck: "" })}
        />
      </section>

      <section className="space-y-4" aria-label="Saved decks">
        <h2 className="text-lg">Saved decks</h2>
        {saved.length === 0 ? (
          <EmptyState title="No custom decks yet" description="Build your first deck above and it will appear here and in Play." />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {saved.map((deck) => (
              <DeckSummary key={deck.key} deck={deck} onEdit={() => setState({ deck: deck.id ?? "" }, { replace: false })} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-4" aria-label="Preset decks">
        <h2 className="text-lg">Preset decks</h2>
        <p className="text-[13px] text-muted">Classic archetypes that ship with the arena. Use one as a starting point in the builder.</p>
        <div className="grid gap-3 md:grid-cols-2">
          {presets.map((deck) => (
            <DeckSummary key={deck.key} deck={deck} />
          ))}
        </div>
      </section>
    </div>
  );
}
