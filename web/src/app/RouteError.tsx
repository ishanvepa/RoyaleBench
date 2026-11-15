import { Component, type ErrorInfo, type ReactNode } from "react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router";
import { ErrorState } from "@/components/domain/ErrorState";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      description="This address does not match any page."
      action={
        <Button asChild variant="secondary">
          <Link to="/">Go to Jobs</Link>
        </Button>
      }
    />
  );
}

/** Shown by the router when a route throws while loading or rendering. */
export function RouteError() {
  const error = useRouteError();
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />;
  return <ErrorState error={error} title="This page failed to load" onRetry={() => window.location.reload()} />;
}

interface BoundaryState {
  error: Error | null;
}

/** Catches render errors in a subtree so one broken widget cannot blank the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode; fallback?: (error: Error) => ReactNode }, BoundaryState> {
  override state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Render error:", error, info.componentStack);
  }

  override render() {
    if (this.state.error) {
      return this.props.fallback ? (
        this.props.fallback(this.state.error)
      ) : (
        <ErrorState error={this.state.error} title="This part of the page crashed" onRetry={() => this.setState({ error: null })} />
      );
    }
    return this.props.children;
  }
}
