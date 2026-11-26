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
import { scopeOf, type Model, type PageProps, type Scope } from "@/lib/model"
import { baseKey, n, palette, useDark, useSticky, type Palette, type ResOption, type Results } from "@/lib/results"
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
  const sc = scopeOf(m), ed1 = R.rics_edition === 1
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
        ? <CompareView m={m} R={R} sfN={sfN} P={P} lineColor={lineColor} sc={sc} />
        : <OptionView m={m} R={R} o={opts[cur]} sfN={sfN} P={P} lineColor={lineColor} sc={sc} />}
      <Note>
        Results are read from the calculated workbook ({R.workbook}). Building-level figures are shown to {sfN} significant figures (PS 6.1.4);
        {ed1
          ? "headline figures are on the RICS PS 1st edition (2017) basis - no contingency, pre-construction demolition reported separately; breakdowns include the PS Table 10 contingency unless stated. "
          : "all figures include the PS Table 10 contingency unless stated. "}
        Targets are judged on their own scheme's edition. The workbook holds every assumption and breakdown.
      </Note>
    </div>
  )
}

type ViewProps = { m: Model; R: Results; sfN: number; P: Palette; lineColor: (c: string) => string; sc: Scope }

/** Targets on a boundary the scope reports: A1-A5 boundaries for upfront, A-C boundaries for life cycle / whole life. */
export const targetInScope = (key: string, sc: Scope) => (baseKey(key).startsWith("UP_") ? sc.up : sc.ac)

/** The headline key on the workbook's reporting method (D21): the 1st edition reads the V1_ figures where the workbook has them. */
export const headKey = (R: Results, v: ResOption["values"], key: "UP_ALL" | "AC_ALL" | "WLC_ND") =>
  R.rics_edition === 1 && typeof v["V1_" + key] !== "undefined" ? "V1_" + key : key

function OptionView({ m, R, o, sfN, P, lineColor, sc }: ViewProps & { o: ResOption }) {
  const v = o.values, S = (k: string) => fmt(sf(n(v, k), sfN))
  const op = sc.wlc && n(v, "WLC_ND") != null && !!(n(v, "B6_ND") || n(v, "B7_ND"))
  const basis = ([["Modelled: project information", "B_MOD"], ["Modelled: assumed quantities", "B_ASM"], ["Benchmarked", "B_BM"],
    ["Site lumps (A5.1 / A5.2)", "B_SITE"], ["Contingency (PS Table 10)", "B_CONT"]] as const)
    .map(([label, k], i) => ({ label, value: n(v, k), color: P.basis[i % P.basis.length] }))
  const basisTotal = basis.reduce((a, b) => a + Math.max(0, b.value || 0), 0)
  const mc = [P.modules[0], P.modules[1], P.modules[2], P.b23[0], P.b23[1], P.modules[3], P.modules[4]]
  const mods: BarRow[] = ([["A1-A3 (product)", "M_A13"], ["A4 (transport)", "M_A4"], ["A5 (construction)", "M_A5"], ["B2 (maintenance)", "M_B2"],
    ["B3 (repair)", "M_B3"], ["B4 (replacement)", "M_B4"], ["C1-C4 (end of life)", "M_C"]] as const)
    .map(([label, k], i) => ({ label, value: n(v, k), color: mc[i] }))
  if (!sc.ac) mods.splice(3)                                    // upfront only: A1-A3, A4, A5
  if (n(v, "M_D")) mods.push({ label: "D (memo, not in A-C)", value: n(v, "M_D"), color: P.module_d, sep: true, muted: true })
  const groups: BarRow[] = (m.group_labels as string[]).map((label, i) => ({ label, value: n(v, "E_" + i), color: P.groups[i % P.groups.length] }))
  groups.push({ label: "Contingency", value: n(v, "E_CONT"), color: P.cont })
  const hUp = headKey(R, v, "UP_ALL"), ed1 = hUp !== "UP_ALL", gia = n(v, "GIA"), demo = n(v, "DEMO")
  const upT = ed1 ? (n(v, hUp) != null && gia ? (n(v, hUp) as number) * gia / 1000 : undefined) : n(v, "UP_T")
  const upSub = [upT != null ? `${fmt(sf(upT, sfN))} tCO2e` : "", ed1 && demo ? `demolition ${fmt(sf(demo, sfN))} separate` : ""].filter(Boolean).join(" · ")
  return (
    <div className="space-y-5">
      {ed1 && <Note>Headline on the RICS PS 1st edition (2017) basis: no contingency; pre-construction demolition reported separately; B3 = 25% of B2.</Note>}
      <div className="grid grid-cols-2 gap-3 @4xl/main:grid-cols-4">
        {sc.up && <Tile title="Upfront carbon A1-A5" value={S(hUp)} unit="kgCO2e/m² GIA" sub={upSub || undefined} />}
        {sc.emb && <Tile title="Life cycle embodied carbon A-C" value={S(headKey(R, v, "AC_ALL"))} unit="kgCO2e/m² GIA" sub="incl. B2-B4, excl. B6/B7" />}
        {op && <Tile title="Whole life, non-decarbonised" value={S(headKey(R, v, "WLC_ND"))} unit="kgCO2e/m² GIA" sub="A-C + B6 + B7" />}
        {op && <Tile title="Whole life, decarbonised" value={S("WLC_D")} unit="kgCO2e/m² GIA" sub={ed1 ? "PS Table 15, FES grid · 2nd ed. basis" : "PS Table 15, FES grid"} />}
      </div>
      {n(v, "QA_FLAGS") ? (
        <Notice tone="warn">{fmt(n(v, "QA_FLAGS"))} QA flag(s) open: check sheet O{o.k}_QA in the workbook before using these figures.</Notice>
      ) : null}
      <div className="grid grid-cols-1 gap-5 @3xl/main:grid-cols-2">
        {R.targets.some((t) => targetInScope(t.key, sc)) && <TargetsCard m={m} R={R} o={o} sfN={sfN} P={P} lineColor={lineColor} sc={sc} />}
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
        {sc.ac && <WholeLifeCard v={v} sfN={sfN} P={P} op={op} />}
        {sc.ac && <TrajectoryCard opts={[o]} R={R} sfN={sfN} P={P} lineColor={lineColor} wlc={sc.wlc} />}
      </div>
      {n(v, "BIO_STORED") ? (
        <Note>Biogenic carbon stored in products: {fmt(n(v, "BIO_STORED"))} kgCO2e/m² GIA (reported separately, not in A1-A5; released at end of life within A-C).</Note>
      ) : null}
    </div>
  )
}

