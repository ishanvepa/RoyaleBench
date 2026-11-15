import { screen, waitFor, within } from "@testing-library/react";
import type { UserEvent } from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { DeckOut } from "@/api/types";
import { deckList, GIANT_BEATDOWN, HOG_CYCLE, presetDeck, savedDeck } from "@/test/legacyFixtures";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

const WAIT = { timeout: 3_000 };

let saved: DeckOut[];
let writes: { method: string; url: string; body?: unknown }[];

function useDeckHandlers() {
  server.use(
    http.get("*/api/legacy/decks", () => HttpResponse.json(deckList([presetDeck("giant-beatdown", GIANT_BEATDOWN), presetDeck("hog-cycle", HOG_CYCLE), ...saved]))),
    http.post("*/api/legacy/decks", async ({ request }) => {
      const body = (await request.json()) as { name: string; cards: string[] };
      writes.push({ method: "POST", url: request.url, body });
      const deck = savedDeck("new1", body.name, body.cards);
      saved.push(deck);
      return HttpResponse.json(deck, { status: 201 });
    }),
    http.put("*/api/legacy/decks/:id", async ({ request, params }) => {
      const body = (await request.json()) as { name: string; cards: string[] };
      writes.push({ method: "PUT", url: request.url, body });
      const deck = savedDeck(String(params.id), body.name, body.cards);
      saved = saved.map((d) => (d.id === params.id ? deck : d));
      return HttpResponse.json(deck);
    }),
    http.delete("*/api/legacy/decks/:id", ({ request, params }) => {
      writes.push({ method: "DELETE", url: request.url });
      saved = saved.filter((d) => d.id !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
  );
}

beforeEach(() => {
  saved = [];
  writes = [];
});

const card = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name},`) });
const pressed = () => screen.queryAllByRole("button", { pressed: true });
const saveButton = () => screen.getByRole("button", { name: /^Save (deck|changes)$/ });

async function pickCards(user: UserEvent, names: string[]) {
  for (const name of names) await user.click(card(name));
}

async function choosePreset(user: UserEvent, name: RegExp) {
  await user.click(await screen.findByLabelText("Start from a preset"));
  await user.click(await screen.findByRole("option", { name }));
}

describe("Decks page", () => {
  it("lists saved and preset decks with their average elixir", async () => {
    saved = [savedDeck("d1", "My cycle", HOG_CYCLE)];
    useDeckHandlers();
    renderApp("/legacy/decks");
    const savedSection = await screen.findByRole("region", { name: "Saved decks" });
    expect(within(savedSection).getByText("My cycle")).toBeInTheDocument();
    expect(within(savedSection).getByText("Average elixir 2.8")).toBeInTheDocument(); // 22 elixir over 8 cards, shown to one decimal
    const presets = screen.getByRole("region", { name: "Preset decks" });
    expect(within(presets).getByText("giant-beatdown")).toBeInTheDocument();
    expect(within(presets).getByText(/Giant, Musketeer, Knight/)).toBeInTheDocument();
  });

  it("says so when there are no saved decks", async () => {
    useDeckHandlers();
    renderApp("/legacy/decks");
    expect(await screen.findByText("No custom decks yet")).toBeInTheDocument();
    expect(screen.getByText("Choose cards to preview your deck and average elixir cost.")).toBeInTheDocument();
  });

  it("cannot be saved until it has a name and exactly eight cards", async () => {
    useDeckHandlers();
    const { user } = renderApp("/legacy/decks");
    await screen.findByLabelText("Deck name");
    expect(saveButton()).toBeDisabled();

    await pickCards(user, GIANT_BEATDOWN.slice(0, 7));
    expect(screen.getByText("7 of 8 cards chosen")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Deck name"), "My giant");
    expect(saveButton()).toBeDisabled(); // one card short

    await user.click(card(GIANT_BEATDOWN[7] ?? ""));
    await waitFor(() => expect(saveButton()).toBeEnabled());

    await user.clear(screen.getByLabelText("Deck name"));
    await waitFor(() => expect(saveButton()).toBeDisabled());
    expect(await screen.findByText("Give the deck a name")).toBeInTheDocument();
  });

  it("stops accepting cards after the eighth, and takes one off to make room", async () => {
    useDeckHandlers();
    const { user } = renderApp("/legacy/decks");
    await screen.findByLabelText("Deck name");
    await pickCards(user, GIANT_BEATDOWN);
    expect(pressed()).toHaveLength(8);
    expect(card("HogRider")).toBeDisabled();
    expect(card("Giant")).toBeEnabled(); // a chosen card can always be removed

    await user.click(card("Giant"));
    expect(pressed()).toHaveLength(7);
    expect(card("HogRider")).toBeEnabled();
  });

  it("previews the chosen cards and their average elixir, and removes one from the preview", async () => {
    useDeckHandlers();
    const { user } = renderApp("/legacy/decks");
    await screen.findByLabelText("Deck name");
    await pickCards(user, ["Giant", "Zap"]);
    const preview = screen.getByRole("list", { name: "Selected cards" });
    expect(within(preview).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("3.5")).toBeInTheDocument(); // (5 + 2) / 2
    await user.click(within(preview).getByRole("button", { name: "Remove Giant" }));
    expect(within(screen.getByRole("list", { name: "Selected cards" })).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByText("2.0")).toBeInTheDocument();
  });

  it("starts from a preset, saves a new deck and opens it for editing", async () => {
    useDeckHandlers();
    const { router, user } = renderApp("/legacy/decks");
    await choosePreset(user, /giant-beatdown/);
    expect(pressed()).toHaveLength(8);
    expect(screen.getByLabelText("Start from a preset")).toHaveTextContent("giant-beatdown"); // it shows which preset the cards match

    await user.type(screen.getByLabelText("Deck name"), "  My giant  ");
    await waitFor(() => expect(saveButton()).toBeEnabled());
    await user.click(saveButton());

    await waitFor(() => expect(router.state.location.search).toBe("?deck=new1"));
    expect(writes).toHaveLength(1);
    expect(writes[0]).toMatchObject({ method: "POST", body: { name: "My giant", cards: GIANT_BEATDOWN } }); // the name is trimmed
    expect(await screen.findByText("Edit deck")).toBeInTheDocument();
    expect(screen.getByLabelText("Deck name")).toHaveValue("My giant");
    expect(screen.getByRole("region", { name: "Saved decks" })).toHaveTextContent("My giant");
    expect(screen.getByRole("button", { name: "Delete deck" })).toBeInTheDocument();
  });

  it("forgets the preset it was started from once the cards no longer match it", async () => {
    useDeckHandlers();
    const { user } = renderApp("/legacy/decks");
    await choosePreset(user, /giant-beatdown/);
    await user.click(card("Giant"));
    expect(screen.getByLabelText("Start from a preset")).toHaveTextContent("Choose a preset");
  });

  it("shows the server's reason next to the field it rejected, and clears it when the user edits", async () => {
    useDeckHandlers();
    server.use(
      http.post("*/api/legacy/decks", () =>
        apiError(422, "validation_error", "That deck name is already taken.", [{ field: "name", message: "That deck name is already taken." }]),
      ),
    );
    const { user } = renderApp("/legacy/decks");
    await choosePreset(user, /hog-cycle/);
    await user.type(screen.getByLabelText("Deck name"), "Taken");
    await waitFor(() => expect(saveButton()).toBeEnabled());
    await user.click(saveButton());
    const error = await screen.findByText("That deck name is already taken.");
    expect(screen.getByLabelText("Deck name")).toHaveAccessibleDescription("That deck name is already taken.");
    expect(error).toHaveAttribute("role", "alert");

    await user.type(screen.getByLabelText("Deck name"), "2");
    await waitFor(() => expect(screen.queryByText("That deck name is already taken.")).not.toBeInTheDocument());
  });

  it("says why when the save fails for a reason that belongs to no field", async () => {
    useDeckHandlers();
    server.use(http.post("*/api/legacy/decks", () => apiError(503, "database_unavailable", "Cannot open the arena database")));
    const { user } = renderApp("/legacy/decks");
    await choosePreset(user, /hog-cycle/);
    await user.type(screen.getByLabelText("Deck name"), "Cycle");
    await waitFor(() => expect(saveButton()).toBeEnabled());
    await user.click(saveButton());
    expect(await screen.findByText("Couldn't save the deck", {}, WAIT)).toBeInTheDocument();
    expect(screen.getByText("Cannot open the arena database")).toBeInTheDocument();
  });

  it("edits a saved deck: loads its cards, then updates it in place", async () => {
    saved = [savedDeck("d1", "My cycle", HOG_CYCLE)];
    useDeckHandlers();
    const { router, user } = renderApp("/legacy/decks?deck=d1");
    expect(await screen.findByText("Edit deck")).toBeInTheDocument();
    expect(screen.getByLabelText("Deck name")).toHaveValue("My cycle");
    expect(pressed().map((b) => b.getAttribute("aria-label")?.split(",")[0]).sort()).toEqual([...HOG_CYCLE].sort());
    expect(screen.getByRole("combobox", { name: "Edit a deck" })).toHaveTextContent("My cycle");

    await user.click(card("Knight")); // swap Knight for Giant
    await user.click(card("Giant"));
    await user.clear(screen.getByLabelText("Deck name"));
    await user.type(screen.getByLabelText("Deck name"), "Renamed");
    await waitFor(() => expect(saveButton()).toBeEnabled());
    await user.click(saveButton());

    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({ method: "PUT", body: { name: "Renamed" } });
    expect((writes[0]?.body as { cards: string[] }).cards).toContain("Giant");
    expect((writes[0]?.body as { cards: string[] }).cards).not.toContain("Knight");
    expect(writes[0]?.url).toMatch(/\/decks\/d1$/);
    expect(router.state.location.search).toBe("?deck=d1");
    expect(await screen.findByRole("region", { name: "Saved decks" })).toHaveTextContent("Renamed");
  });

  it("switches between decks from the selector, starting each editor from that deck's saved cards", async () => {
    saved = [savedDeck("d1", "My cycle", HOG_CYCLE)];
    useDeckHandlers();
    const { router, user } = renderApp("/legacy/decks");
    await user.click(await screen.findByRole("combobox", { name: "Edit a deck" }));
    await user.click(await screen.findByRole("option", { name: /My cycle/ }));
    await waitFor(() => expect(router.state.location.search).toBe("?deck=d1"));
    expect(await screen.findByLabelText("Deck name")).toHaveValue("My cycle");

    await user.click(screen.getByRole("combobox", { name: "Edit a deck" }));
    await user.click(await screen.findByRole("option", { name: "Create a new deck" }));
    await waitFor(() => expect(router.state.location.search).toBe(""));
    expect(screen.getByLabelText("Deck name")).toHaveValue("");
    expect(pressed()).toHaveLength(0);
  });

  it("deletes a saved deck only after the user confirms", async () => {
    saved = [savedDeck("d1", "My cycle", HOG_CYCLE)];
    useDeckHandlers();
    const { router, user } = renderApp("/legacy/decks?deck=d1");
    await user.click(await screen.findByRole("button", { name: "Delete deck" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Matches already played keep their original cards/)).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(writes).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: "Delete deck" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Delete deck" }));
    await waitFor(() => expect(writes).toEqual([{ method: "DELETE", url: expect.stringMatching(/\/decks\/d1$/) }]));
    await waitFor(() => expect(router.state.location.search).toBe(""));
    expect(await screen.findByText("No custom decks yet")).toBeInTheDocument();
  });

  it("explains a link to a deck that no longer exists, and offers a new deck instead", async () => {
    useDeckHandlers();
    renderApp("/legacy/decks?deck=gone");
    expect(await screen.findByText("That deck no longer exists")).toBeInTheDocument();
    expect(screen.getByLabelText("Deck name")).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Delete deck" })).not.toBeInTheDocument();
  });

  it("cannot save or delete on a read-only server", async () => {
    saved = [savedDeck("d1", "My cycle", HOG_CYCLE)];
    useDeckHandlers();
    server.use(http.get("*/api/health", () => HttpResponse.json({ status: "ok", read_only: true, fake: false })));
    renderApp("/legacy/decks?deck=d1");
    expect(await screen.findByText("This server is read-only")).toBeInTheDocument();
    await waitFor(() => expect(saveButton()).toBeDisabled());
    expect(screen.getByRole("button", { name: "Delete deck" })).toBeDisabled();
  });

  it("filters the card pool by search and by type", async () => {
    useDeckHandlers();
    const { user } = renderApp("/legacy/decks");
    await screen.findByLabelText("Deck name");
    await user.type(screen.getByRole("searchbox", { name: "Search cards" }), "ice");
    const pool = () => within(screen.getByRole("list", { name: "Card pool" })).getAllByRole("listitem");
    expect(pool()).toHaveLength(1);
    expect(card("IceSpirits")).toBeInTheDocument();

    await user.clear(screen.getByRole("searchbox", { name: "Search cards" }));
    await user.click(screen.getByText("Spells"));
    expect(pool().map((li) => li.textContent?.replace(/\d+$/, ""))).toEqual(["FireballSpell", "LogSpell", "ZapSpell"]);

    await user.type(screen.getByRole("searchbox", { name: "Search cards" }), "zzz");
    expect(await screen.findByText("No cards match your search.")).toBeInTheDocument();
  });
});
