import type { ArenaResults } from "@/api/types";
import { ModelLabel } from "@/components/domain/ModelLabel";
import { Banner } from "@/components/ui/banner";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { familyColor } from "@/lib/family";
import { METRIC_FORMAT, METRICS, skylineLayout, type MetricKey } from "./stats";

/**
 * Every player on one vertical axis by the chosen metric, best at the top. The axis is plain positioned markup,
 * so each point is real text that screen readers and find-in-page can reach.
 */
export function PerformanceView({ results, metric, onMetricChange }: { results: ArenaResults; metric: MetricKey; onMetricChange: (m: MetricKey) => void }) {
  const { points, height } = skylineLayout(results.players, metric);
  const format = METRIC_FORMAT[metric];
  return (
    <div className="space-y-6">
      <div className="flex justify-center">
        <SegmentedControl
          aria-label="Metric"
          value={metric}
          onValueChange={onMetricChange}
          options={METRICS.map((m) => ({ value: m.key, label: m.label }))}
        />
      </div>
      {results.running ? <Banner tone="info" title="In progress">Standings include finished games only.</Banner> : null}
      {points.length === 0 ? (
        <p className="py-10 text-center text-[13px] text-muted">No games yet.</p>
      ) : (
        <ol className="relative mx-auto w-full max-w-[520px]" style={{ height }} aria-label={`Players by ${METRICS.find((m) => m.key === metric)?.label}`}>
          <span aria-hidden className="absolute bottom-0 left-1/2 top-0 w-0.5 -translate-x-1/2 bg-line" />
          {points.map((p) => (
            <li key={p.player.name} className="absolute inset-x-0 flex h-[22px] -translate-y-1/2 items-center" style={{ top: p.top }}>
              <span className="w-1/2 pr-4 text-right text-sm font-semibold tabular-nums">{format(p.value)}</span>
              <span aria-hidden className="absolute left-1/2 size-[13px] -translate-x-1/2 rounded-full" style={{ background: familyColor(p.player.family) }} />
              <span className="w-1/2 pl-4 text-sm" style={{ color: familyColor(p.player.family) }}>
                <ModelLabel model={p.player.name} logoUrl={p.player.logo_url} />
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
