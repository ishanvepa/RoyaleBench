import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/api/client";

/**
 * Defaults for every query:
 * - data counts as fresh for 5 s, so several components asking for the same thing share one request;
 * - a failure is retried (twice, backing off) only when it is transient: a bad request or a missing
 *   sign-in will not fix itself, so those fail at once instead of hanging on a spinner;
 * - mutations are never retried automatically, because a retried "start job" would start two jobs.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: true,
        retry: (failureCount, error) => failureCount < 2 && error instanceof ApiError && error.transient,
        retryDelay: (attempt) => Math.min(1_000 * 2 ** attempt, 8_000),
      },
      mutations: { retry: false },
    },
  });
}
