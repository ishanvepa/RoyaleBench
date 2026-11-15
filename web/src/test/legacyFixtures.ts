/** Typed fixtures for the Legacy (arena) API. They use the generated types, so a changed API breaks them at compile time. */
import type {
  ArenaGame,
  ArenaPlayer,
  ArenaResults,
  ArenaRun,
  BattleOptions,
  BattleStatus,
  BoardEntity,
  CardInfo,
  DeckList,
  DeckOut,
  DecisionRow,
  JobReport,
  MatchReport,
  MatchRow,
  ModelRow,
  Overview,
  OverviewJob,
  PlayOpponent,
  PlayOptions,
  PlayState,
} from "@/api/types";

// ------------------------------------------------------------------------------------------------ decks
export const POOL: CardInfo[] = [
  { name: "Archer", elixir: 3, kind: "Troop" },
  { name: "Cannon", elixir: 3, kind: "Building" },
  { name: "Fireball", elixir: 4, kind: "Spell" },
  { name: "Giant", elixir: 5, kind: "Troop" },
  { name: "HogRider", elixir: 4, kind: "Troop" },
  { name: "IceSpirits", elixir: 1, kind: "Troop" },
  { name: "Knight", elixir: 3, kind: "Troop" },
  { name: "Log", elixir: 2, kind: "Spell" },
  { name: "Minions", elixir: 3, kind: "Troop" },
  { name: "Musketeer", elixir: 4, kind: "Troop" },
  { name: "Skeletons", elixir: 1, kind: "Troop" },
  { name: "Zap", elixir: 2, kind: "Spell" },
];

export const GIANT_BEATDOWN = ["Giant", "Musketeer", "Knight", "Archer", "Minions", "Cannon", "Fireball", "Zap"];
export const HOG_CYCLE = ["HogRider", "Musketeer", "Cannon", "IceSpirits", "Skeletons", "Knight", "Fireball", "Log"];

const average = (cards: string[]) => Math.round((cards.reduce((sum, name) => sum + (POOL.find((c) => c.name === name)?.elixir ?? 0), 0) / cards.length) * 100) / 100;

export const presetDeck = (name: string, cards: string[]): DeckOut => ({ key: name, name, cards, preset: true, avg_elixir: average(cards), id: null });
export const savedDeck = (id: string, name: string, cards: string[]): DeckOut => ({ key: `custom:${id}`, name, cards, preset: false, avg_elixir: average(cards), id });

export const deckList = (decks: DeckOut[] = [presetDeck("giant-beatdown", GIANT_BEATDOWN), presetDeck("hog-cycle", HOG_CYCLE)]): DeckList => ({ decks, cards: POOL });

// ------------------------------------------------------------------------------------------------ play
export const searchBot: PlayOpponent = { name: "search-bot", family: "bot", logo_url: null, kind: "bot", provider: "", model: "" };
export const claudeOpponent: PlayOpponent = { name: "claude-opus-5.5", family: "claude", logo_url: null, kind: "llm", provider: "anthropic", model: "claude-opus-5-5" };
export const gptOpponent: PlayOpponent = { name: "gpt-5", family: "gpt", logo_url: null, kind: "llm", provider: "openai", model: "gpt-5" };

export const playOptions = (overrides: Partial<PlayOptions> = {}): PlayOptions => ({
  // The server lists models before the bot; the page puts bots first.
  opponents: [claudeOpponent, searchBot],
  decks: deckList().decks,
  tick_choices: [20, 40, 60],
  ...overrides,
});

export const entity = (id: number, team: number, kind: BoardEntity["kind"], x: number, y: number, overrides: Partial<BoardEntity> = {}): BoardEntity => {
  const tower = kind === "king" || kind === "princess";
  const hp = overrides.hp ?? (kind === "king" ? 4824 : kind === "princess" ? 3052 : 700);
  return {
    id, team, kind, x, y,
    radius: tower ? 1.5 : 0.6,
    hp,
    max_hp: overrides.max_hp ?? hp,
    flying: false,
    deploying: false,
    label: kind === "king" ? "K" : kind === "princess" ? "P" : "Kn",
    name: kind === "king" ? "King tower" : kind === "princess" ? "Princess tower" : "Knight",
    ...overrides,
  };
};

export const towers = (): BoardEntity[] => [
  entity(1, 0, "king", 9, 3),
  entity(2, 0, "princess", 3.5, 6.5),
  entity(3, 0, "princess", 14.5, 6.5),
  entity(4, 1, "king", 9, 29),
  entity(5, 1, "princess", 3.5, 25.5),
  entity(6, 1, "princess", 14.5, 25.5),
];

