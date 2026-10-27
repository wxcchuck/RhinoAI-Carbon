// shadcn/ui charts (Recharts) with WLCA-specific overlays: against targets, whole life by stage, the trajectory.
// Drafted by an AI agent (Claude) - review before trusting.
// Recharts draws the axes, grid, bars, lines and tooltips; what it has no stock part for is drawn by small overlay
// components that read the chart's own scales (useXAxisScale / useYAxisScale, Recharts 3.8): target lines that span
// one column only, column totals, replacement-year markers with staggered labels, and end values nudged apart.
// The geometry rules are those of the SVG charts they replace (rhino_ui/web/charts.js).
import type { ReactNode } from "react"
import {
  Bar, BarChart, CartesianGrid, LabelList, Line, LineChart, Rectangle, ReferenceLine, XAxis, YAxis,
  useXAxisScale, useYAxisScale, usePlotArea, ZIndexLayer, DefaultZIndexes, type BarShapeProps,
} from "recharts"
import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { fmt, type Col, type Event, type Series, type StackCol } from "@/lib/charts"

const HALO = { paintOrder: "stroke", stroke: "var(--card)", strokeWidth: 3, strokeLinejoin: "round" } as const

/** "Nice" axis step for a range: 1, 2 or 5 x 10^n giving about `n` ticks. */
function niceStep(range: number, n = 5) {
  const raw = range / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p
}
const range = (a: number, b: number, s: number) => {
  const out: number[] = []
  for (let t = a; t <= b + 1e-9; t += s) out.push(Math.round(t * 1e6) / 1e6)
  return out
}

/** Column label and its sub-lines ("excl. ext. works · UKNZCBS offices") under a category axis. */
function columnTick(rows: { key: string; label: string; sub?: string }[]) {
  return function Tick({ x, y, payload }: { x?: number | string; y?: number | string; payload?: { value: string } }) {
    const r = rows.find((d) => d.key === payload?.value)
    if (!r) return null
    return (
      <g transform={`translate(${x},${y})`}>
        <text y={14} textAnchor="middle" className="fill-foreground" fontSize={11.5} fontWeight={600}>{r.label}</text>
        {String(r.sub || "").split(" · ").filter(Boolean).map((t, j) => (
          <text key={j} y={28 + 13 * j} textAnchor="middle" className="fill-muted-foreground" fontSize={10.5}>{t}</text>
        ))}
      </g>
    )
  }
}

/** A chart that keeps a readable width: below it the card scrolls sideways instead of squeezing the labels. */
function Scroll({ minWidth, children }: { minWidth: number; children: ReactNode }) {
  return <div className="overflow-x-auto"><div style={{ minWidth }}>{children}</div></div>
}

/** Unit label down the y axis. */
const yUnit = (unit: string) => ({ value: unit, angle: -90, position: "insideLeft" as const, offset: 4, style: { textAnchor: "middle" as const }, className: "fill-muted-foreground", fontSize: 10.5 })

