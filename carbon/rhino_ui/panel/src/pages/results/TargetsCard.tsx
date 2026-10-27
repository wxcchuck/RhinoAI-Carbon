// "Against targets": up to four targets drawn on their reporting boundaries, and the table of all of them.
// Drafted by an AI agent (Claude) - review before trusting.
import { ChevronRight } from "lucide-react"
import { ChartCard, Legend, Verdict, VerdictDot } from "@/components/chart-ui"
import { TargetColumnsChart } from "@/components/charts-rich"
import { fmt, sf, type Col, type Part } from "@/lib/charts"
import { patchModel, send } from "@/lib/bridge"
import type { Model } from "@/lib/model"
import { BOUNDARY, type Palette, type ResOption, type Results, type Target } from "@/lib/results"
import { cn } from "@/lib/utils"

export const MAX_CHART_TARGETS = 4
// one column per reporting boundary; targets on that boundary are drawn as lines across it
const TCOL: Record<string, [string, string]> = {
  UP_SC: ["A1-A5 shell & core", "excl. ext. works · UKNZCBS offices"], UP_WB: ["A1-A5 + Cat B", "whole building · UKNZCBS offices"],
  UP_X8: ["A1-A5", "excl. ext. works · UKNZCBS, LETI"], UP_ALL: ["A1-A5", "all elements · GLA"],
  AC_X8: ["A-C", "excl. ext. works · LETI, RIBA"], AC_ALL: ["A-C", "all elements · GLA"],
}
const UPFRONT = ["UP_SC", "UP_WB", "UP_X8", "UP_ALL"], LIFECYCLE = ["AC_X8", "AC_ALL"]
const short = (l: string) => l.replace("shell & core limit", "S&C").replace("whole-building limit", "whole bldg").replace(" design target", "")
  .replace("RIBA 2030 Challenge - ", "RIBA ").replace(" A1-A5", "").replace(" A-C", "")

export function chartTargets(m: Model, R: Results): string[] {
  const saved = (m.state.targets as { chart?: string[] | null }).chart, labels = R.targets.map((t) => t.label)
  if (Array.isArray(saved)) return saved.filter((l) => labels.includes(l))
  const pick: string[] = []         // default: the main limit, GLA aspirational, RIBA 2030 and GLA aspirational A-C
  const first = (re: RegExp) => { const t = R.targets.find((x) => re.test(x.label) && !pick.includes(x.label)); if (t) pick.push(t.label) }
  first(/UKNZCBS.*shell/); if (!pick.length) first(/UKNZCBS/)
  first(/GLA aspirational A1-A5/); first(/RIBA 2030.*2030/); first(/GLA aspirational A-C/)
  return pick.slice(0, MAX_CHART_TARGETS)
}

function boundarySegs(key: string, v: ResOption["values"], R: Results, P: Palette, groupLabels: string[]): { segs: Part[]; total: number | null } {
  const total = v[key], sc = R.sc || { fin: 1, ffe: 1, mep: 1 }
  if (typeof total !== "number") return { segs: [], total: null }
  let segs: Part[] = []
  if (key.startsWith("UP_")) {
    const share: Record<number, number> = { 3: key === "UP_SC" ? sc.fin : 1, 4: key === "UP_SC" ? sc.ffe : 1, 5: key === "UP_SC" ? sc.mep : 1 }
    groupLabels.forEach((label, i) => {
      if (i === 6 && key !== "UP_ALL") return               // external works only on the GLA boundary
      segs.push({ label, value: (Number(v["E_" + i]) || 0) * (share[i] ?? 1), color: P.groups[i % P.groups.length] })
    })
    if (key === "UP_WB" && R.catb) segs.push({ label: "Cat B + loose FF&E", value: R.catb, color: "#c9c2b4" })
    const sum = segs.reduce((a, g) => a + (g.value || 0), 0)
    segs.push({ label: "Contingency (PS Table 10)", value: Math.max(0, total - sum), color: P.cont })
  } else {
    const up = Number(key === "AC_X8" ? v.UP_X8 : v.UP_ALL) || 0
    segs = [{ label: "Upfront A1-A5", value: up, color: P.stages[0] }, { label: "In use and end of life B-C", value: Math.max(0, total - up), color: P.stages[1] }]
  }
  return { segs, total }
}

