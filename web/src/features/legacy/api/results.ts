import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

export function useArenaRuns() {
  return useQuery({
    queryKey: qk.legacy.runs(),
    queryFn: () => unwrap(api.GET("/api/legacy/results")),
    staleTime: 15_000,
  });
}

/** Standings and games of one run. A run that is still playing refreshes every 30 s, like the original page. */
export function useArenaResults(job: string) {
  return useQuery({
    queryKey: qk.legacy.results(job),
    queryFn: () => unwrap(api.GET("/api/legacy/results/{job}", { params: { path: { job } } })),
    enabled: job !== "",
    refetchInterval: (query) => (query.state.data?.running ? 30_000 : false),
  });
}
