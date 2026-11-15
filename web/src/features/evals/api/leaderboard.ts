import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

export interface LeaderboardFilters {
  dataset: string;
  revision: string;
  harness: string;
  includeSmoke: boolean;
}

function query(filters: LeaderboardFilters) {
  return {
    dataset: filters.dataset || undefined,
    revision: filters.revision || undefined,
    harness: filters.harness || undefined,
    include_smoke: filters.includeSmoke,
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
export function useCostsDownload(filters: LeaderboardFilters) {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: qk.evals.costs(),
    queryFn: () => unwrap(api.GET("/api/evals/leaderboard/costs")),
    refetchInterval: (q) => (q.state.data?.state === "running" ? 1_000 : false),
  });
  const start = useMutation({
    mutationFn: () => unwrap(api.POST("/api/evals/leaderboard/costs", { params: { query: query(filters) } })),
    onSuccess: (data) => queryClient.setQueryData(qk.evals.costs(), data),
  });

  const previous = useRef<string | undefined>(undefined);
  useEffect(() => {
    const state = status.data?.state;
    if (previous.current === "running" && state !== "running") {
      void queryClient.invalidateQueries({ queryKey: qk.evals.leaderboardAll() });
    }
    previous.current = state;
  }, [status.data?.state, queryClient]);

  return { status: status.data, start };
}
