import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "./ErrorState";

interface QueryBoundaryProps<T> {
  query: UseQueryResult<T, Error>;
  children: (data: T) => ReactNode;
  /** Shown while the first load is in flight. */
  skeleton?: ReactNode;
  errorTitle?: string;
}

function DefaultSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

/**
 * The one place that decides what a query looks like: a skeleton on first load, an error with a retry button
 * if there is nothing to show, and (if a background refresh fails) the old data under a small warning.
 */
export function QueryBoundary<T>({ query, children, skeleton, errorTitle }: QueryBoundaryProps<T>) {
  if (query.isPending) return <>{skeleton ?? <DefaultSkeleton />}</>;
  if (query.data === undefined) {
    return <ErrorState error={query.error} title={errorTitle} onRetry={() => void query.refetch()} retrying={query.isFetching} />;
  }
  return (
    <>
      {query.isError ? <ErrorState inline error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
      {children(query.data)}
    </>
  );
}
