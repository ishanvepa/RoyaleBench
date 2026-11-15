import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

/** Valkyrie/Modal connection, secrets, harnesses and the server's settings. Changes rarely. */
export function useEnvironment() {
  return useQuery({
    queryKey: qk.evals.environment(),
    queryFn: () => unwrap(api.GET("/api/evals/environment")),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}
