import { Outlet } from "react-router";
import { Banner } from "@/components/ui/banner";
import { TabNav } from "@/components/ui/tab-nav";
import { useEnvironment } from "./api/environment";

const SECTIONS = [
  { to: "/evals/jobs", label: "Jobs" },
  { to: "/evals/benchmarks", label: "Benchmarks" },
  { to: "/evals/leaderboard", label: "Leaderboard" },
  { to: "/evals/overview", label: "Overview" },
  { to: "/evals/models", label: "Models" },
];

/** Says up front when jobs cannot run (not signed in, Modal missing, read-only) instead of failing on click. */
function EnvironmentBanner() {
  const { data: env, error } = useEnvironment();
  if (error && !env) return null; // each page shows its own error; the server is unreachable
  if (!env) return null;
  return (
    <div className="mb-6 space-y-3 empty:hidden">
      {env.fake ? (
        <Banner tone="info" title="Simulated Valkyrie">
          This server is running with fake data. Nothing here talks to Valkyrie or Modal, and nothing costs money.
        </Banner>
      ) : null}
      {!env.valkyrie_ok ? (
        <Banner tone="danger" title={env.valkyrie_error_kind === "auth" ? "Not signed in to Valkyrie" : "Can't reach Valkyrie"}>
          {env.valkyrie_error}
        </Banner>
      ) : !env.modal_configured ? (
        <Banner tone="warning" title="Modal isn't connected">
          Valkyrie has no <code>{env.settings.provider}</code> sandbox provider configured for this organization, so jobs can&apos;t start. See docs/modal_guide.md.
        </Banner>
      ) : null}
      {env.read_only ? (
        <Banner tone="neutral" title="Read-only">
          You can browse everything, but starting, stopping and publishing are turned off on this server.
        </Banner>
      ) : null}
    </div>
  );
}

export function EvalsLayout() {
  return (
    <>
      <TabNav items={SECTIONS} label="Evals sections" className="mb-6 justify-center" />
      <EnvironmentBanner />
      <Outlet />
    </>
  );
}
