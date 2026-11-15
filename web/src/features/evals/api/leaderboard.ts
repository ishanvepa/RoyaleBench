import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

export interface LeaderboardFilters {
  dataset: string;
  revision: string;
  harness: string;
  includeSmoke: boolean;
  fullOnly: boolean;
}

/** Every finished run, smoke tests included: the pool that overview-style totals are summed over. */
export const ALL_RESULTS: LeaderboardFilters = { dataset: "", revision: "", harness: "", includeSmoke: true, fullOnly: false };

function query(filters: LeaderboardFilters) {
  return {
    dataset: filters.dataset || undefined,
    revision: filters.revision || undefined,
    harness: filters.harness || undefined,
    include_smoke: filters.includeSmoke,
    full_only: filters.fullOnly,
  };
}

export function useLeaderboard(filters: LeaderboardFilters) {
  return useQuery({
    queryKey: qk.evals.leaderboard(filters),
    queryFn: () => unwrap(api.GET("/api/evals/leaderboard", { params: { query: query(filters) } })),
    placeholderData: keepPreviousData,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
}

/**
 * Cost data is downloaded in the background on the server. Starting it, polling its progress, and refreshing
 * the leaderboard when it finishes are all handled here.
 */
export function useCostsDownload(filters: LeaderboardFilters, runIds?: string[]) {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: qk.evals.costs(),
    queryFn: () => unwrap(api.GET("/api/evals/leaderboard/costs")),
    refetchInterval: (q) => (q.state.data?.state === "running" ? 1_000 : 30_000),
  });
  const start = useMutation({
    mutationFn: () => runIds
      ? unwrap(api.POST("/api/evals/jobs/costs", { body: runIds }))
      : unwrap(api.POST("/api/evals/leaderboard/costs", { params: { query: query(filters) } })),
    onSuccess: (data) => {
      queryClient.setQueryData(qk.evals.costs(), data);
      // A cached or very small download can finish before the POST returns.
      if (data.state !== "running") {
        void queryClient.invalidateQueries({ queryKey: qk.evals.leaderboardAll() });
        void queryClient.invalidateQueries({ queryKey: qk.evals.jobsAll() });
        void queryClient.invalidateQueries({ queryKey: ["evals", "job"] });
      }
    },
  });

  const previous = useRef<string | undefined>(undefined);
  useEffect(() => {
    const state = status.data?.state;
    if (previous.current === "running" && state !== "running") {
      void queryClient.invalidateQueries({ queryKey: qk.evals.leaderboardAll() });
      void queryClient.invalidateQueries({ queryKey: qk.evals.jobsAll() });
      void queryClient.invalidateQueries({ queryKey: ["evals", "job"] });
    }
    previous.current = state;
  }, [status.data?.state, queryClient]);

  return { status: status.data, start };
}
