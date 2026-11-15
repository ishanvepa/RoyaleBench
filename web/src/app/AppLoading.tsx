import { Loader2 } from "lucide-react";

/** Shown by the router while the first page's code is still loading, so the first paint is never a blank screen. */
export function AppLoading() {
  return (
    <div role="status" aria-label="Loading" className="grid min-h-screen place-items-center text-muted">
      <Loader2 className="size-5 animate-spin" aria-hidden />
    </div>
  );
}
