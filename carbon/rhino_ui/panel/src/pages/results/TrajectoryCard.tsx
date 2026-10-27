// Carbon over the reference study period: one option (with replacement events) or every option overlaid.
// Drafted by an AI agent (Claude) - review before trusting.
import { ChartCard, LineLegend, Svg } from "@/components/chart-ui"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Toggle } from "@/components/ui/toggle"
import { fmt, lineChart, sf, type Event, type Series } from "@/lib/charts"
import { n, OPTION_COLOURS, useSticky, type Palette, type ResOption, type Results, type Traj } from "@/lib/results"

const EVENT_NAME: Record<string, string> = { Substructure: "Substructure", Superstructure: "Partitions", Facade: "Façade",
  "Internal finishes": "Internal fit-out", FFE: "FF&E", "Services/MEP": "MEP", "External works": "External works", Site: "Site" }
const GROUPS = ["Substructure", "Superstructure", "Facade", "Internal finishes", "FFE", "Services/MEP", "External works", "Site"]
const DX = 4                // module D drawn this many years beyond the RSP

/** Replacement years worth marking: at least 1.5% of the final embodied figure; named by the largest groups. */
function trajEvents(tr: Traj, R: Results, gia: number): Event[] {
  const k = ((1 + (R.cont || 0)) * 1000) / gia, fin = tr.emb_nd[tr.emb_nd.length - 1] || 1, ev: Event[] = []
  tr.b4.forEach((row, i) => {
    const tot = row.reduce((a, x) => a + x, 0) * k
    if (!i || tot < 0.015 * fin) return
    const ranked = row.map((x, j) => [x, GROUPS[j]] as [number, string]).filter(([x]) => x > 0).sort((a, b) => b[0] - a[0])
    const names = ranked.filter(([x], j) => j === 0 || x >= 0.3 * ranked[0][0]).slice(0, 2).map(([, g]) => EVENT_NAME[g] || g)
    ev.push({ x: tr.year[i], label: names.join(" + "), title: `${tr.year[i]}: replacements ${fmt(tot)} kgCO2e/m²` })
  })
  return ev
}