export const playState = (overrides: Partial<PlayState> = {}): PlayState => ({
  id: "game1",
  over: false,
  winner: null,
  opponent: "search-bot",
  step: 3,
  time_left_s: 174,
  overtime: false,
  elixir: 6.5,
  crowns: [0, 0],
  hand: [
    { slot: 0, name: "Knight", cost: 3, kind: "TROOP" },
    { slot: 1, name: "Fireball", cost: 4, kind: "SPELL" },
    { slot: 2, name: "Giant", cost: 5, kind: "TROOP" },
    { slot: 3, name: "Cannon", cost: 3, kind: "BUILDING" },
  ],
  next_card: "Archer",
  events: ["your Knight was deployed"],
  moves: [
    { index: 0, slot: -1, card: "wait", cost: 0, kind: "WAIT", target: "save elixir", x: null, y: null },
    { index: 1, slot: 0, card: "Knight", cost: 3, kind: "TROOP", target: "left bridge", x: 3.5, y: 14 },
    { index: 2, slot: 0, card: "Knight", cost: 3, kind: "TROOP", target: "right bridge", x: 14.5, y: 14 },
    { index: 3, slot: 1, card: "Fireball", cost: 4, kind: "SPELL", target: "enemy king tower", x: 9, y: 29 },
  ],
  entities: [...towers(), entity(10, 1, "troop", 8, 20)],
  spells: [],
  zones: [
    { name: "left bridge", x: 3.5, y: 14 },
    { name: "right bridge", x: 14.5, y: 14 },
  ],
  log: ["[2:56] you played Knight @ left bridge"],
  opponent_thinking: null,
  saved_as: null,
  save_error: null,
  ...overrides,
});

export const battleOptions = (overrides: Partial<BattleOptions> = {}): BattleOptions => ({
  players: [claudeOpponent, gptOpponent],
  decks: deckList().decks,
  max_parallel: 4,
  config_name: "config.toml",
  ...overrides,
});

export const battleStatus = (overrides: Partial<BattleStatus> = {}): BattleStatus => ({
  name: "battle-20261114-181500-abcd1234",
  state: "running",
  exit_code: null,
  output: "starting runner\n",
  job_exists: false,
  players: ["claude-opus-5.5", "gpt-5"],
  ...overrides,
});

// ------------------------------------------------------------------------------------------------ models
export const modelRow = (overrides: Partial<ModelRow> = {}): ModelRow => ({
  name: "gpt-5",
  family: "gpt",
  logo_url: null,
  type: "llm",
  provider: "openai",
  model: "gpt-5",
  effort: "low",
  enabled: true,
  key_env: "OPENAI_API_KEY",
  key_ok: true,
  check_ok: null,
  check_detail: "",
  checked_at: null,
  price_in: 1.25,
  price_out: 10,
  games: 4,
  wins: 3,
  ...overrides,
});

// ------------------------------------------------------------------------------------------------ matches
export const decisionRow = (overrides: Partial<DecisionRow> = {}): DecisionRow => ({
  step: 0,
  team: 0,
  player: "model-a",
  time_elapsed_s: 0,
  time_left_s: 180,
  elixir: 5,
  my_towers: 9000,
  enemy_towers: 9000,
  asked: true,
  move: "1. Knight @ left bridge",
  result: "played Knight @ left bridge",
  ok: true,
  error: "",
  latency_s: 1.5,
  tokens_in: 1000,
  tokens_out: 100,
  ...overrides,
});

export const matchReport = (overrides: Partial<MatchReport> = {}): MatchReport => ({
  match_id: "a-b__s1",
  job: "tourney",
  status: "done",
  blue: "model-a",
  red: "model-b",
  seed: 1,
  winner: "model-a",
  crowns: [3, 0],
  wall_s: 12,
  error: null,
  has_replay: true,
  decks: null,
  deck: GIANT_BEATDOWN,
  decision_seconds: 2,
  decisions: [
    decisionRow({ step: 0, team: 0, player: "model-a", time_elapsed_s: 0 }),
    decisionRow({ step: 0, team: 1, player: "model-b", time_elapsed_s: 0, move: "0. wait", result: "wait" }),
    decisionRow({ step: 1, team: 0, player: "model-a", time_elapsed_s: 2, asked: false, move: "0. wait", result: "wait", latency_s: null, tokens_in: 0, tokens_out: 0 }),
    decisionRow({ step: 2, team: 1, player: "model-b", time_elapsed_s: 4, ok: false, error: "reply had no MOVE line", move: null, result: null }),
  ],
  ...overrides,
});

