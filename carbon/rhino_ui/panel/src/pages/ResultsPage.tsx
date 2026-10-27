// Results: read back from the calculated workbook (the workbook stays the single source of the numbers).
// Drafted by an AI agent (Claude) - review before trusting.
import { ExternalLink, RefreshCw, Sheet } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Note, Notice, Section } from "@/components/blocks"
import { ChartCard, Tile, Verdict } from "@/components/chart-ui"
import { fmt, forDark, sf } from "@/lib/charts"
import { DonutChart, HBarChart, type BarRow } from "@/components/charts"
import { act } from "@/lib/bridge"
import type { Model, PageProps } from "@/lib/model"
import { n, palette, useDark, useSticky, type Palette, type ResOption, type Results } from "@/lib/results"
import { CalcStatus } from "@/pages/RunPage"
import { TargetsCard } from "@/pages/results/TargetsCard"
import { WholeLifeCard } from "@/pages/results/WholeLifeCard"
import { TrajectoryCard } from "@/pages/results/TrajectoryCard"

export function ResultsPage({ m }: PageProps) {
  const R = m.results as Results | null
  const dark = useDark()
  const [tab, setTab] = useSticky("results.tab", 0)
  const lastWb = (m.state.output as { last_workbook?: string }).last_workbook
  if (!R) {
    return (
      <Section title="No results yet">
        <CalcStatus m={m} />
        {!m.calc?.status && (
          <Note>{lastWb ? "The last workbook has not been calculated yet." : "Run the take-off and create the workbook on step 7; the results then appear here."}</Note>
        )}
        {lastWb && m.calc?.status !== "running" && (
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={() => act("calculate")}><Sheet />Calculate results</Button>
            <Button type="button" variant="outline" size="sm" onClick={() => act("open_workbook")}><ExternalLink />Open in Excel</Button>
          </div>
        )}
      </Section>
    )
  }
  const opts = R.options, sfN = (R.stage || 2) <= 2 ? 2 : 3
  const cur = tab >= opts.length ? 0 : tab
  const P = palette(m.branding as Record<string, unknown>)
  const lineColor = (c: string) => forDark(c, dark)
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Tabs value={String(cur)} onValueChange={(x) => setTab(Number(x))}>
          <TabsList>
            {opts.map((o, i) => <TabsTrigger key={o.k} value={String(i)}>{o.values.NAME || `Option ${o.k}`}</TabsTrigger>)}
            {opts.length > 1 && <TabsTrigger value="-1">Compare options</TabsTrigger>}
          </TabsList>
        </Tabs>
        <div className="ml-auto flex gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => act("open_workbook")}><ExternalLink />Open in Excel</Button>
          <Button type="button" variant="ghost" size="sm" disabled={m.calc?.status === "running"} onClick={() => act("calculate")}><RefreshCw />Recalculate</Button>
        </div>
      </div>
      <CalcStatus m={m} />
      {cur === -1
        ? <CompareView m={m} R={R} sfN={sfN} P={P} lineColor={lineColor} />
        : <OptionView m={m} R={R} o={opts[cur]} sfN={sfN} P={P} lineColor={lineColor} />}
      <Note>
        Results are read from the calculated workbook ({R.workbook}). Building-level figures are shown to {sfN} significant figures (PS 6.1.4);
        all figures include the PS Table 10 contingency unless stated. The workbook holds every assumption and breakdown.
      </Note>
    </div>
  )
}

type ViewProps = { m: Model; R: Results; sfN: number; P: Palette; lineColor: (c: string) => string }

