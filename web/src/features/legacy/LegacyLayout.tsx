import { Outlet } from "react-router";
import { TabNav } from "@/components/ui/tab-nav";

const SECTIONS = [
  { to: "/legacy/leaderboard", label: "Leaderboard" },
  { to: "/legacy/play", label: "Play" },
  { to: "/legacy/decks", label: "Decks" },
  { to: "/legacy/overview", label: "Overview", alsoActiveFor: ["/legacy/jobs", "/legacy/matches"] },
  { to: "/legacy/models", label: "Models" },
];

/** The original arena: models playing Clash Royale against each other locally. */
export function LegacyLayout() {
  return (
    <>
      <TabNav items={SECTIONS} label="Legacy sections" className="mb-6" />
      <Outlet />
    </>
  );
}