export function TargetsCard({ m, R, o, sfN, P, lineColor }: {
  m: Model; R: Results; o: ResOption; sfN: number; P: Palette; lineColor: (c: string) => string
}) {
  const v = o.values, pick = chartTargets(m, R), groupLabels = m.group_labels as string[]
  const sel = R.targets.map((t, i) => [t, i] as [Target, number]).filter(([t]) => pick.includes(t.label))
  const toggle = (label: string) => {
    const next = pick.includes(label) ? pick.filter((x) => x !== label) : pick.length >= MAX_CHART_TARGETS ? pick : [...pick, label]
    patchModel((mm) => ({ ...mm, state: { ...mm.state, targets: { ...(mm.state.targets as object), chart: next } } }))   // draw now
    send({ type: "action", name: "chart_targets", args: { labels: next } })                                              // Rhino saves it
  }
  const chart = (keys: string[], title: string) => {
    const cols: Col[] = keys.filter((k) => sel.some(([t]) => t.key === k)).map((k) => {
      const { segs, total } = boundarySegs(k, v, R, P, groupLabels)
      return { label: TCOL[k][0], sub: TCOL[k][1], segs, total: total == null ? null : sf(total, sfN),
        lines: sel.filter(([t]) => t.key === k).map(([t]) => ({ label: t.label, short: short(t.label), value: t.target,
          color: lineColor(k.startsWith("AC_") ? P.target_ac : P.target) })) }
    })
    if (!cols.length) return null
    const order = (g: Part) => { const i = groupLabels.indexOf(g.label); return i >= 0 ? i : g.label.startsWith("Contingency") ? 99 : 50 }
    const items = cols.flatMap((c) => c.segs.filter((g) => (g.value || 0) > 0)).sort((a, b) => order(a) - order(b))
    return (
      <div className="min-w-0">
        <h3 className="mb-1 text-sm font-medium">{title}</h3>
        <TargetColumnsChart cols={cols} unit="kgCO2e/m² GIA" title={title} />
        <Legend items={items} />
      </div>
    )
  }
  const up = chart(UPFRONT, "Upfront A1-A5 by element"), ac = chart(LIFECYCLE, "Embodied A-C by stage")
  return (
    <ChartCard title="Against targets" wide
      note="Each column is one reporting boundary, with that boundary's targets as dashed lines. Project figures include the PS Table 10 contingency (top segment); targets are bare thresholds (PS 4.10). Element segments are before contingency.">
      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs text-muted-foreground">Show up to {MAX_CHART_TARGETS}:</span>
        {([["Upfront", UPFRONT], ["Life cycle", LIFECYCLE]] as const).map(([g, keys], gi) => (
          <span key={g} className="contents">
            {gi > 0 && <span className="mx-1 h-5 w-px bg-border" aria-hidden />}
            <span className="mr-0.5 text-xs font-medium">{g}</span>
            {R.targets.map((t, i) => keys.includes(t.key as never) && (
              <button key={t.label} type="button" aria-pressed={pick.includes(t.label)} onClick={() => toggle(t.label)}
                title={`${BOUNDARY[t.key] || t.key}: ${o.verdicts[i]}`}
                className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                  pick.includes(t.label) ? "border-primary bg-accent text-accent-foreground" : "bg-card text-muted-foreground hover:bg-muted")}>
                <VerdictDot v={o.verdicts[i]} />{t.label}
              </button>
            ))}
          </span>
        ))}
      </div>
      {up || ac ? <div className={cn("grid gap-6", up && ac && "@3xl/main:grid-cols-[3fr_2fr]")}>{up}{ac}</div>
        : <p className="text-sm text-muted-foreground">Pick a target above to draw it.</p>}
      {sel.length > 0 && <TargetTable rows={sel} v={v} o={o} sfN={sfN} className="mt-4" />}
      <details className="group mt-3">
        <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-sm font-medium text-primary">
          <ChevronRight className="size-4 transition-transform group-open:rotate-90" />All {R.targets.length} targets
        </summary>
        <TargetTable rows={R.targets.map((t, i) => [t, i] as [Target, number])} v={v} o={o} sfN={sfN} className="mt-2" />
      </details>
    </ChartCard>
  )
}

function TargetTable({ rows, v, o, sfN, className }: { rows: [Target, number][]; v: ResOption["values"]; o: ResOption; sfN: number; className?: string }) {
  return (
    <div className={cn("overflow-x-auto rounded-md border", className)}>
      <table className="w-full min-w-max text-sm">
        <thead>
          <tr className="border-b bg-muted/60 text-xs text-muted-foreground">
            <th className="px-3 py-2 text-left font-medium">Target</th><th className="px-3 py-2 text-left font-medium">Boundary</th>
            <th className="px-3 py-2 text-right font-medium">Project</th><th className="px-3 py-2 text-right font-medium">Target</th>
            <th className="px-3 py-2 text-right font-medium">Margin</th><th className="px-3 py-2 text-left font-medium">Result</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map(([t, i]) => {
            const val = v[t.key], ok = typeof val === "number"
            return (
              <tr key={t.label}>
                <td className="px-3 py-1.5">{t.label}</td>
                <td className="px-3 py-1.5 text-muted-foreground">{BOUNDARY[t.key] || t.key}</td>
                <td className="num px-3 py-1.5 text-right">{ok ? fmt(sf(val as number, sfN)) : "–"}</td>
                <td className="num px-3 py-1.5 text-right">{fmt(t.target)}</td>
                <td className="num px-3 py-1.5 text-right">{ok ? fmt(t.target - sf(val as number, sfN)) : ""}</td>
                <td className="px-3 py-1.5"><Verdict v={o.verdicts[i]} /></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
