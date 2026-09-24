import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { UnavailableNote } from "@/components/common/States";
import type { AngleEffectiveness } from "@/api/historyTypes";

/**
 * Average title-quality score by content angle.
 *
 * A horizontal bar: the job is comparing magnitude across named categories,
 * and angle names are variable-length text that reads better on the y-axis.
 * One series, so one hue and no legend — the card title names the measure.
 * Every bar is directly labelled, so the value never depends on reading the
 * axis or the colour.
 *
 * Deliberately not rendered below two angles: a one-bar bar chart is a stat
 * tile wearing a costume, and this product should not imply a comparison it
 * does not have the data for.
 */
const MIN_ANGLES_FOR_CHART = 2;

interface Row {
  angle: string;
  score: number;
  runs: number;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;

  return (
    <div className="rounded-xl border border-border bg-popover px-3 py-2 shadow-elevated">
      <p className="text-xs font-semibold text-popover-foreground">{row.angle}</p>
      <p className="numeric mt-0.5 text-[11px] text-muted-foreground">
        {row.score.toFixed(1)} / 10 average title quality
      </p>
      <p className="text-[11px] text-muted-foreground">
        {row.runs} {row.runs === 1 ? "run" : "runs"}
      </p>
    </div>
  );
}

export function AngleChart({ data }: { data: AngleEffectiveness[] }) {
  const rows: Row[] = data
    .filter((item) => typeof item.avg_title_score === "number")
    .map((item) => ({
      angle: String(item.content_angle ?? "Unknown"),
      score: Number(item.avg_title_score),
      runs: Number(item.run_count ?? 0),
    }))
    .sort((a, b) => b.score - a.score);

  if (rows.length < MIN_ANGLES_FOR_CHART) {
    return (
      <div className="space-y-4">
        {/* The shape of the chart to come; decorative, and carries no values. */}
        <div className="space-y-2.5 opacity-60" aria-hidden="true">
          {[82, 64, 46].map((width) => (
            <div key={width} className="flex items-center gap-3">
              <span className="h-2.5 w-20 rounded-full bg-muted" />
              <span
                className="h-6 rounded-r-lg border border-dashed border-border bg-linear-to-r from-transparent to-muted"
                style={{ width: `${width}%` }}
              />
            </div>
          ))}
        </div>
        <UnavailableNote>
          {rows.length === 1
            ? `Only one content angle has been analysed so far (${rows[0]?.angle}, averaging ${rows[0]?.score.toFixed(1)} / 10). A comparison needs at least two.`
            : "No scored content angles yet. Generate a few packages and their angles will be compared here."}
        </UnavailableNote>
      </div>
    );
  }

  return (
    <>
      <div style={{ height: Math.max(150, rows.length * 46) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 4, right: 44, bottom: 4, left: 4 }}
            barCategoryGap={8}
          >
            <defs>
              <linearGradient id="angle-bar" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="var(--chart-1)" stopOpacity={0.55} />
                <stop offset="1" stopColor="var(--chart-1)" stopOpacity={1} />
              </linearGradient>
            </defs>
            <CartesianGrid horizontal={false} stroke="var(--chart-grid)" strokeDasharray="2 4" />
            <XAxis
              type="number"
              domain={[0, 10]}
              tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
              stroke="var(--chart-grid)"
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="angle"
              width={116}
              tick={{ fill: "var(--chart-axis)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ fill: "var(--chart-grid)", fillOpacity: 0.35 }}
            />
            <Bar
              dataKey="score"
              fill="url(#angle-bar)"
              radius={[0, 8, 8, 0]}
              isAnimationActive={false}
            >
              <LabelList
                dataKey="score"
                position="right"
                offset={8}
                formatter={(value: number) => value.toFixed(1)}
                style={{ fill: "var(--foreground)", fontSize: 11, fontWeight: 600 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Identity is never colour-alone: the same numbers as a table. */}
      <details className="group mt-3">
        <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
          View as table
        </summary>
        <table className="mt-2 w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border text-[11px] text-muted-foreground">
              <th scope="col" className="pb-1.5 font-medium">Content angle</th>
              <th scope="col" className="pb-1.5 font-medium">Avg title quality</th>
              <th scope="col" className="pb-1.5 font-medium">Runs</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row) => (
              <tr key={row.angle}>
                <td className="py-1.5 text-foreground">{row.angle}</td>
                <td className="numeric py-1.5 text-muted-foreground">{row.score.toFixed(1)} / 10</td>
                <td className="numeric py-1.5 text-muted-foreground">{row.runs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Average local title-quality heuristic per angle across your saved analyses. It reflects how
        the generator scored the packaging, not how videos performed.
      </p>
    </>
  );
}
