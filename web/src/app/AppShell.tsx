import { Moon, Sun } from "lucide-react";
import { Link, Outlet } from "react-router";
import { Button } from "@/components/ui/button";
import { TabNav, type TabNavItem } from "@/components/ui/tab-nav";
import { ErrorBoundary } from "./RouteError";
import { useTheme } from "./theme";

/** The two areas of the app. Evals is the default; Legacy holds the original arena pages. */
const AREAS: TabNavItem[] = [
  { to: "/evals", label: "Evals" },
  { to: "/legacy", label: "Legacy" },
];

export function AppShell() {
  const { theme, toggle } = useTheme();
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-ink focus:px-3 focus:py-2 focus:text-background">
        Skip to content
      </a>
      <div className="relative mx-auto w-full max-w-[1360px] px-6 pt-8">
        <div className="absolute right-6 top-6">
          <Button variant="ghost" size="icon" onClick={toggle} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
            {theme === "dark" ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
          </Button>
        </div>
        <div className="pb-6 text-center">
          <Link to="/" className="font-display text-[26px] font-semibold tracking-tight no-underline">
            Royale<span className="font-normal">Bench</span>
          </Link>
          <p className="mt-2 text-sm text-subtle">A Clash Royale Benchmark for Language Models</p>
        </div>
        <TabNav items={AREAS} label="Sections" className="justify-center" />
      </div>
      <main id="main" className="mx-auto w-full max-w-[1360px] flex-1 px-6 pb-20 pt-6">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
      <footer className="border-t border-line py-6 text-center text-xs tracking-wide text-muted">RoyaleBench · Language models in the arena</footer>
    </div>
  );
}
