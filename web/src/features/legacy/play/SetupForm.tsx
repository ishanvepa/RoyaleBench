import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { fieldErrors } from "@/api/client";
import type { DeckOut, PlayOptions, PlayOpponent } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useReadOnly } from "@/hooks/useServerInfo";
import { useStartGame } from "../api/play";

/** Stands for "the opponent plays the same deck as you" in the opponent-deck list. */
const SAME_DECK = "__same__";

const schema = z.object({
  opponent: z.string().min(1, "Choose an opponent"),
  deck: z.string().min(1, "Choose your deck"),
  opponentDeck: z.string().min(1, "Choose the opponent's deck"),
  seed: z.number({ error: "Enter a whole number" }).int("Enter a whole number").min(1, "At least 1").max(10_000, "At most 10,000"),
  ticks: z.string().min(1, "Choose an interval"),
});
type Values = z.infer<typeof schema>;

/** Decision interval shown in seconds of game time (the engine counts 20 ticks per second). */
const tickLabel = (ticks: number): string => `${ticks / 20} s`;

const opponentHint = (o: PlayOpponent) => (o.kind === "bot" ? "Reference bot, no API calls" : [o.provider, o.model].filter(Boolean).join(" · "));

function DeckLine({ deck }: { deck: DeckOut | undefined }) {
  if (!deck) return null;
  return (
    <p className="text-xs text-muted">
      <b className="font-medium text-subtle">{deck.name}</b>: {deck.cards.join(", ")}
    </p>
  );
}

export function SetupForm({ options, onStarted }: { options: PlayOptions; onStarted: (gameId: string) => void }) {
  const start = useStartGame();
  const readOnly = useReadOnly();
  const ordered = [...options.opponents].sort((a, b) => Number(a.kind !== "bot") - Number(b.kind !== "bot"));
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: {
      opponent: ordered[0]?.name ?? "",
      deck: options.decks[0]?.key ?? "",
      opponentDeck: SAME_DECK,
      seed: 1,
      ticks: String(options.tick_choices.includes(40) ? 40 : (options.tick_choices[0] ?? 40)),
    },
  });
  const { register, setValue, handleSubmit, watch, formState } = form;
  const { errors, isValid } = formState;
  const values = watch();

  const serverFields = fieldErrors(start.error);
  const unexplained = start.isError && Object.keys(serverFields).length === 0;
  const edited = () => {
    if (start.isError) start.reset();
  };
  const choose = (field: "opponent" | "deck" | "opponentDeck" | "ticks") => (value: string) => {
    edited();
    setValue(field, value, { shouldValidate: true, shouldDirty: true });
  };

  const opponent = options.opponents.find((o) => o.name === values.opponent);
  const mine = options.decks.find((d) => d.key === values.deck);
  const theirs = values.opponentDeck === SAME_DECK ? undefined : options.decks.find((d) => d.key === values.opponentDeck);
  const deckOptions = options.decks.map((d) => ({ value: d.key, label: d.name, hint: `${d.preset ? "Preset" : "Saved"} · average elixir ${d.avg_elixir.toFixed(1)}` }));

  const submit = handleSubmit((v) => {
    start.mutate(
      { opponent: v.opponent, deck: v.deck, opponent_deck: v.opponentDeck === SAME_DECK ? null : v.opponentDeck, seed: v.seed, ticks: Number(v.ticks) },
      { onSuccess: (state) => onStarted(state.id) },
    );
  });

  return (
    <form onSubmit={(e) => void submit(e)} noValidate aria-label="Start a game">
      <Card>
        <CardHeader>
          <CardTitle>New game</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Opponent" error={errors.opponent?.message ?? serverFields.opponent}>
              {(c) => (
                <Select
                  id={c.id}
                  value={values.opponent}
                  onValueChange={choose("opponent")}
                  aria-invalid={c.invalid}
                  aria-describedby={c.describedBy}
                  placeholder="Choose an opponent"
                  options={ordered.map((o) => ({ value: o.name, label: <ModelLabel model={o.name} logoUrl={o.logo_url} />, hint: opponentHint(o) }))}
                />
              )}
            </Field>
            <Field label="Your deck" error={errors.deck?.message ?? serverFields.deck}>
              {(c) => <Select id={c.id} value={values.deck} onValueChange={choose("deck")} aria-invalid={c.invalid} aria-describedby={c.describedBy} placeholder="Choose a deck" options={deckOptions} />}
            </Field>
            <Field label="Opponent deck" error={errors.opponentDeck?.message ?? serverFields.opponent_deck}>
              {(c) => (
                <Select
                  id={c.id}
                  value={values.opponentDeck}
                  onValueChange={choose("opponentDeck")}
                  aria-invalid={c.invalid}
                  aria-describedby={c.describedBy}
                  options={[{ value: SAME_DECK, label: "Same as mine" }, ...deckOptions]}
                />
              )}
            </Field>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Seed (shuffle)" error={errors.seed?.message} hint="The same seed deals the same hands.">
              {(c) => (
                <Input
                  id={c.id}
                  type="number"
                  min={1}
                  max={10_000}
                  inputMode="numeric"
                  aria-invalid={c.invalid}
                  aria-describedby={c.describedBy}
                  {...register("seed", { valueAsNumber: true, onChange: edited })}
                />
              )}
            </Field>
            <Field label="Decision interval" error={errors.ticks?.message ?? serverFields.ticks} hint="Game time between your moves. The game waits while you decide.">
              {(c) => (
                <Select
                  id={c.id}
                  value={values.ticks}
                  onValueChange={choose("ticks")}
                  aria-invalid={c.invalid}
                  aria-describedby={c.describedBy}
                  options={options.tick_choices.map((t) => ({ value: String(t), label: tickLabel(t) }))}
                />
              )}
            </Field>
          </div>

          <div className="space-y-1">
            <DeckLine deck={mine} />
            {theirs ? <DeckLine deck={theirs} /> : null}
          </div>

          {opponent?.kind === "llm" ? (
            <p className="text-xs text-muted">
              {opponent.name} is called through its configured provider each time it moves, using this server&rsquo;s credentials, which may incur API charges.
            </p>
          ) : null}
          {readOnly ? <Banner tone="warning" title="This server is read-only">Games cannot be started here.</Banner> : null}
          {unexplained ? (
            <Banner tone="danger" title="Couldn't start the game">
              {start.error?.message}
            </Banner>
          ) : null}
          <Button type="submit" variant="primary" disabled={!isValid || readOnly} loading={start.isPending}>
            Start game
          </Button>
        </CardContent>
      </Card>
    </form>
  );
}
