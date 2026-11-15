import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Badge } from "@/components/ui/badge";
import { Banner } from "@/components/ui/banner";
import { useBattleOptions, useBattles } from "../api/play";
import { BattleForm } from "./BattleForm";
import { BattleStatusPanel } from "./BattleStatusPanel";

function RecentBattles({ selected, onSelect }: { selected: string; onSelect: (name: string) => void }) {
  const battles = useBattles();
  const list = battles.data?.battles ?? [];
  if (list.length === 0) return null;
  return (
    <section aria-label="Recent battles" className="space-y-2">
      <h2 className="text-base">Recent battles</h2>
      <ul className="divide-y divide-line rounded-xl border border-line bg-surface">
        {list.slice(0, 8).map((b) => (
          <li key={b.name}>
            <button
              type="button"
              aria-current={b.name === selected ? "true" : undefined}
              onClick={() => onSelect(b.name)}
              className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left text-[13px] hover:bg-selected aria-[current=true]:bg-selected"
            >
              <span className="truncate font-mono text-xs">{b.name}</span>
              <Badge tone={b.state === "running" ? "info" : b.state === "done" ? "success" : "danger"}>{b.state === "done" ? "finished" : b.state}</Badge>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Two models play each other; the tournament runner does the work in the background and this follows it. */
export function BattlePanel({ battle, onSelect }: { battle: string; onSelect: (name: string) => void }) {
  const options = useBattleOptions();
  return (
    <div className="space-y-6">
      <p className="text-[13px] text-muted">Choose two models and play both sides of each matchup. Results appear under Overview and as match replays.</p>
      <QueryBoundary query={options} errorTitle="Couldn't load the battle options">
        {(data) =>
          data.players.length < 2 ? (
            <Banner tone="info" title="Not enough models">
              Enable at least two models in {data.config_name} to start a battle.
            </Banner>
          ) : (
            <BattleForm options={data} onStarted={onSelect} />
          )
        }
      </QueryBoundary>
      {battle ? <BattleStatusPanel name={battle} /> : null}
      <RecentBattles selected={battle} onSelect={onSelect} />
    </div>
  );
}
