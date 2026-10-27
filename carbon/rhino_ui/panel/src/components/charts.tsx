// shadcn/ui charts (Recharts) for the Results page: bars and the doughnut. Drafted by an AI agent (Claude) - review before trusting.
// Against targets, whole life by stage and the trajectory: components/charts-rich.tsx.
import { Bar, BarChart, Cell, Label, LabelList, Pie, PieChart, ReferenceLine, XAxis, YAxis } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { fmt } from "@/lib/charts"
import { cn } from "@/lib/utils"

export type BarRow = { label: string; value: number | null | undefined; color: string; sep?: boolean; muted?: boolean }

const config = { value: { label: "Value" } } satisfies ChartConfig
const ROW = 30                      // px per bar row

/** One tooltip line: colour, what it is, the figure and its unit (en-GB grouping). */
function TipRow({ color, label, value, unit, extra }: { color: string; label: string; value: number; unit: string; extra?: string }) {
  return (
    <div className="flex w-full min-w-44 items-center gap-2">
      <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: color }} />
      <span className="flex-1 text-muted-foreground">{label}</span>
      <span className="num font-medium text-foreground">{fmt(value)}<span className="ml-1 font-normal text-muted-foreground">{unit}</span>{extra && <span className="ml-1.5 text-muted-foreground">{extra}</span>}</span>
    </div>
  )
}

/**
 * Horizontal bars, one value label per bar. Negative values (module D) run left of a zero line; a row with sep: true
 * starts a separated group (a blank row before it).
 */
export function HBarChart({ rows, unit, labelWidth = 136, title }: { rows: BarRow[]; unit: string; labelWidth?: number; title: string }) {
  const data = rows.flatMap((r, i) => [
    ...(r.sep ? [{ key: `gap${i}`, label: "", value: null as number | null, fill: "transparent", muted: false }] : []),
    { key: r.label, label: r.label, value: r.value ?? null, fill: r.color, muted: !!r.muted },
  ])
  const neg = rows.some((r) => (r.value || 0) < 0)
  return (
    <ChartContainer config={config} className="aspect-auto w-full" style={{ height: data.length * ROW + 8 }} role="img" aria-label={title}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 44, bottom: 0, left: 0 }} barCategoryGap={7} accessibilityLayer>
        <YAxis dataKey="key" type="category" width={labelWidth} tickLine={false} axisLine={false} interval={0}
          tick={({ x, y, payload }) => {
            const d = data.find((r) => r.key === payload.value)
            return (
              <text x={Number(x) - 6} y={y} dy={4} textAnchor="end" className={cn("fill-muted-foreground text-xs", d?.muted && "italic")}>
                {d?.label}
              </text>
            )
          }} />
        <XAxis type="number" hide domain={[neg ? "dataMin" : 0, "dataMax"]} />
        <ChartTooltip cursor={false} allowEscapeViewBox={{ x: true, y: true }} wrapperStyle={{ zIndex: 30 }}
          content={<ChartTooltipContent hideLabel formatter={(value, _n, item) => (
            <TipRow color={item.payload.fill} label={item.payload.label} value={Number(value)} unit={unit} />
          )} />} />
        {neg && <ReferenceLine x={0} stroke="var(--chart-axis)" />}
        <Bar dataKey="value" name="value" radius={3} isAnimationActive={false}>
          {data.map((d) => <Cell key={d.key} fill={d.fill} />)}
          {/* value right of the bar's outer end; for a negative bar, right of the zero line (clear of the row label) */}
          <LabelList dataKey="value" content={({ x, y, width, height, value }) => value == null ? null : (
            <text x={Math.max(Number(x), Number(x) + Number(width)) + 6} y={Number(y) + Number(height) / 2} dy={4}
              className="num fill-foreground" fontSize={12}>{fmt(Number(value))}</text>
          )} />
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

export type Slice = { label: string; value: number | null | undefined; color: string }

/** Doughnut with the total in the middle; the legend with values and shares is drawn next to it by the page. */
export function DonutChart({ parts, center, unit, title }: { parts: Slice[]; center: string; unit: string; title: string }) {
  const data = parts.filter((p) => (p.value || 0) > 0).map((p) => ({ label: p.label, value: p.value as number, fill: p.color }))
  const total = data.reduce((a, p) => a + p.value, 0)
  return (
    <ChartContainer config={config} className="aspect-square w-44 shrink-0" role="img" aria-label={title}>
      <PieChart>
        <ChartTooltip cursor={false} allowEscapeViewBox={{ x: true, y: true }} wrapperStyle={{ zIndex: 30 }}
          content={<ChartTooltipContent hideLabel formatter={(value, _n, item) => (
            <TipRow color={item.payload.fill} label={item.payload.label} value={Number(value)} unit={unit}
              extra={total ? `${fmt((100 * Number(value)) / total)}%` : undefined} />
          )} />} />
        <Pie data={data} dataKey="value" nameKey="label" innerRadius="62%" outerRadius="96%" paddingAngle={data.length > 1 ? 1.2 : 0}
          stroke="var(--card)" strokeWidth={1} isAnimationActive={false}>
          {data.map((d) => <Cell key={d.label} fill={d.fill} />)}
          <Label content={({ viewBox }) => {
            if (!viewBox || !("cx" in viewBox)) return null
            const { cx, cy } = viewBox as { cx: number; cy: number }
            return (
              <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle">
                <tspan x={cx} y={cy - 4} className="num fill-foreground text-xl font-semibold">{center}</tspan>
                <tspan x={cx} y={cy + 16} className="fill-muted-foreground text-xs">{unit}</tspan>
              </text>
            )
          }} />
        </Pie>
      </PieChart>
    </ChartContainer>
  )
}
