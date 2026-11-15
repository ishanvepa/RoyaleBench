import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DecisionRow } from "@/api/types";
import { seriesOf, type SeriesPoint } from "./series";

const TICK = { fill: "var(--rb-muted)", fontSize: 11 };
const AXIS_LABEL = { fill: "var(--rb-muted)", fontSize: 11 };

function SideChart({ title, data, blue, red, yLabel }: { title: string; data: SeriesPoint[]; blue: string; red: string; yLabel: string }) {
  return (
    <figure className="rounded-xl border border-line bg-surface p-4">
      <figcaption className="mb-2 text-[13px] font-medium">{title}</figcaption>
      <div className="h-64" role="img" aria-label={`${title}: ${blue} (blue) against ${red} (red) over game time`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 4 }}>
            <CartesianGrid stroke="var(--rb-border)" strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tick={TICK}
              stroke="var(--rb-border)"
              height={44}
              label={{ ...AXIS_LABEL, value: "game time elapsed (s)", position: "insideBottom", offset: 0 }}
            />
            <YAxis tick={TICK} stroke="var(--rb-border)" width={68} label={{ ...AXIS_LABEL, value: yLabel, angle: -90, position: "insideLeft", offset: 4 }} />
            <Tooltip
              contentStyle={{ background: "var(--rb-surface)", border: "1px solid var(--rb-border)", borderRadius: 8, fontSize: 12, color: "var(--rb-ink)" }}
              labelFormatter={(t) => `${t}s`}
            />
            <Legend verticalAlign="top" align="right" height={28} wrapperStyle={{ fontSize: 12 }} />
            {/* Blue is wide and solid, red narrower and dashed: when the two sides have equal values, both stay visible. */}
            <Line type="stepAfter" dataKey="blue" name={`blue: ${blue}`} stroke="var(--rb-side-blue)" strokeWidth={3.5} dot={false} isAnimationActive={false} />
            <Line type="stepAfter" dataKey="red" name={`red: ${red}`} stroke="var(--rb-side-red)" strokeWidth={1.75} strokeDasharray="6 3" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

export function MatchCharts({ decisions, blue, red }: { decisions: DecisionRow[]; blue: string; red: string }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <SideChart title="Own tower HP (sum of the three towers)" data={seriesOf(decisions, "my_towers")} blue={blue} red={red} yLabel="tower HP" />
      <SideChart title="Elixir at each decision" data={seriesOf(decisions, "elixir")} blue={blue} red={red} yLabel="elixir" />
    </div>
  );
}