function Tip({ title, rows, unit: axisUnit }: { title: ReactNode; rows: { label: string; value: number; color: string; dash?: boolean }[]; unit: string }) {
  if (!rows.length) return null
  const unit = axisUnit.replace(/ GIA.*$/, "")          // "kgCO2e/m² GIA, cumulative" -> "kgCO2e/m²" beside each figure
  return (
    <div className="grid min-w-52 gap-1.5 rounded-lg border border-border/50 bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <div className="font-medium">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2">
          {r.dash !== undefined
            ? <svg width="16" height="6" aria-hidden><line x1="0" x2="16" y1="3" y2="3" stroke={r.color} strokeWidth="2" strokeDasharray={r.dash ? "4 2" : undefined} /></svg>
            : <span className="size-2.5 shrink-0 rounded-[2px]" style={{ background: r.color }} />}
          <span className="flex-1 text-muted-foreground">{r.label}</span>
          <span className="num font-medium">{fmt(r.value)}<span className="ml-1 font-normal text-muted-foreground">{unit}</span></span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------------------------- against targets

/**
 * Stacked columns against target lines (the "benchmarking" chart). Each column is one reporting boundary; its
 * target lines span that column only, because targets on different boundaries cannot share a line.
 */
export function TargetColumnsChart({ cols, unit, title }: { cols: Col[]; unit: string; title: string }) {
  const keys: { k: string; label: string; color: string }[] = []
  cols.forEach((c) => c.segs.forEach((g) => { if (!keys.some((x) => x.label === g.label)) keys.push({ k: `s${keys.length}`, label: g.label, color: g.color }) }))
  const rows = cols.map((c) => ({ key: c.label + "|" + c.sub, label: c.label, sub: c.sub, total: c.total,
    ...Object.fromEntries(keys.map(({ k, label }) => [k, Math.max(0, c.segs.find((g) => g.label === label)?.value || 0) || null])) }))
  const peak = Math.max(1, ...cols.map((c) => Math.max(c.total || 0, ...(c.lines || []).map((l) => l.value || 0))))
  const step = niceStep(peak * 1.08), ymax = Math.ceil((peak * 1.12) / step) * step
  const config = Object.fromEntries(keys.map(({ k, label, color }) => [k, { label, color }])) satisfies ChartConfig
  return (
    <ChartContainer config={config} className="aspect-auto w-full" style={{ height: 330, maxWidth: Math.max(300, 160 * cols.length + 60) }} role="img" aria-label={title}>
      <BarChart data={rows} margin={{ top: 16, right: 8, bottom: 6, left: 4 }} barCategoryGap="29%" accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="key" tickLine={false} axisLine={{ stroke: "var(--chart-axis)" }} height={56} interval={0} tick={columnTick(rows)} />
        <YAxis domain={[0, ymax]} ticks={range(0, ymax, step)} tickFormatter={(v) => fmt(v)} tickLine={false} axisLine={false} width={52} label={yUnit(unit)} />
        <ChartTooltip cursor={{ fill: "var(--muted)", opacity: 0.5 }} content={({ active, payload }) => {
          if (!active || !payload?.length) return null
          const r = payload[0].payload as (typeof rows)[number]
          const c = cols.find((x) => x.label + "|" + x.sub === r.key)!
          return <Tip title={<>{r.label} <span className="font-normal text-muted-foreground">{r.sub}</span></>} unit={unit}
            rows={[...c.segs.filter((g) => (g.value || 0) > 0).map((g) => ({ label: g.label, value: g.value as number, color: g.color })),
              ...(c.lines || []).map((l) => ({ label: l.label, value: l.value, color: l.color, dash: true }))]} />
        }} />
        {keys.map(({ k, color }) => <Bar key={k} dataKey={k} stackId="s" fill={color} maxBarSize={64} isAnimationActive={false} />)}
        <ColumnOverlay cols={cols} rowKey={(c) => c.label + "|" + c.sub} />
      </BarChart>
    </ChartContainer>
  )
}

/** Totals above the columns and each column's target lines, labelled on the left and nudged apart when close. */
function ColumnOverlay({ cols, rowKey }: { cols: Col[]; rowKey: (c: Col) => string }) {
  const xs = useXAxisScale(), ys = useYAxisScale()
  if (!xs || !ys) return null
  return (
    <ZIndexLayer zIndex={DefaultZIndexes.line + 50}>
      {cols.map((c) => {
        const k = rowKey(c), a = xs(k, { position: "start" }), b = xs(k, { position: "end" }), cx = xs(k, { position: "middle" })
        if (a == null || b == null || cx == null) return null
        const slot = b - a
        let lastY = -1e9
        return (
          <g key={k}>
            {c.total != null && <text x={cx} y={(ys(c.total) ?? 0) - 6} textAnchor="middle" className="num fill-foreground" fontSize={12} fontWeight={600}>{fmt(c.total)}</text>}
            {(c.lines || []).slice().sort((p, q) => q.value - p.value).map((l) => {
              const ly = ys(l.value) ?? 0, x1 = cx - slot * 0.46, x2 = cx + slot * 0.46, ty = Math.max(ly - 4, lastY + 12)
              lastY = ty
              return (
                <g key={l.label}>
                  <line x1={x1} x2={x2} y1={ly} y2={ly} stroke={l.color} strokeWidth={2} strokeDasharray="6 4" />
                  <text x={x1} y={ty} fontSize={10.5} fontWeight={600} fill={l.color} style={HALO}>{l.short || l.label} {fmt(l.value)}</text>
                </g>
              )
            })}
          </g>
        )
      })}
    </ZIndexLayer>
  )
}

// ---------------------------------------------------------------------------------------------- whole life by stage

/** Stacked columns with labelled segments; negative segments hang below the axis; a column with weight < 1 is narrow. */
export function StackColumnsChart({ cols, unit, title }: { cols: StackCol[]; unit: string; title: string }) {
  const keys: { k: string; label: string; color: string }[] = []
  cols.forEach((c) => c.segs.forEach((g) => { if (!keys.some((x) => x.label === g.label)) keys.push({ k: `s${keys.length}`, label: g.label, color: g.color }) }))
  const rows = cols.map((c) => ({ key: c.label, label: c.label, sub: c.sub, narrow: (c.weight || 1) < 1,
    ...Object.fromEntries(keys.map(({ k, label }) => [k, c.segs.find((g) => g.label === label)?.value || null])) }))
  const pos = (c: StackCol) => c.segs.reduce((a, g) => a + Math.max(0, g.value || 0), 0)
  const neg = (c: StackCol) => c.segs.reduce((a, g) => a + Math.min(0, g.value || 0), 0)
  const hi = Math.max(1, ...cols.map(pos)), lo = Math.min(0, ...cols.map(neg))
  const step = niceStep((hi - lo) * 1.08), ymax = Math.ceil((hi * 1.1) / step) * step
  const fine = step / 5, ymin = lo < 0 ? -Math.max(fine, Math.ceil((-lo * 1.3) / fine) * fine) : 0
  const config = Object.fromEntries(keys.map(({ k, label, color }) => [k, { label, color }])) satisfies ChartConfig
  const seg = (i: number, label: string) => cols[i]?.segs.find((g) => g.label === label)
  const narrowShape = (p: BarShapeProps) => {
    const w = Number(p.width) || 0, x = Number(p.x) || 0
    const narrow = (p.payload as { narrow?: boolean } | undefined)?.narrow
    return narrow ? <Rectangle {...(p as object)} x={x + w * 0.22} width={w * 0.56} /> : <Rectangle {...(p as object)} />
  }
  return (
    <Scroll minWidth={190 * cols.length + 130}>
    <ChartContainer config={config} className="aspect-auto w-full" style={{ height: 380 }} role="img" aria-label={title}>
      <BarChart data={rows} stackOffset="sign" margin={{ top: 18, right: 70, bottom: 6, left: 4 }} barCategoryGap="15%" accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="key" tickLine={false} axisLine={false} height={48} interval={0} tick={columnTick(rows)} />
        <YAxis domain={[ymin, ymax]} ticks={range(Math.ceil(ymin / step) * step, ymax, step)} tickFormatter={(v) => fmt(v)} tickLine={false} axisLine={false} width={54} label={yUnit(unit)} />
        <ReferenceLine y={0} stroke="var(--chart-axis)" strokeWidth={1.2} />
        <ChartTooltip cursor={{ fill: "var(--muted)", opacity: 0.5 }} content={({ active, payload }) => {
          if (!active || !payload?.length) return null
          const r = payload[0].payload as (typeof rows)[number], c = cols.find((x) => x.label === r.key)!
          return <Tip title={c.total != null ? <>{c.label}: {c.totalLabel || ""}{fmt(c.total)}</> : c.label} unit={unit}
            rows={c.segs.filter((g) => g.value).map((g) => ({ label: g.label, value: g.text ?? g.value, color: g.color }))} />
        }} />
        {keys.map(({ k, label, color }) => (
          <Bar key={k} dataKey={k} stackId="s" fill={color} maxBarSize={124} isAnimationActive={false} shape={narrowShape}>
            <LabelList dataKey={k} content={(p) => {
              const g = seg(Number(p.index), label)
              if (!g || !g.value) return null
              const w0 = Number(p.width), x0 = Number(p.x), narrow = rows[Number(p.index)]?.narrow
              const x = narrow ? x0 + w0 * 0.22 : x0, w = narrow ? w0 * 0.56 : w0
              const h = Math.abs(Number(p.height)), top = Math.min(Number(p.y), Number(p.y) + Number(p.height)), shown = g.text ?? g.value
              if (h >= 30) return (
                <g>
                  <text x={x + w / 2} y={top + h / 2 - 2} textAnchor="middle" fontSize={11} fill={g.ink || "#fff"}>{g.label}</text>
                  <text x={x + w / 2} y={top + h / 2 + 12} textAnchor="middle" fontSize={11.5} fontWeight={600} fill={g.ink || "#fff"} className="num">{fmt(shown)}</text>
                </g>
              )
              return <text x={x + w + 6} y={top + h / 2 + 4} fontSize={10.5} className="fill-muted-foreground">{g.short || g.label} {fmt(shown)}</text>
            }} />
          </Bar>
        ))}
        <StackTotals cols={cols} />
      </BarChart>
    </ChartContainer>
    </Scroll>
  )
}

function StackTotals({ cols }: { cols: StackCol[] }) {
  const xs = useXAxisScale(), ys = useYAxisScale()
  if (!xs || !ys) return null
  return (
    <ZIndexLayer zIndex={DefaultZIndexes.line + 50}>
      {cols.map((c) => {
        if (c.total == null) return null
        const up = c.segs.reduce((a, g) => a + Math.max(0, g.value || 0), 0), cx = xs(c.label, { position: "middle" }), y = ys(up)
        if (cx == null || y == null) return null
        return <text key={c.label} x={cx} y={y - 6} textAnchor="middle" className="num fill-foreground" fontSize={12} fontWeight={600}>{c.totalLabel || ""}{fmt(c.total)}</text>
      })}
    </ZIndexLayer>
  )
}

// ---------------------------------------------------------------------------------------------- trajectory

/** Cumulative lines over years; events = dotted verticals labelled above the plot; end values nudged apart. */
export function TrajectoryChart({ series, events, unit, title, x2 }: {
  series: Series[]; events: Event[]; unit: string; title: string; x2: (x: number) => string
}) {
  const xsAll = [...new Set(series.flatMap((s) => s.x))].sort((a, b) => a - b)
  const rows = xsAll.map((x) => ({ x, ...Object.fromEntries(series.map((s, i) => {
    const j = s.x.indexOf(x)
    return [`s${i}`, j >= 0 ? s.y[j] : null]
  })) }))
  const ys = series.flatMap((s) => s.y).filter((v): v is number => v != null)
  const x0 = Math.min(...xsAll), x1 = Math.max(...xsAll), ymax0 = Math.max(1, ...ys), ymin0 = Math.min(0, ...ys)
  const step = niceStep(ymax0 - ymin0), ymax = Math.ceil((ymax0 * 1.05) / step) * step, ymin = ymin0 < 0 ? -Math.ceil(-ymin0 / step) * step : 0
  const config = Object.fromEntries(series.map((s, i) => [`s${i}`, { label: s.label, color: s.color }])) satisfies ChartConfig
  return (
    <Scroll minWidth={480}>
    <ChartContainer config={config} className="aspect-auto w-full" style={{ height: 360 }} role="img" aria-label={title}>
      <LineChart data={rows} margin={{ top: 46, right: 16, bottom: 4, left: 4 }} accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="x" type="number" domain={[x0, x1]} ticks={range(x0, x1, 10)} tickLine={false} axisLine={false} height={40} interval={0}
          tick={({ x, y, payload }) => (
            <g transform={`translate(${x},${y})`}>
              <text y={12} textAnchor="middle" fontSize={11} className="num fill-muted-foreground">{payload.value}</text>
              <text y={26} textAnchor="middle" fontSize={10} className="fill-muted-foreground">{x2(Number(payload.value))}</text>
            </g>
          )} />
        <YAxis domain={[ymin, ymax]} ticks={range(ymin, ymax, step)} tickFormatter={(v) => fmt(v)} tickLine={false} axisLine={false} width={56} label={yUnit(unit)} />
        <ReferenceLine y={0} stroke="var(--chart-axis)" strokeWidth={1.2} />
        <ChartTooltip cursor={{ stroke: "var(--chart-event)", strokeDasharray: "2 3" }} content={({ active, payload, label }) => {
          if (!active || !payload?.length) return null
          const seen = new Set<string>()
          const tipRows = payload.filter((p) => p.value != null).map((p) => {
            const s = series[Number(String(p.dataKey).slice(1))]
            return { label: s.label, value: Number(p.value), color: s.color, dash: !!(s.dash || s.dot) }
          }).filter((r) => !seen.has(r.label) && seen.add(r.label))
          return <Tip title={<>{label} <span className="font-normal text-muted-foreground">{x2(Number(label))}</span></>} rows={tipRows} unit={unit} />
        }} />
        {series.map((s, i) => (
          <Line key={i} dataKey={`s${i}`} type="linear" stroke={s.color} strokeWidth={s.width || 2} dot={false}
            activeDot={s.dot ? false : { r: 3, strokeWidth: 0, fill: s.color }} isAnimationActive={false} connectNulls={false}
            strokeDasharray={s.dot ? "1.5 3.5" : s.dash ? "7 4" : undefined} strokeLinecap={s.dot ? "round" : undefined} />
        ))}
        <TrajectoryOverlay series={series} events={events} ymin={ymin} />
      </LineChart>
    </ChartContainer>
    </Scroll>
  )
}

function TrajectoryOverlay({ series, events, ymin }: { series: Series[]; events: Event[]; ymin: number }) {
  const xs = useXAxisScale(), ys = useYAxisScale(), plot = usePlotArea()
  if (!xs || !ys || !plot) return null
  const top = plot.y, bottom = ys(ymin) ?? plot.y + plot.height
  const rowsEnd = [-1e9, -1e9, -1e9]
  const ev = events.map((e) => {
    const ex = xs(e.x) ?? 0, w = 6.2 * e.label.length
    let row = rowsEnd.findIndex((end) => ex - w / 2 > end + 6)
    if (row < 0) row = 2
    rowsEnd[row] = ex + w / 2
    return { ...e, ex, row }
  })
  const ends = series.flatMap((s) => {
    const n = s.y.length - 1
    if (s.end === false || s.y[n] == null) return []
    return [{ y: (ys(s.y[n]) ?? 0) - 6, x: (xs(s.x[n]) ?? 0) - 2, c: s.color, t: fmt(s.endValue != null ? s.endValue : s.y[n]) }]
  }).sort((a, b) => a.y - b.y)
  for (let i = 1; i < ends.length; i++) if (ends[i].y < ends[i - 1].y + 12) ends[i].y = ends[i - 1].y + 12
  return (
    <ZIndexLayer zIndex={DefaultZIndexes.line + 50}><g pointerEvents="none">
      {ev.map((e) => (
        <g key={e.x + e.label}>
          <line x1={e.ex} x2={e.ex} y1={top - 6} y2={bottom} stroke="var(--chart-event)" strokeDasharray="2 3" />
          <text x={e.ex} y={top - 30 + 12 * e.row} textAnchor="middle" fontSize={10} fontWeight={600} className="fill-muted-foreground" style={HALO}>
            {e.label}<title>{e.title || e.label}</title>
          </text>
        </g>
      ))}
      {ends.map((e, i) => (
        <text key={i} x={e.x} y={e.y} textAnchor="end" fontSize={11} fontWeight={600} fill={e.c} className="num" style={HALO}>{e.t}</text>
      ))}
    </g></ZIndexLayer>
  )
}