function OptionView({ m, R, o, sfN, P, lineColor }: ViewProps & { o: ResOption }) {
  const v = o.values, S = (k: string) => fmt(sf(n(v, k), sfN))
  const op = n(v, "WLC_ND") != null && !!(n(v, "B6_ND") || n(v, "B7_ND"))
  const basis = ([["Modelled: project information", "B_MOD"], ["Modelled: assumed quantities", "B_ASM"], ["Benchmarked", "B_BM"],
    ["Site lumps (A5.1 / A5.2)", "B_SITE"], ["Contingency (PS Table 10)", "B_CONT"]] as const)
    .map(([label, k], i) => ({ label, value: n(v, k), color: P.basis[i % P.basis.length] }))
  const basisTotal = basis.reduce((a, b) => a + Math.max(0, b.value || 0), 0)
  const mc = [P.modules[0], P.modules[1], P.modules[2], P.b23[0], P.b23[1], P.modules[3], P.modules[4]]
  const mods: BarRow[] = ([["A1-A3 (product)", "M_A13"], ["A4 (transport)", "M_A4"], ["A5 (construction)", "M_A5"], ["B2 (maintenance)", "M_B2"],
    ["B3 (repair)", "M_B3"], ["B4 (replacement)", "M_B4"], ["C1-C4 (end of life)", "M_C"]] as const)
    .map(([label, k], i) => ({ label, value: n(v, k), color: mc[i] }))
  if (n(v, "M_D")) mods.push({ label: "D (memo, not in A-C)", value: n(v, "M_D"), color: P.module_d, sep: true, muted: true })
  const groups: BarRow[] = (m.group_labels as string[]).map((label, i) => ({ label, value: n(v, "E_" + i), color: P.groups[i % P.groups.length] }))
  groups.push({ label: "Contingency", value: n(v, "E_CONT"), color: P.cont })
  const upT = n(v, "UP_T")
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 @4xl/main:grid-cols-4">
        <Tile title="Upfront carbon A1-A5" value={S("UP_ALL")} unit="kgCO2e/m² GIA" sub={upT != null ? `${fmt(sf(upT, sfN))} tCO2e` : undefined} />
        <Tile title="Embodied carbon A-C" value={S("AC_ALL")} unit="kgCO2e/m² GIA" sub="incl. B2-B4, excl. B6/B7" />
        {op && <Tile title="Whole life, non-decarbonised" value={S("WLC_ND")} unit="kgCO2e/m² GIA" sub="A-C + B6 + B7" />}
        {op && <Tile title="Whole life, decarbonised" value={S("WLC_D")} unit="kgCO2e/m² GIA" sub="PS Table 15, FES grid" />}
      </div>
      {n(v, "QA_FLAGS") ? (
        <Notice tone="warn">{fmt(n(v, "QA_FLAGS"))} QA flag(s) open: check sheet O{o.k}_QA in the workbook before using these figures.</Notice>
      ) : null}
      <div className="grid grid-cols-1 gap-5 @3xl/main:grid-cols-2">
        {R.targets.length > 0 && <TargetsCard m={m} R={R} o={o} sfN={sfN} P={P} lineColor={lineColor} />}
        <ChartCard title="Basis of A1-A5"
          note="How much of the upfront figure rests on project information, on assumed quantities, on benchmarks for elements not yet designed, on site lumps and on the contingency.">
          <div className="flex flex-wrap items-center gap-5">
            <DonutChart parts={basis} center={fmt(sf(n(v, "UP_ALL"), sfN))} unit="kgCO2e/m²" title="basis of the A1-A5 figure" />
            <ul className="min-w-[14rem] flex-1 space-y-1.5 text-sm">
              {basis.map((b) => (
                <li key={b.label} className="flex items-baseline gap-2">
                  <span className="size-2.5 shrink-0 translate-y-px rounded-[3px]" style={{ background: b.color }} aria-hidden />
                  <span className="min-w-0 flex-1">{b.label}</span>
                  <span className="num whitespace-nowrap text-muted-foreground">{fmt(b.value)}<span className="ml-1.5 text-xs">{basisTotal ? fmt((100 * Math.max(0, b.value || 0)) / basisTotal) : 0}%</span></span>
                </li>
              ))}
            </ul>
          </div>
        </ChartCard>
        <ChartCard title="A1-A5 by element group" note="kgCO2e/m² GIA, before contingency; contingency shown as its own bar.">
          <HBarChart rows={groups} unit="kgCO2e/m²" title="A1-A5 by element group" />
        </ChartCard>
        {/* full width: the chart with its explanation beside it */}
        <ChartCard title="By life-cycle module" wide>
          <div className="grid items-start gap-5 @3xl/main:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
            <HBarChart rows={mods} unit="kgCO2e/m²" title="by life-cycle module" />
            <p className="max-w-[72ch] text-xs leading-relaxed text-muted-foreground">
              kgCO2e/m² GIA incl. contingency. B2 / B3: PS default allowances for the whole building (B2 = the greater of 10 kgCO2e/m² GIA and 1% of
              A1-A5{v.B2_BASIS ? `, here ${v.B2_BASIS}` : ""}; B3 = 25% of the non-MEP part of B2 + 10% of services A1-A3). B4 includes the end of life of
              the items replaced (PS 5.2.4); C1-C4 covers what is in place at the end. D: benefits beyond the system boundary (reuse, recycling, energy
              recovery), before contingency, reported separately and never netted off A-C.
            </p>
          </div>
        </ChartCard>
        <WholeLifeCard v={v} sfN={sfN} P={P} />
        <TrajectoryCard opts={[o]} R={R} sfN={sfN} P={P} lineColor={lineColor} />
      </div>
      {n(v, "BIO_STORED") ? (
        <Note>Biogenic carbon stored in products: {fmt(n(v, "BIO_STORED"))} kgCO2e/m² GIA (reported separately, not in A1-A5; released at end of life within A-C).</Note>
      ) : null}
    </div>
  )
}

