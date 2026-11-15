import { AlertTriangle } from "lucide-react";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

/** What the user can do about each kind of failure. */
function hintFor(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  switch (error.code) {
    case "valkyrie_auth":
      return "Run `valkyrie login` in a terminal, then try again.";
    case "valkyrie_network":
    case "network":
      return "Check your connection and that the RoyaleBench server is running, then try again.";
    case "not_found":
      return "It may have been removed, or the link may be wrong.";
    case "database_unavailable":
      return "Check that the arena SQLite path is writable, then try again.";
    default:
      return null;
  }
}

interface ErrorStateProps {
  error: unknown;
  title?: string;
  onRetry?: () => void;
  retrying?: boolean;
  /** A compact one-line version for use above content that is still showing. */
  inline?: boolean;
  className?: string;
}

export function ErrorState({ error, title = "Something went wrong", onRetry, retrying, inline = false, className }: ErrorStateProps) {
  const message = error instanceof Error ? error.message : "Unknown error";
  const hint = hintFor(error);
  if (inline) {
    return (
      <div role="alert" className={cn("mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-warning/30 bg-warning/10 px-4 py-2.5 text-[13px]", className)}>
        <AlertTriangle className="size-4 shrink-0 text-warning" aria-hidden />
        <span className="min-w-0 flex-1">
          Couldn&apos;t refresh: {message} Showing the last data we have.
        </span>
        {onRetry ? (
          <Button size="sm" variant="secondary" onClick={onRetry} loading={retrying}>
            Retry
          </Button>
        ) : null}
      </div>
    );
  }
  return (
    <div role="alert" className={cn("flex flex-col items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-6 py-10 text-center", className)}>
      <AlertTriangle className="size-6 text-danger" aria-hidden />
      <h3 className="text-[15px] font-medium">{title}</h3>
      <p className="max-w-xl text-[13px] text-subtle">{message}</p>
      {hint ? <p className="max-w-xl text-[13px] text-muted">{hint}</p> : null}
      {onRetry ? (
        <Button className="mt-2" variant="secondary" onClick={onRetry} loading={retrying}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
