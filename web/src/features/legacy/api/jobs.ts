import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

const LIVE_MS = 5_000;

export function useOverview(live: boolean) {
  return useQuery({
    queryKey: qk.legacy.overview(),
    queryFn: () => unwrap(api.GET("/api/legacy/overview")),
    refetchInterval: live ? LIVE_MS : false,
  });
}

export function useJobSummaries() {
  return useQuery({
    queryKey: qk.legacy.jobs(),
    queryFn: () => unwrap(api.GET("/api/legacy/jobs")),
    staleTime: 10_000,
  });
}

export function useJobReport(job: string, live: boolean) {
  return useQuery({
    queryKey: qk.legacy.job(job),
    queryFn: () => unwrap(api.GET("/api/legacy/jobs/{job}", { params: { path: { job } } })),
    refetchInterval: (query) => (live && query.state.data?.status === "running" ? LIVE_MS : false),
  });
}

export interface MatchFilters {
  status: string[];
  player: string;
  page: number;
}

export const PAGE_SIZE = 25;

export function useJobMatches(job: string, filters: MatchFilters, live: boolean) {
  return useQuery({
    queryKey: qk.legacy.matches(job, filters),
    queryFn: () =>
      unwrap(
        api.GET("/api/legacy/jobs/{job}/matches", {
          params: {
            path: { job },
            query: { status: filters.status.length ? filters.status : undefined, player: filters.player || undefined, page: filters.page, page_size: PAGE_SIZE },
          },
        }),
      ),
    placeholderData: keepPreviousData,
    refetchInterval: live ? LIVE_MS : false,
  });
}

export function useMatch(job: string, matchId: string) {
  return useQuery({
    queryKey: qk.legacy.match(job, matchId),
    queryFn: () => unwrap(api.GET("/api/legacy/jobs/{job}/matches/{match_id}", { params: { path: { job, match_id: matchId } } })),
    // A match that is still being played refreshes; a finished one never changes again.
    refetchInterval: (query) => (query.state.data?.status === "running" ? LIVE_MS : false),
  });
}

/** The board text a model saw and its full reply: large, so only fetched when a row is selected. */
export function useDecisionDetail(job: string, matchId: string, step: number | null, team: number | null) {
  return useQuery({
    queryKey: qk.legacy.decision(job, matchId, step ?? -1, team ?? -1),
    queryFn: () =>
      unwrap(
        api.GET("/api/legacy/jobs/{job}/matches/{match_id}/decisions/{step}/{team}", {
          params: { path: { job, match_id: matchId, step: step ?? 0, team: team ?? 0 } },
        }),
      ),
    enabled: step !== null && team !== null,
    staleTime: Infinity,
  });
}