export function TrajectoryCard({ opts, R, sfN, P, lineColor }: {
  opts: ResOption[]; R: Results; sfN: number; P: Palette; lineColor: (c: string) => string
}) {
  const [scopePick, setScope] = useSticky<"wlc" | "emb">("traj.scope", "wlc")
  const [bioOn, setBio] = useSticky("traj.bio", false)
  const [dOn, setD] = useSticky("traj.d", false)
  const have = opts.filter((o) => o.traj && o.traj.t && o.traj.t.length) as (ResOption & { traj: Traj })[]
  if (!have.length) return null
  const multi = opts.length > 1
  const anyOp = have.some((o) => n(o.values, "WLC_ND") != null && (n(o.values, "B6_ND") || n(o.values, "B7_ND")))
  const scope = anyOp ? scopePick : "emb"
  const bioOk = have.every((o) => Array.isArray(o.traj.bio)), anyBio = bioOk && have.some((o) => o.traj.bio!.some((x) => Math.abs(x) > 1e-9))
  const anyD = have.some((o) => n(o.values, "M_D")), showBio = bioOn && anyBio, showD = dOn && anyD
  const series: Series[] = [], items: { label: string; color: string; dash?: boolean; dot?: boolean }[] = []
  const grey = lineColor("#777777")
  have.forEach((o, i) => {
    const tr = o.traj, v = o.values, nm = v.NAME || "Option " + o.k
    const col = lineColor(multi ? OPTION_COLOURS[i % OPTION_COLOURS.length] : P.project)
    const add = (ys: number[]) => (showBio ? ys.map((y, j) => (y == null ? y : y + (tr.bio![j] || 0))) : ys)
    const nd = add(scope === "wlc" ? tr.wlc_nd : tr.emb_nd), d = add(scope === "wlc" ? tr.wlc_d : tr.emb_d)
    const pre = multi ? nm + " - " : "", last = tr.year.length - 1, xe = tr.year[last], MD = n(v, "M_D")
    series.push({ label: pre + "non-decarbonised", color: col, x: tr.year, y: nd, endValue: sf(nd[last], sfN) })
    series.push({ label: pre + "decarbonised", color: col, dash: true, x: tr.year, y: d, endValue: sf(d[last], sfN) })
    if (showD && MD) {
      series.push({ label: pre + "with module D (memo), non-decarbonised", color: col, dot: true, x: [xe, xe + DX], y: [nd[last], nd[last] + MD], endValue: sf(nd[last] + MD, sfN), end: !multi })
      series.push({ label: pre + "with module D (memo), decarbonised", color: col, dot: true, x: [xe, xe + DX], y: [d[last], d[last] + (n(v, "D_DEC") ?? MD)], end: false })
    }
    if (multi) items.push({ label: String(nm), color: col })
    else items.push({ label: "non-decarbonised", color: col }, { label: "decarbonised (PS Table 15, FES grid)", color: col, dash: true })
  })
  if (multi) items.push({ label: "solid: non-decarbonised", color: grey }, { label: "dashed: decarbonised (PS Table 15, FES grid)", color: grey, dash: true })
  if (showD) items.push({ label: "dotted: + module D beyond the RSP (memo, not netted)", color: multi ? grey : lineColor(P.project), dot: true })
  const tr0 = have[0].traj, first = tr0.year[0], rspYears = tr0.year[tr0.year.length - 1] - first
  const events = multi ? [] : trajEvents(tr0, R, n(have[0].values, "GIA") || 1)
  if (showD) events.push({ x: tr0.year[tr0.year.length - 1] + DX, label: "D", title: "Module D: benefits beyond the system boundary, reported separately (not part of A-C)" })

  const controls = (
    <>
      {anyOp && (
        <ToggleGroup type="single" variant="outline" size="sm" value={scope} onValueChange={(x) => x && setScope(x as "wlc" | "emb")} aria-label="Scope">
          <ToggleGroupItem value="wlc" className="px-3 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">Whole life (A-C + B6-B7)</ToggleGroupItem>
          <ToggleGroupItem value="emb" className="px-3 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">Embodied A-C</ToggleGroupItem>
        </ToggleGroup>
      )}
      {anyBio && (
        <Toggle variant="outline" size="sm" pressed={showBio} onPressedChange={setBio} className="px-3 data-[state=on]:bg-accent"
          title="Add the carbon stored in bio-based products at year 0 and its release at the end of the RSP (nets to zero)">Biogenic (-1/+1)</Toggle>
      )}
      {anyD && (
        <Toggle variant="outline" size="sm" pressed={showD} onPressedChange={setD} className="px-3 data-[state=on]:bg-accent"
          title="Show module D beyond the RSP (memo, not netted)">Module D</Toggle>
      )}
    </>
  )

  return (
    <ChartCard title={multi ? "Options over the reference study period" : "Over the reference study period"} wide aside={controls}
      note={<>
        Year 0 = practical completion ({first}); year 1 = the first year of operation. A1-A5 at year 0; each replacement in its year (modelled
        items at their own life, benchmarked groups at the trajectory lives on the workbook's Project sheet) with the end of life of what it
        replaces; B2 / B3 spread evenly; B6 / B7 each year (decarbonised: that year's FES factor); C1-C4 of what is left at the end. Contingency
        on embodied carbon. The end points equal the headline figures.{" "}
        {showBio ? `Biogenic shown (-1/+1): the carbon stored in bio-based products is taken off at year 0 and released at the end of the RSP, as the PS reports it (A1-A3 / C3-C4). This is an accounting convention, not a forecast of when the carbon returns to the air; it nets to zero by year ${rspYears}. `
          : anyBio ? "Biogenic carbon is left out, as in the headline A1-A5 (it nets to zero over A-C under -1/+1); switch it on to see it. " : ""}
        {!bioOk && "This workbook was made before biogenic carbon had its own column: its lines include it. Create the workbook again. "}
        {showD && "Module D (dotted, beyond the RSP) is a memo: benefits beyond the system boundary, before contingency, never netted off A-C."}
      </>}>
      <Svg html={lineChart(series, events, { unit: "kgCO2e/m² GIA, cumulative", title: "carbon over the reference study period", x2: (x) => "yr " + (x - first) })} />
      <LineLegend items={items} />
      {multi && (
        <div className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-3">
          {have.map((o, i) => {
            const v = o.values, c = lineColor(OPTION_COLOURS[i % OPTION_COLOURS.length])
            return (
              <div key={o.k} className="rounded-md border-2 bg-card px-3 py-2.5" style={{ borderColor: c }}>
                <div className="text-sm font-semibold" style={{ color: c }}>{v.NAME || `Option ${o.k}`}</div>
                <dl className="num mt-1.5 grid gap-1 text-sm">
                  <div><dt className="text-xs text-muted-foreground">Upfront A1-A5</dt><dd className="font-semibold">{fmt(sf(n(v, "UP_ALL"), sfN))}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Embodied A-C</dt><dd className="font-semibold">{fmt(sf(n(v, "AC_ALL"), sfN))}</dd></div>
                  {n(v, "WLC_ND") != null && (
                    <div><dt className="text-xs text-muted-foreground">Whole life A-C + B6-B7</dt>
                      <dd><span className="font-semibold">{fmt(sf(n(v, "WLC_ND"), sfN))}</span> <span className="text-xs text-muted-foreground">/ {fmt(sf(n(v, "WLC_D"), sfN))} decarb.</span></dd></div>
                  )}
                </dl>
                <div className="mt-1 text-xs text-muted-foreground">kgCO2e/m² GIA</div>
              </div>
            )
          })}
        </div>
      )}
    </ChartCard>
  )
}
