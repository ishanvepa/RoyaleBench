import type { components } from "./schema";

type S = components["schemas"];

export type ServerInfo = S["HealthOut"];

// Evals
export type Environment = S["EnvironmentOut"];
export type EvalsSettings = S["EvalsSettingsOut"];
export type JobRow = S["JobRow"];
export type JobList = S["JobList"];
export type JobDetail = S["JobDetail"];
export type TaskRow = S["TaskRow"];
export type TaskList = S["TaskList"];
export type TaskDetail = S["TaskDetail"];
export type Trace = S["TraceOut"];
export type TraceStep = S["TraceStep"];
export type LogLine = S["LogLine"];
export type JobErrors = S["ErrorsOut"];
export type JobSpecIn = S["JobSpecIn"];
export type JobPreview = S["JobPreviewOut"];
export type JobStarted = S["JobStartOut"];

export type BenchmarkRow = S["BenchmarkRow"];
export type BenchmarkList = S["BenchmarkList"];
export type BenchmarkDetail = S["BenchmarkDetail"];
export type BenchmarkVersion = S["VersionOut"];
export type BenchmarkTask = S["TaskInfo"];
export type BenchmarkTaskDetail = S["TaskDetailOut"];
export type TaskResults = S["TaskResultsOut"];
export type TaskResultRow = S["TaskResultRow"];
export type PublishResult = S["PublishOut"];

export type LeaderboardRow = S["LeaderboardRow"];
export type Leaderboard = S["LeaderboardOut"];
export type CostsStatus = S["CostsStatus"];

/** Known run and task states. The server sends plain strings, so unknown values must still render. */
export const RUN_STATUSES = ["IN_PROGRESS", "STOPPING", "STOPPED", "FINISHED", "ERROR"] as const;
export const TASK_STATUSES = ["PENDING", "BUILDING", "IN_PROGRESS", "EVALUATING", "FINISHED", "ERROR", "STOPPED"] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const ACTIVE_RUN_STATUSES: readonly string[] = ["IN_PROGRESS", "STOPPING"];
export const isActiveRun = (status: string): boolean => ACTIVE_RUN_STATUSES.includes(status);

// Legacy arena
export type ArenaRun = S["ArenaRunOut"];
export type ArenaResults = S["ArenaResults"];
export type ArenaPlayer = S["ArenaPlayer"];
export type ArenaGame = S["ArenaGame"];
export type Overview = S["Overview"];
export type OverviewJob = S["OverviewJob"];
export type JobSummary = S["JobSummary"];
export type JobReport = S["JobReport"];
export type StandingRow = S["StandingRow"];
export type HeadToHeadCell = S["HeadToHeadCell"];
export type WinRow = S["WinRow"];
export type EndingCount = S["EndingCount"];
export type PlayerMetrics = S["PlayerMetrics"];
export type MatchRow = S["MatchRow"];
export type MatchList = S["MatchList"];
export type MatchReport = S["MatchReport"];
export type DecisionRow = S["DecisionRow"];
export type DecisionDetail = S["DecisionDetail"];
export type ModelRow = S["ModelRow"];
export type CommandStatus = S["CommandStatus"];
export type DeckOut = S["DeckOut"];
export type DeckList = S["DeckList"];
export type CardInfo = S["CardInfo"];
export type PlayOptions = S["PlayOptions"];
export type PlayOpponent = S["PlayOpponent"];
export type PlayState = S["PlayState"];
export type PlayMove = S["PlayMove"];
export type PlayCard = S["PlayCard"];
export type BoardEntity = S["BoardEntity"];
export type BoardSpell = S["BoardSpell"];
export type BoardZone = S["BoardZone"];
export type BattleOptions = S["BattleOptions"];
export type BattlePreview = S["BattlePreview"];
export type BattleRequest = S["BattleRequest"];
export type BattleStatus = S["BattleStatus"];
