import { createBrowserRouter, createMemoryRouter, Navigate, type RouteObject } from "react-router";
import { EvalsLayout } from "@/features/evals/EvalsLayout";
import { LegacyLayout } from "@/features/legacy/LegacyLayout";
import { AppLoading } from "./AppLoading";
import { AppShell } from "./AppShell";
import { NotFound, RouteError } from "./RouteError";

/**
 * Every page is its own lazily loaded chunk (each module exports `Component`), so the first paint only
 * downloads the shell and the page being opened.
 */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteError />,
    HydrateFallback: AppLoading,
    children: [
      { index: true, element: <Navigate to="/evals/jobs" replace /> },
      {
        path: "evals",
        element: <EvalsLayout />,
        children: [
          { index: true, element: <Navigate to="jobs" replace /> },
          { path: "jobs", lazy: () => import("@/features/evals/jobs/JobsPage") },
          { path: "jobs/new", lazy: () => import("@/features/evals/jobs/NewJobPage") },
          { path: "jobs/:runId", lazy: () => import("@/features/evals/jobs/JobMonitorPage") },
          { path: "benchmarks", lazy: () => import("@/features/evals/benchmarks/BenchmarksPage") },
          { path: "benchmarks/:name", lazy: () => import("@/features/evals/benchmarks/BenchmarkPage") },
          { path: "benchmarks/:name/tasks/:taskId", lazy: () => import("@/features/evals/benchmarks/TaskPage") },
          { path: "leaderboard", lazy: () => import("@/features/evals/leaderboard/LeaderboardPage") },
        ],
      },
      {
        path: "legacy",
        element: <LegacyLayout />,
        children: [
          { index: true, element: <Navigate to="leaderboard" replace /> },
          { path: "leaderboard", lazy: () => import("@/features/legacy/leaderboard/LeaderboardPage") },
          { path: "overview", lazy: () => import("@/features/legacy/overview/OverviewPage") },
          { path: "jobs/:job", lazy: () => import("@/features/legacy/job/JobPage") },
          { path: "matches/:job/:matchId", lazy: () => import("@/features/legacy/match/MatchPage") },
          { path: "models", lazy: () => import("@/features/legacy/models/ModelsPage") },
          { path: "decks", lazy: () => import("@/features/legacy/decks/DecksPage") },
          { path: "play", lazy: () => import("@/features/legacy/play/PlayPage") },
        ],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);

/** For tests: the real routes, starting at ``path``. */
export const createTestRouter = (path: string) => createMemoryRouter(routes, { initialEntries: [path] });
