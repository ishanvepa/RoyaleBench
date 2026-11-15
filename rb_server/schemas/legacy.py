"""Request and response models for /api/legacy (the original arena: tournaments, battles, decks, play)."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------- results (the public leaderboard)
class ArenaRunOut(BaseModel):
    name: str
    status: str
    format: str  # round_robin | duel
    player_count: int
    deck_rules: str
    scored_games: int
    created_at: float | None = None


class ArenaRuns(BaseModel):
    runs: list[ArenaRunOut]


class ArenaPlayer(BaseModel):
    rank: int
    name: str
    family: str
    logo_url: str | None = None
    llm: bool
    games: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    crowns: float  # per game
    conceded: float  # per game
    crown_diff: int
    three_crowns: int
    reliability: float | None = None
    think_s: float | None = None
    cost_per_game: float | None = None
    deck_valid: float | None = None
    decisions: int
    as_blue: list[int]  # [wins, losses, draws]
    as_red: list[int]


class ArenaGame(BaseModel):
    id: str
    job: str
    blue: str
    red: str
    winner: int  # 0 blue, 1 red, 2 draw
    crowns: list[int]
    ticks: int | None = None
    deck_name: str | None = None
    deck_kind: str  # preset | built | unknown
    finished_at: float | None = None
    replay: bool


class ArenaResults(BaseModel):
    name: str
    format: str
    deck_rules: str
    running: bool
    updated_at: float | None = None
    players: list[ArenaPlayer]
    games: list[ArenaGame]


# ---------------------------------------------------------------------- overview and jobs
class JobProgress(BaseModel):
    done: int
    total: int
    running: int
    queued: int
    crashed: int
    elapsed_s: float | None = None
    eta_s: float | None = None
    progress: float


class OverviewJob(JobProgress):
    name: str
    status: str
    notes: str
    created_at: float | None = None
    started_at: float | None = None
    players: list[str]


class OverviewTotals(BaseModel):
    jobs: int
    running_jobs: int
    matches_done: int
    matches_total: int
    decisions: int
    est_spend_usd: float


class Overview(BaseModel):
    jobs: list[OverviewJob]
    totals: OverviewTotals


class JobSummary(BaseModel):
    name: str
    status: str
    created_at: float | None = None
    total_matches: int


class JobSummaries(BaseModel):
    jobs: list[JobSummary]


class StandingRow(BaseModel):
    rank: int
    player: str
    family: str
    logo_url: str | None = None
    games: int
    wins: int
    draws: int
    losses: int
    win_rate: float
    crowns_for: int
    crowns_against: int


class HeadToHeadCell(BaseModel):
    player: str
    opponent: str
    points: float
    games: int
    score: float


class WinRow(BaseModel):
    player: str
    family: str
    logo_url: str | None = None
    games: int
    wins: int
    draws: int
    losses: int
    win_rate: float
    avg_crowns: float
    avg_conceded: float
    three_crown_wins: int
    won_at_full_time: int
    won_in_overtime: int
    won_on_tiebreak: int
    wins_as_blue: int
    wins_as_red: int


class EndingCount(BaseModel):
    ending: str
    matches: int


class PlayerMetrics(BaseModel):
    player: str
    family: str
    logo_url: str | None = None
    decisions: int
    asked: int
    api_errors: int
    bad_replies: int
    plays: int
    refused: int
    error_rate: float | None = None
    bad_reply_rate: float | None = None
    avg_latency_s: float | None = None
    max_latency_s: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cache_read: int | None = None
    est_cost_usd: float


class JobReport(JobProgress):
    name: str
    status: str
    notes: str
    started_at: float | None = None
    finished_at: float | None = None
    est_spend_usd: float
    standings: list[StandingRow]
    head_to_head: list[HeadToHeadCell]
    win_table: list[WinRow]
    endings: list[EndingCount]
    metrics: list[PlayerMetrics]
    config_toml: str
    anchor: str | None = None
    decision_ticks: int


class MatchRow(BaseModel):
    match_id: str
    status: str
    blue: str
    red: str
    seed: int | None = None
    winner: str | None = None
    crowns: list[int] | None = None
    ending: str | None = None
    time_left_s: float | None = None
    length_s: float | None = None
    errors_blue: int | None = None
    errors_red: int | None = None
    wall_s: float | None = None
    has_replay: bool
    error: str | None = None


class MatchList(BaseModel):
    matches: list[MatchRow]
    total: int
    players: list[str]
    page: int
    page_size: int


class DecisionRow(BaseModel):
    step: int
    team: int  # 0 blue, 1 red
    player: str
    time_elapsed_s: float
    time_left_s: float | None = None
    elixir: float | None = None
    my_towers: int | None = None
    enemy_towers: int | None = None
    asked: bool
    move: str | None = None
    result: str | None = None
    ok: bool
    error: str
    latency_s: float | None = None
    tokens_in: int
    tokens_out: int


class MatchDecks(BaseModel):
    blue: list[str]
    red: list[str]


class MatchReport(BaseModel):
    match_id: str
    job: str
    status: str
    blue: str
    red: str
    seed: int | None = None
    winner: str | None = None
    crowns: list[int] | None = None
    wall_s: float | None = None
    error: str | None = None
    has_replay: bool
    decks: MatchDecks | None = None  # when the two sides played different decks
    deck: list[str] | None = None  # when both played the same one
    decision_seconds: float
    decisions: list[DecisionRow]


class DecisionDetail(BaseModel):
    state: str  # the exact board text the model saw
    raw: str  # its full reply


# ---------------------------------------------------------------------- models
class ModelRow(BaseModel):
    name: str
    family: str
    logo_url: str | None = None
    type: str
    provider: str
    model: str
    effort: str
    enabled: bool
    key_env: str | None = None
    key_ok: bool | None = None
    check_ok: bool | None = None
    check_detail: str
    checked_at: float | None = None
    price_in: float | None = None
    price_out: float | None = None
    games: int
    wins: int


class ModelsOut(BaseModel):
    models: list[ModelRow]
    config_name: str


class CommandStatus(BaseModel):
    """State of a background command (a model check or a tournament run)."""

    name: str
    state: str  # idle | running | done | failed
    exit_code: int | None = None
    output: str = ""


# ---------------------------------------------------------------------- decks
class CardInfo(BaseModel):
    name: str
    elixir: int
    kind: str  # Troop | Building | Spell


class DeckOut(BaseModel):
    key: str  # presets are their own name; saved decks are "custom:<id>"
    name: str
    cards: list[str]
    preset: bool
    avg_elixir: float
    id: str | None = None


class DeckList(BaseModel):
    decks: list[DeckOut]
    cards: list[CardInfo]


class DeckIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    cards: list[str]


# ---------------------------------------------------------------------- play (turn-based, one human vs a bot or model)
class PlayOpponent(BaseModel):
    name: str
    family: str
    logo_url: str | None = None
    kind: str  # bot | llm
    provider: str = ""
    model: str = ""


class PlayOptions(BaseModel):
    opponents: list[PlayOpponent]
    decks: list[DeckOut]
    tick_choices: list[int]


class PlayStart(BaseModel):
    opponent: str
    deck: str  # a deck key (see DeckOut.key)
    opponent_deck: str | None = None  # None = the same deck as yours
    seed: int = Field(default=1, ge=1, le=10_000)
    ticks: int = 40


class PlayMoveIn(BaseModel):
    index: int = Field(ge=0, description="Index in the move list of the current PlayState")


class BoardEntity(BaseModel):
    id: int
    team: int  # 0 = you (blue, bottom), 1 = the opponent (red, top)
    kind: str  # troop | building | king | princess
    x: float  # tiles from your left edge (0..18)
    y: float  # tiles from your back edge (0..32)
    radius: float
    hp: int
    max_hp: int
    flying: bool
    deploying: bool
    label: str
    name: str


class BoardSpell(BaseModel):
    team: int
    x: float
    y: float
    radius: float
    name: str


class BoardZone(BaseModel):
    name: str
    x: float
    y: float


class PlayCard(BaseModel):
    slot: int
    name: str
    cost: int
    kind: str


class PlayMove(BaseModel):
    index: int
    slot: int  # -1 for "wait"
    card: str
    cost: int
    kind: str  # TROOP | BUILDING | SPELL | WAIT
    target: str
    x: float | None = None  # where it lands, in tiles
    y: float | None = None


class OpponentThinking(BaseModel):
    time: str
    text: str


class PlayState(BaseModel):
    id: str
    over: bool
    winner: int | None = None  # 0 you, 1 the opponent, 2 a draw
    opponent: str
    step: int
    time_left_s: float
    overtime: bool
    elixir: float
    crowns: list[int]  # [yours, theirs]
    hand: list[PlayCard]
    next_card: str
    events: list[str]
    moves: list[PlayMove]
    entities: list[BoardEntity]
    spells: list[BoardSpell]
    zones: list[BoardZone]
    log: list[str]
    opponent_thinking: OpponentThinking | None = None
    saved_as: str | None = None
    save_error: str | None = None


# ---------------------------------------------------------------------- battles (model vs model)
class BattleRequest(BaseModel):
    players: list[str] = Field(min_length=2, max_length=2)
    mode: str = Field(default="mirror", pattern="^(mirror|build)$")  # mirror: configured/chosen decks; build: models build their own
    deck: str | None = None  # a deck key; only used in mirror mode
    parallel: int = Field(default=1, ge=1, le=6)


class BattlePreview(BaseModel):
    valid: bool
    games: int = 0
    error: str | None = None


class BattleOptions(BaseModel):
    players: list[PlayOpponent]
    decks: list[DeckOut]
    max_parallel: int
    config_name: str


class BattleStatus(CommandStatus):
    job_exists: bool = False
    players: list[str] = []


class BattleList(BaseModel):
    battles: list[BattleStatus]
