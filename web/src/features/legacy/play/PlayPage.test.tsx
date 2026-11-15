import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { PlayState } from "@/api/types";
import { claudeOpponent, entity, playOptions, playState, searchBot } from "@/test/legacyFixtures";
import { renderApp } from "@/test/render";
import { apiError, server } from "@/test/server";

const WAIT = { timeout: 3_000 };

let started: unknown[];
let moved: unknown[];
let abandoned: string[];

/** The server's game: GET returns ``current``, a move replaces it with ``afterMove``. */
function usePlayHandlers(options: { current?: PlayState; afterMove?: () => Response | Promise<Response>; opponents?: ReturnType<typeof playOptions>["opponents"] } = {}) {
  const current = options.current ?? playState();
  server.use(
    http.get("*/api/legacy/play/options", () => HttpResponse.json(playOptions(options.opponents ? { opponents: options.opponents } : {}))),
    http.post("*/api/legacy/play/games", async ({ request }) => {
      started.push(await request.json());
      return HttpResponse.json(current, { status: 201 });
    }),
    http.get("*/api/legacy/play/games/:id", () => HttpResponse.json(current)),
    http.post("*/api/legacy/play/games/:id/move", async ({ request }) => {
      moved.push(await request.json());
      return options.afterMove ? options.afterMove() : HttpResponse.json(playState({ step: 4, time_left_s: 172 }));
    }),
    http.delete("*/api/legacy/play/games/:id", ({ params }) => {
      abandoned.push(String(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
}

beforeEach(() => {
  started = [];
  moved = [];
  abandoned = [];
});

const startButton = () => screen.getByRole("button", { name: "Start game" });
const board = () => screen.getByRole("img", { name: /^Arena\./ });
const metric = (label: string) => screen.getByText(label).nextElementSibling;
const circles = () => board().querySelectorAll("circle").length;

async function startGame(path = "/legacy/play") {
  const view = renderApp(path);
  await screen.findByLabelText("Opponent");
  await waitFor(() => expect(startButton()).toBeEnabled());
  await view.user.click(startButton());
  await screen.findByRole("img", { name: /^Arena\./ }, WAIT);
  return view;
}

describe("Play: setting up a game", () => {
  it("starts from sensible defaults, with the bot first even though the server lists a model first", async () => {
    usePlayHandlers();
    renderApp("/legacy/play");
    expect(await screen.findByLabelText("Opponent")).toHaveTextContent("search-bot");
    expect(screen.getByLabelText("Your deck")).toHaveTextContent("giant-beatdown");
    expect(screen.getByLabelText("Opponent deck")).toHaveTextContent("Same as mine");
    expect(screen.getByLabelText("Seed (shuffle)")).toHaveValue(1);
    expect(screen.getByLabelText("Decision interval")).toHaveTextContent("2 s");
    expect(screen.getByText(/Giant, Musketeer, Knight, Archer/)).toBeInTheDocument(); // the chosen deck's cards are listed
    expect(screen.getByText("Want real time?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "http://localhost:8600" })).toHaveAttribute("href", "http://localhost:8600");
  });

  it("starts a game and shows the board, with the game's id in the address", async () => {
    usePlayHandlers();
    const { router } = await startGame();
    expect(started).toEqual([{ opponent: "search-bot", deck: "giant-beatdown", opponent_deck: null, seed: 1, ticks: 40 }]);
    expect(router.state.location.search).toBe("?game=game1");
    expect(board()).toHaveAccessibleName("Arena. You have 0 units and 3 towers standing. search-bot has 1 units and 3 towers standing.");
    expect(metric("Time left")).toHaveTextContent("2:54");
    expect(metric("Crowns (you–opponent)")).toHaveTextContent("0–0");
    expect(metric("Your elixir")).toHaveTextContent("6.5");
    expect(screen.getByRole("progressbar", { name: "Your elixir" })).toHaveAttribute("aria-valuenow", "6.5");
    const hand = within(screen.getByRole("region", { name: "Your hand" }));
    expect(hand.getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Knighttroop3", "Fireballspell4", "Gianttroop5", "Cannonbuilding3"]);
    expect(hand.getByText("Next card: Archer")).toBeInTheDocument();
    expect(screen.getByText("Since your last move: your Knight was deployed")).toBeInTheDocument();
  });

  it("sends the opponent's deck, the seed and the interval that were chosen", async () => {
    usePlayHandlers();
    const { user } = renderApp("/legacy/play");
    await user.click(await screen.findByLabelText("Opponent deck"));
    await user.click(await screen.findByRole("option", { name: /hog-cycle/ }));
    await user.click(screen.getByLabelText("Decision interval"));
    await user.click(await screen.findByRole("option", { name: "3 s" }));
    await user.clear(screen.getByLabelText("Seed (shuffle)"));
    await user.type(screen.getByLabelText("Seed (shuffle)"), "7");
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    await waitFor(() => expect(started).toHaveLength(1));
    expect(started[0]).toEqual({ opponent: "search-bot", deck: "giant-beatdown", opponent_deck: "hog-cycle", seed: 7, ticks: 60 });
  });

  it("will not start with a seed outside 1 to 10,000", async () => {
    usePlayHandlers();
    const { user } = renderApp("/legacy/play");
    const seed = await screen.findByLabelText("Seed (shuffle)");
    await user.clear(seed);
    await user.type(seed, "0");
    expect(await screen.findByText("At least 1")).toBeInTheDocument();
    expect(startButton()).toBeDisabled();
    await user.clear(seed);
    await user.type(seed, "10001");
    expect(await screen.findByText("At most 10,000")).toBeInTheDocument();
    await user.clear(seed);
    await user.type(seed, "10000");
    await waitFor(() => expect(startButton()).toBeEnabled());
  });

  it("warns that a model opponent is called with the server's credentials", async () => {
    usePlayHandlers();
    const { user } = renderApp("/legacy/play");
    expect(screen.queryByText(/may incur API charges/)).not.toBeInTheDocument();
    await user.click(await screen.findByLabelText("Opponent"));
    await user.click(await screen.findByRole("option", { name: new RegExp(claudeOpponent.name) }));
    expect(await screen.findByText(/claude-opus-5\.5 is called through its configured provider.*may incur API charges/)).toBeInTheDocument();
    await user.click(screen.getByLabelText("Opponent"));
    await user.click(await screen.findByRole("option", { name: new RegExp(searchBot.name) }));
    await waitFor(() => expect(screen.queryByText(/may incur API charges/)).not.toBeInTheDocument());
  });

  it("shows the server's reason next to the field it rejected", async () => {
    usePlayHandlers();
    server.use(http.post("*/api/legacy/play/games", () => apiError(422, "validation_error", "No API key for this model.", [{ field: "opponent", message: "No API key for this model." }])));
    const { user } = renderApp("/legacy/play");
    await screen.findByLabelText("Opponent");
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    expect(await screen.findByText("No API key for this model.")).toBeInTheDocument();
    expect(screen.getByLabelText("Opponent")).toHaveAccessibleDescription("No API key for this model.");
    expect(screen.queryByRole("img", { name: /^Arena\./ })).not.toBeInTheDocument(); // still on the form
  });

  it("explains a failure that belongs to no field, and stays on the form", async () => {
    usePlayHandlers();
    server.use(http.post("*/api/legacy/play/games", () => apiError(502, "bad_gateway", "Opponent model unreachable: timed out")));
    const { user } = renderApp("/legacy/play");
    await screen.findByLabelText("Opponent");
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    expect(await screen.findByText("Couldn't start the game")).toBeInTheDocument();
    expect(screen.getByText("Opponent model unreachable: timed out")).toBeInTheDocument();
  });

  it("cannot start a game on a read-only server", async () => {
    usePlayHandlers();
    server.use(http.get("*/api/health", () => HttpResponse.json({ status: "ok", read_only: true, fake: false })));
    renderApp("/legacy/play");
    expect(await screen.findByText("This server is read-only")).toBeInTheDocument();
    expect(startButton()).toBeDisabled();
  });
});

describe("Play: playing", () => {
  it("sends the chosen move, shows that the opponent is thinking, then the new board", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    usePlayHandlers({
      afterMove: async () => {
        await gate;
        return HttpResponse.json(playState({ step: 4, time_left_s: 172, elixir: 3.5, crowns: [0, 1], entities: [...playState().entities, entity(11, 0, "troop", 3.5, 14)] }));
      },
    });
    const { user } = await startGame();
    await user.click(screen.getByRole("button", { name: "Knight: left bridge" }));

    expect(await screen.findByText(/Waiting for the opponent/)).toBeInTheDocument();
    expect(moved).toEqual([{ index: 1 }]);
    expect(screen.getByRole("button", { name: "Knight: right bridge" })).toBeDisabled(); // nothing else can be chosen meanwhile
    expect(screen.getByRole("button", { name: /Wait \(save elixir\)/ })).toBeDisabled();
    expect(metric("Time left")).toHaveTextContent("2:54"); // the old board stays until the reply arrives

    release();
    await waitFor(() => expect(metric("Time left")).toHaveTextContent("2:52"), WAIT);
    expect(metric("Crowns (you–opponent)")).toHaveTextContent("0–1");
    expect(metric("Your elixir")).toHaveTextContent("3.5");
    expect(screen.queryByText(/Waiting for the opponent/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Knight: right bridge" })).toBeEnabled();
    expect(board()).toHaveAccessibleName(expect.stringContaining("You have 1 units"));
  });

  it("waits when asked to: move 0", async () => {
    usePlayHandlers();
    const { user } = await startGame();
    await user.click(screen.getByRole("button", { name: /Wait \(save elixir\)/ }));
    await waitFor(() => expect(moved).toEqual([{ index: 0 }]));
  });

  it("keeps the game and lets the player choose again when the opponent model cannot be reached", async () => {
    usePlayHandlers({ afterMove: () => apiError(502, "bad_gateway", "Opponent model unreachable: connection reset") as unknown as Response });
    const { user } = await startGame();
    await user.click(screen.getByRole("button", { name: "Knight: left bridge" }));
    expect(await screen.findByText("That move was not played")).toBeInTheDocument();
    expect(screen.getByText(/Opponent model unreachable: connection reset/)).toBeInTheDocument();
    expect(screen.getByText(/The game has not advanced/)).toBeInTheDocument();
    expect(metric("Time left")).toHaveTextContent("2:54");
    expect(screen.getByRole("button", { name: "Knight: left bridge" })).toBeEnabled();
  });

  it("marks on the board every place the hovered card could go, and clears them afterwards", async () => {
    usePlayHandlers();
    const { user } = await startGame();
    const before = circles();
    await user.hover(screen.getByRole("button", { name: "Knight: left bridge" }));
    await waitFor(() => expect(circles()).toBe(before + 2)); // both bridges
    await user.unhover(screen.getByRole("button", { name: "Knight: left bridge" }));
    await waitFor(() => expect(circles()).toBe(before));
  });

  it("shows the game log and, when there is one, the opponent's reasoning", async () => {
    usePlayHandlers({ current: playState({ log: ["[2:56] you played Knight @ left bridge", "[2:54] opponent played Giant"], opponent_thinking: { time: "2:54", text: "Defend the left lane." } }) });
    await startGame();
    expect(screen.getByText(/\[2:54\] opponent played Giant/)).toBeInTheDocument();
    expect(screen.getByText("search-bot’s reasoning (last move)")).toBeInTheDocument();
    expect(screen.getByText("Defend the left lane.")).toBeInTheDocument();
    expect(screen.getByText("At 2:54")).toBeInTheDocument();
  });

  it("does not offer a reasoning section before the opponent has said anything", async () => {
    usePlayHandlers();
    await startGame();
    expect(screen.queryByText(/reasoning/)).not.toBeInTheDocument();
  });
});

describe("Play: leaving and returning", () => {
  it("picks a game up again from the address after a reload, without starting a new one", async () => {
    usePlayHandlers();
    renderApp("/legacy/play?game=game1");
    expect(await screen.findByRole("img", { name: /^Arena\./ }, WAIT)).toBeInTheDocument();
    expect(started).toHaveLength(0);
    expect(screen.queryByLabelText("Opponent")).not.toBeInTheDocument();
  });

  it("explains a game the server no longer has, and goes back to the setup form", async () => {
    usePlayHandlers();
    server.use(http.get("*/api/legacy/play/games/:id", () => apiError(404, "not_found", "Unknown game")));
    const { router, user } = renderApp("/legacy/play?game=lost");
    expect(await screen.findByText("This game is no longer available")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start a new game" }));
    expect(await screen.findByLabelText("Opponent")).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
  });

  it("asks before abandoning a game in progress, and forgets it on the server once confirmed", async () => {
    usePlayHandlers();
    const { router, user } = await startGame();
    await user.click(screen.getByRole("button", { name: "New game" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Abandon this game?")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(abandoned).toEqual([]);
    expect(board()).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "New game" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Abandon game" }));
    expect(await screen.findByLabelText("Opponent")).toBeInTheDocument();
    await waitFor(() => expect(abandoned).toEqual(["game1"]));
    expect(router.state.location.search).toBe("");
  });
});

describe("Play: when the game ends", () => {
  const over = (overrides: Partial<PlayState>) => playState({ over: true, moves: [], hand: [], events: [], time_left_s: 0, saved_as: "human__vs__search-bot__abc123", ...overrides });

  it("says you won, links to the saved match, and removes the move list", async () => {
    usePlayHandlers({ current: over({ winner: 0, crowns: [2, 1] }) });
    await startGame();
    expect(await screen.findByText("You win!")).toBeInTheDocument();
    expect(screen.getByText("2–1", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open the replay and the opponent.s reasoning/ })).toHaveAttribute("href", "/legacy/matches/human-play/human__vs__search-bot__abc123");
    expect(screen.queryByRole("region", { name: "Your move" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Your hand" })).not.toBeInTheDocument();
  });

  it("names the opponent when it wins, and calls a tie a draw", async () => {
    usePlayHandlers({ current: over({ winner: 1, crowns: [0, 3] }) });
    const first = await startGame();
    expect(await screen.findByText("search-bot wins.")).toBeInTheDocument();
    first.unmount();

    usePlayHandlers({ current: over({ winner: 2, crowns: [1, 1] }) });
    await startGame();
    expect(await screen.findByText("Draw.")).toBeInTheDocument();
  });

  it("tells you when the finished game could not be saved", async () => {
    usePlayHandlers({ current: over({ winner: 0, saved_as: null, save_error: "OperationalError: database is locked" }) });
    await startGame();
    expect(await screen.findByText("The game finished but could not be saved")).toBeInTheDocument();
    expect(screen.getByText("OperationalError: database is locked")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Open the replay/ })).not.toBeInTheDocument();
  });

  it("plays again without confirmation, returning to the setup form", async () => {
    usePlayHandlers({ current: over({ winner: 0 }) });
    const { router, user } = await startGame();
    await user.click(await screen.findByRole("button", { name: "Play again" }));
    expect(await screen.findByLabelText("Opponent")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(abandoned).toEqual(["game1"]));
    expect(router.state.location.search).toBe("");
  });
});

describe("Play: modes", () => {
  it("opens the model battle tab from the address and switches with the tabs", async () => {
    usePlayHandlers();
    server.use(http.get("*/api/legacy/battles/options", () => HttpResponse.json({ players: [claudeOpponent], decks: [], max_parallel: 4, config_name: "config.toml" })));
    server.use(http.get("*/api/legacy/battles", () => HttpResponse.json({ battles: [] })));
    const { router, user } = renderApp("/legacy/play?mode=battle");
    expect(await screen.findByText("Not enough models")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Model battle" })).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("tab", { name: "Play a game" }));
    expect(await screen.findByLabelText("Opponent")).toBeInTheDocument();
    expect(router.state.location.search).toBe("");
  });
});