function CompareView({ R, sfN, P, lineColor }: ViewProps) {
  const opts = R.options, names = opts.map((o) => String(o.values.NAME || `Option ${o.k}`))
  const rows = ([["Upfront A1-A5", "UP_ALL"], ["Embodied A-C", "AC_ALL"], ["Embodied A-C decarbonised", "AC_DEC"],
    ["Whole life, non-decarbonised", "WLC_ND"], ["Whole life, decarbonised", "WLC_D"], ["EUI (kWh/m²/yr)", "EUI"], ["QA flags open", "QA_FLAGS"]] as const)
    .filter(([, k]) => opts.some((o) => n(o.values, k) != null))
  return (
    <div className="space-y-5">
      <ChartCard title="Options side by side">
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full min-w-max text-sm">
            <thead>
              <tr className="border-b bg-muted/60 text-xs text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">kgCO2e/m² GIA</th>
                {names.map((nm) => <th key={nm} className="px-3 py-2 text-right font-semibold text-foreground">{nm}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map(([label, k]) => (
                <tr key={k}>
                  <td className="px-3 py-1.5">{label}</td>
                  {opts.map((o) => {
                    const x = n(o.values, k)
                    return <td key={o.k} className="num px-3 py-1.5 text-right">{x == null ? "–" : fmt(k === "QA_FLAGS" || k === "EUI" ? x : sf(x, sfN))}</td>
                  })}
                </tr>
              ))}
              {R.targets.map((t, i) => (
                <tr key={t.label}>
                  <td className="px-3 py-1.5 text-muted-foreground">{t.label} ({fmt(t.target)})</td>
                  {opts.map((o) => <td key={o.k} className="px-3 py-1.5 text-right"><Verdict v={o.verdicts[i]} /></td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>
      <div className="grid grid-cols-1 gap-5 @3xl/main:grid-cols-2">
        <TrajectoryCard opts={opts} R={R} sfN={sfN} P={P} lineColor={lineColor} />
        {([["Upfront A1-A5", "UP_ALL"], ["Embodied A-C", "AC_ALL"]] as const).map(([label, k]) => (
          <ChartCard key={k} title={label} note="kgCO2e/m² GIA incl. contingency.">
            <HBarChart rows={opts.map((o, i) => ({ label: names[i], value: n(o.values, k), color: P.project }))} unit="kgCO2e/m²" title={label} labelWidth={120} />
          </ChartCard>
        ))}
      </div>
    </div>
  )
}