// ------------------------------------------------------------------------------------------------ results, overview and jobs
export const arenaPlayer = (overrides: Partial<ArenaPlayer> = {}): ArenaPlayer => ({
  rank: 1,
  name: "model-a",
  family: "claude",
  logo_url: null,
  llm: true,
  games: 4,
  wins: 3,
  losses: 1,
  draws: 0,
  win_rate: 0.75,
  crowns: 2.5,
  conceded: 1,
  crown_diff: 6,
  three_crowns: 2,
  reliability: 0.98,
  think_s: 2.4,
  cost_per_game: 0.031,
  deck_valid: null,
  decisions: 120,
  as_blue: [2, 0, 0],
  as_red: [1, 1, 0],
  ...overrides,
});

export const arenaGame = (overrides: Partial<ArenaGame> = {}): ArenaGame => ({
  id: "a-b__s1",
  job: "tourney",
  blue: "model-a",
  red: "model-b",
  winner: 0,
  crowns: [3, 0],
  ticks: 900,
  deck_name: "giant-beatdown",
  deck_kind: "preset",
  finished_at: 1_800_000_100,
  replay: true,
  ...overrides,
});

export const arenaRun = (overrides: Partial<ArenaRun> = {}): ArenaRun => ({
  name: "tourney",
  status: "running",
  format: "round_robin",
  player_count: 3,
  deck_rules: "Preset decks",
  scored_games: 1,
  created_at: 1_800_000_000,
  ...overrides,
});

export const arenaResults = (overrides: Partial<ArenaResults> = {}): ArenaResults => ({
  name: "tourney",
  format: "round_robin",
  deck_rules: "Preset decks",
  running: false,
  updated_at: 1_800_000_200,
  players: [arenaPlayer(), arenaPlayer({ rank: 2, name: "model-b", family: "gpt", wins: 1, losses: 3, win_rate: 0.25, crowns: 0.5, crown_diff: -6, three_crowns: 0, reliability: 0.9 })],
  games: [arenaGame()],
  ...overrides,
});

export const overviewJob = (overrides: Partial<OverviewJob> = {}): OverviewJob => ({
  name: "tourney",
  status: "running",
  notes: "a note",
  created_at: 1_800_000_000,
  started_at: 1_800_000_010,
  players: ["model-a", "model-b", "bot"],
  done: 1,
  total: 3,
  running: 1,
  queued: 1,
  crashed: 0,
  elapsed_s: 45,
  eta_s: 93,
  progress: 0.33,
  ...overrides,
});

export const overview = (jobs: OverviewJob[] = [overviewJob(), overviewJob({ name: "battle-1", status: "done", notes: "", done: 1, total: 1, running: 0, queued: 0, progress: 1, eta_s: null, players: ["model-a", "model-b"] })]): Overview => ({
  jobs,
  totals: { jobs: jobs.length, running_jobs: jobs.filter((j) => j.status === "running").length, matches_done: 2, matches_total: 4, decisions: 6, est_spend_usd: 0.013 },
});

export const matchRow = (overrides: Partial<MatchRow> = {}): MatchRow => ({
  match_id: "a-b__s1",
  status: "done",
  blue: "model-a",
  red: "model-b",
  seed: 1,
  winner: "model-a",
  crowns: [3, 0],
  ending: "3-crown knockout",
  time_left_s: 120,
  length_s: 45,
  errors_blue: 3,
  errors_red: 0,
  wall_s: 12,
  has_replay: true,
  error: null,
  ...overrides,
});

export const jobReport = (overrides: Partial<JobReport> = {}): JobReport => ({
  name: "tourney",
  status: "running",
  notes: "a note",
  started_at: 1_800_000_010,
  finished_at: null,
  est_spend_usd: 0.013,
  done: 1,
  total: 3,
  running: 1,
  queued: 1,
  crashed: 0,
  elapsed_s: 47,
  eta_s: 93,
  progress: 0.33,
  standings: [
    { rank: 1, player: "model-a", family: "claude", logo_url: null, games: 1, wins: 1, draws: 0, losses: 0, win_rate: 1, crowns_for: 3, crowns_against: 0 },
    { rank: 2, player: "model-b", family: "gpt", logo_url: null, games: 1, wins: 0, draws: 0, losses: 1, win_rate: 0, crowns_for: 0, crowns_against: 3 },
  ],
  head_to_head: [
    { player: "model-a", opponent: "model-b", points: 1, games: 1, score: 1 },
    { player: "model-b", opponent: "model-a", points: 0, games: 1, score: 0 },
  ],
  win_table: [],
  endings: [{ ending: "3-crown knockout", matches: 1 }],
  metrics: [],
  config_toml: "[tournament]\nseeds = [1]\n",
  anchor: null,
  decision_ticks: 40,
  ...overrides,
});