function CompareView({ R, sfN, P, lineColor, sc }: ViewProps) {
  const opts = R.options, names = opts.map((o) => String(o.values.NAME || `Option ${o.k}`))
  const v1 = R.rics_edition === 1 && opts.some((o) => o.values.V1_UP_ALL !== undefined)
  const want: Record<string, boolean> = { UP_ALL: sc.up, AC_ALL: sc.emb, V1_UP_ALL: sc.up, V1_AC_ALL: sc.emb, V1_WLC_ND: sc.wlc, DEMO: v1,
    AC_DEC: sc.wlc, WLC_ND: sc.wlc, WLC_D: sc.wlc, EUI: sc.wlc, QA_FLAGS: true }
  const rows = ((v1
    ? [["Upfront A1-A5 · PS 1st ed.", "V1_UP_ALL"], ["Life cycle embodied A-C · PS 1st ed.", "V1_AC_ALL"], ["Pre-construction demolition (separate)", "DEMO"],
      ["Whole life, non-decarbonised · PS 1st ed.", "V1_WLC_ND"], ["Upfront A1-A5 · PS 2nd ed.", "UP_ALL"], ["Life cycle embodied A-C · PS 2nd ed.", "AC_ALL"]]
    : [["Upfront A1-A5", "UP_ALL"], ["Life cycle embodied A-C", "AC_ALL"]]).concat([["Embodied A-C decarbonised", "AC_DEC"],
    [v1 ? "Whole life, non-decarbonised · PS 2nd ed." : "Whole life, non-decarbonised", "WLC_ND"], ["Whole life, decarbonised", "WLC_D"],
    ["EUI (kWh/m²/yr)", "EUI"], ["QA flags open", "QA_FLAGS"]]) as [string, string][])
    .filter(([, k]) => want[k] && opts.some((o) => n(o.values, k) != null))
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
              {R.targets.map((t, i) => targetInScope(t.key, sc) && (
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
        {sc.ac && <TrajectoryCard opts={opts} R={R} sfN={sfN} P={P} lineColor={lineColor} wlc={sc.wlc} />}
        {([["Upfront A1-A5", v1 ? "V1_UP_ALL" : "UP_ALL", sc.up], ["Life cycle embodied A-C", v1 ? "V1_AC_ALL" : "AC_ALL", sc.ac]] as const).filter(([, , on]) => on).map(([label, k]) => (
          <ChartCard key={k} title={label} note={v1 ? "kgCO2e/m² GIA, RICS PS 1st ed. basis (no contingency, demolition separate)." : "kgCO2e/m² GIA incl. contingency."}>
            <HBarChart rows={opts.map((o, i) => ({ label: names[i], value: n(o.values, k), color: P.project }))} unit="kgCO2e/m²" title={label} labelWidth={120} />
          </ChartCard>
        ))}
      </div>
    </div>
  )
}
