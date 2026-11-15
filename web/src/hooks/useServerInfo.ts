import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

/** What the server says about itself. Cheap: it never calls Valkyrie, so every page can ask. */
export function useServerInfo() {
  return useQuery({
    queryKey: qk.server(),
    queryFn: () => unwrap(api.GET("/api/health")),
    staleTime: 60_000,
  });
}

/**
 * True when the server refuses anything that changes state (ROYALEBENCH_EVALS_READONLY). Pages use it to disable
 * their buttons up front and say why, instead of letting people click into a 403. Unknown counts as writable:
 * the server still enforces it either way.
 */
export function useReadOnly(): boolean {
  return useServerInfo().data?.read_only ?? false;
}
