import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { fieldErrors } from "@/api/client";
import type { CardInfo, DeckOut } from "@/api/types";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useDeleteDeck, useSaveDeck } from "../api/decks";
import { CardPicker } from "./CardPicker";
import { DeckPreview } from "./DeckPreview";
import { DECK_SIZE, sameCards, toggleCard } from "./deckStats";

const schema = z.object({
  name: z.string().trim().min(1, "Give the deck a name").max(80, "At most 80 characters"),
  cards: z.array(z.string()).length(DECK_SIZE, `Choose exactly ${DECK_SIZE} cards`),
});
type Values = z.infer<typeof schema>;

interface DeckBuilderProps {
  /** The saved deck being edited, or null to build a new one. Remount (change the key) to switch decks. */
  deck: DeckOut | null;
  presets: readonly DeckOut[];
  pool: readonly CardInfo[];
  readOnly: boolean;
  onSaved: (deck: DeckOut) => void;
  onDeleted: () => void;
}

export function DeckBuilder({ deck, presets, pool, readOnly, onSaved, onDeleted }: DeckBuilderProps) {
  const save = useSaveDeck();
  const remove = useDeleteDeck();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { name: deck?.name ?? "", cards: deck ? [...deck.cards] : [] },
  });
  const { control, register, setValue, handleSubmit, reset, watch, formState } = form;
  // Read validity unconditionally; react-hook-form only tracks it once it has been read during a render.
  const { errors, isValid } = formState;
  const values = watch();

  // Whatever the server rejected is shown under its field until the person changes something.
  const serverFields = fieldErrors(save.error);
  const edited = () => {
    if (save.isError) save.reset();
  };

  const presetKey = presets.find((p) => sameCards(p.cards, values.cards))?.key ?? "";

  const submit = handleSubmit((v) => {
    save.mutate(
      { id: deck?.id ?? null, name: v.name.trim(), cards: v.cards },
      {
        onSuccess: (saved) => {
          toast.success(deck ? "Deck updated" : "Deck saved. Choose it in Play.");
          reset({ name: saved.name, cards: [...saved.cards] });
          onSaved(saved);
        },
      },
    );
  });

  const unexplained = save.isError && Object.keys(serverFields).length === 0;

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
      <form onSubmit={(e) => void submit(e)} noValidate aria-label="Deck builder">
        <Card>
          <CardHeader>
            <CardTitle>{deck ? "Edit deck" : "Deck builder"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Deck name" error={errors.name?.message ?? serverFields.name}>
                {(c) => (
                  <Input
                    id={c.id}
                    maxLength={80}
                    placeholder="e.g. My hog cycle"
                    aria-invalid={c.invalid}
                    aria-describedby={c.describedBy}
                    {...register("name", { onChange: edited })}
                  />
                )}
              </Field>
              <Field label="Start from a preset" hint="Fills in the cards. The name stays yours.">
                {(c) => (
                  <Select
                    id={c.id}
                    value={presetKey}
                    placeholder="Choose a preset"
                    onValueChange={(key) => {
                      const preset = presets.find((p) => p.key === key);
                      if (!preset) return;
                      edited();
                      setValue("cards", [...preset.cards], { shouldValidate: true, shouldDirty: true });
                    }}
                    options={presets.map((p) => ({ value: p.key, label: p.name, hint: `average elixir ${p.avg_elixir.toFixed(1)}` }))}
                  />
                )}
              </Field>
            </div>

            <div className="space-y-2">
              <span className="text-[13px] font-medium text-subtle">Cards</span>
              <Controller
                control={control}
                name="cards"
                render={({ field }) => (
                  <CardPicker
                    cards={pool}
                    selected={field.value}
                    onChange={(next) => {
                      edited();
                      field.onChange(next);
                    }}
                  />
                )}
              />
              {serverFields.cards ? (
                <p role="alert" className="text-xs text-danger">
                  {serverFields.cards}
                </p>
              ) : null}
            </div>

            {readOnly ? <Banner tone="warning" title="This server is read-only">Decks can be browsed here but not saved or deleted.</Banner> : null}
            {unexplained ? (
              <Banner tone="danger" title="Couldn't save the deck">
                {save.error?.message}
              </Banner>
            ) : null}

            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit" variant="primary" disabled={!isValid || readOnly} loading={save.isPending}>
                {deck ? "Save changes" : "Save deck"}
              </Button>
              {deck ? (
                <Button variant="danger-outline" disabled={readOnly} onClick={() => setConfirmDelete(true)}>
                  Delete deck
                </Button>
              ) : null}
              <span className="text-xs text-muted">{values.cards.length} of {DECK_SIZE} cards chosen</span>
            </div>
          </CardContent>
        </Card>
      </form>

      <div className="lg:sticky lg:top-6">
        <DeckPreview pool={pool} selected={values.cards} onRemove={(name) => setValue("cards", toggleCard(values.cards, name), { shouldValidate: true, shouldDirty: true })} />
      </div>

      {deck ? (
        <ConfirmDialog
          open={confirmDelete}
          onOpenChange={setConfirmDelete}
          title={`Delete “${deck.name}”?`}
          description="Matches already played keep their original cards. Only the saved deck goes away."
          confirmLabel="Delete deck"
          destructive
          loading={remove.isPending}
          onConfirm={() =>
            remove.mutate(deck.id ?? "", {
              onSuccess: () => {
                setConfirmDelete(false);
                toast.success("Deck deleted");
                onDeleted();
              },
              onError: (error) => {
                setConfirmDelete(false);
                toast.error(error.message);
              },
            })
          }
        />
      ) : null}
    </div>
  );
}
