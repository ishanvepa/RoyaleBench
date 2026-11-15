import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import type { BattleOptions, BattleRequest } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useReadOnly } from "@/hooks/useServerInfo";
import { plural } from "@/lib/format";
import { useBattlePreview, useStartBattle } from "../api/play";

/** Stands for "use the decks in the arena configuration" in the deck list. */
const CONFIGURED = "__configured__";

function makeSchema(maxParallel: number) {
  return z
    .object({
      first: z.string().min(1, "Choose the first model"),
      second: z.string().min(1, "Choose the second model"),
      mode: z.enum(["mirror", "build"]),
      deck: z.string(),
      parallel: z.number({ error: "Enter a whole number" }).int("Enter a whole number").min(1, "At least 1").max(maxParallel, `At most ${maxParallel}`),
    })
    .refine((v) => v.first !== v.second, { path: ["second"], message: "Choose two different models" });
}
type Values = z.infer<ReturnType<typeof makeSchema>>;

function requestOf(v: Values): BattleRequest {
  return { players: [v.first, v.second], mode: v.mode, deck: v.mode === "mirror" && v.deck !== CONFIGURED ? v.deck : null, parallel: Number.isFinite(v.parallel) ? v.parallel : 1 };
}

export function BattleForm({ options, onStarted }: { options: BattleOptions; onStarted: (name: string) => void }) {
  const start = useStartBattle();
  const readOnly = useReadOnly();
  const schema = useMemo(() => makeSchema(options.max_parallel), [options.max_parallel]);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { first: options.players[0]?.name ?? "", second: options.players[1]?.name ?? "", mode: "mirror", deck: CONFIGURED, parallel: 1 },
  });
  const { register, setValue, handleSubmit, watch, formState } = form;
  const { errors, isValid } = formState;
  const values = watch();

  const body = requestOf(values);
  // Compare by value: a new object on every render would restart the debounce forever.
  const key = JSON.stringify(body);
  const debounced = useDebouncedValue(key, 300);
  const pickedTwo = values.first !== "" && values.second !== "" && values.first !== values.second;
  const preview = useBattlePreview(JSON.parse(debounced) as BattleRequest, pickedTwo);
  const settled = key === debounced && !preview.isFetching && !preview.isPlaceholderData;
  const plan = preview.data;

  const submit = handleSubmit(() => {
    start.mutate(body, {
      onSuccess: (status) => {
        toast.success("Battle started");
        onStarted(status.name);
      },
    });
  });

  const choose = (field: "first" | "second" | "mode" | "deck") => (value: string) => {
    if (start.isError) start.reset();
    setValue(field, value as never, { shouldValidate: true, shouldDirty: true });
  };
  const player = (p: BattleOptions["players"][number]) => ({ value: p.name, label: <ModelLabel model={p.name} logoUrl={p.logo_url} />, hint: [p.provider, p.model].filter(Boolean).join(" · ") });
  const chosenDeck = options.decks.find((d) => d.key === values.deck);
  const ready = isValid && pickedTwo && settled && Boolean(plan?.valid) && !readOnly;

  return (
    <form onSubmit={(e) => void submit(e)} noValidate aria-label="Start a battle">
      <Card>
        <CardHeader>
          <CardTitle>New battle</CardTitle>
          <span className="text-xs text-muted">From {options.config_name}</span>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="First model" error={errors.first?.message}>
              {(c) => <Select id={c.id} value={values.first} onValueChange={choose("first")} aria-invalid={c.invalid} aria-describedby={c.describedBy} options={options.players.map(player)} placeholder="Choose a model" />}
            </Field>
            <Field label="Second model" error={errors.second?.message}>
              {(c) => <Select id={c.id} value={values.second} onValueChange={choose("second")} aria-invalid={c.invalid} aria-describedby={c.describedBy} options={options.players.map(player)} placeholder="Choose a model" />}
            </Field>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Deck mode">
              {(c) => (
                <Select
                  id={c.id}
                  value={values.mode}
                  onValueChange={choose("mode")}
                  options={[
                    { value: "mirror", label: "Configured decks", hint: "Both models play the same deck" },
                    { value: "build", label: "Models build their decks", hint: "Each model picks its own eight cards" },
                  ]}
                />
              )}
            </Field>
            {values.mode === "mirror" ? (
              <Field label="Battle deck">
                {(c) => (
                  <Select
                    id={c.id}
                    value={values.deck}
                    onValueChange={choose("deck")}
                    options={[{ value: CONFIGURED, label: "Use configured decks" }, ...options.decks.map((d) => ({ value: d.key, label: d.name, hint: `${d.preset ? "Preset" : "Saved"} · average elixir ${d.avg_elixir.toFixed(1)}` }))]}
                  />
                )}
              </Field>
            ) : null}
            <Field label="Games at once" error={errors.parallel?.message} hint="More at once can hit provider rate limits sooner.">
              {(c) => (
                <Input id={c.id} type="number" min={1} max={options.max_parallel} inputMode="numeric" aria-invalid={c.invalid} aria-describedby={c.describedBy} {...register("parallel", { valueAsNumber: true })} />
              )}
            </Field>
          </div>
          {values.mode === "mirror" && chosenDeck ? <p className="text-xs text-muted">{chosenDeck.cards.join(", ")}</p> : null}

          <div aria-live="polite" className="text-[13px]">
            {!pickedTwo ? null : plan?.valid ? (
              <Banner tone="info" title={`${plural(plan.games, "game")}, with the models swapping sides`}>
                {values.mode === "mirror" && values.deck !== CONFIGURED ? "Uses the selected deck and the seeds from the configuration." : "Uses the seeds and decks from the configuration."}
              </Banner>
            ) : plan ? (
              <Banner tone="danger" title="This battle can't be scheduled">
                {plan.error}
              </Banner>
            ) : preview.isError ? (
              <Banner tone="danger" title="Couldn't check this battle">
                {preview.error.message}
              </Banner>
            ) : null}
          </div>

          <p className="text-xs text-muted">Starting a battle makes model calls using this server&rsquo;s configured credentials and may incur API charges. Keep the server running while it plays.</p>
          {readOnly ? <Banner tone="warning" title="This server is read-only">Battles cannot be started here.</Banner> : null}
          {start.isError ? (
            <Banner tone="danger" title="Couldn't start the battle">
              {start.error.message}
            </Banner>
          ) : null}
          <Button type="submit" variant="primary" disabled={!ready} loading={start.isPending}>
            Start battle
          </Button>
        </CardContent>
      </Card>
    </form>
  );
}
