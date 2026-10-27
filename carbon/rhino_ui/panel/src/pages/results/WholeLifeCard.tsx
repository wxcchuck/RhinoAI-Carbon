// "Whole life by stage": stacked columns per grid scenario, module D apart, and the table.
// Drafted by an AI agent (Claude) - review before trusting.
import { ChartCard, Legend } from "@/components/chart-ui"
import { StackColumnsChart } from "@/components/charts-rich"
import { fmt, sf, type StackCol } from "@/lib/charts"
import { n, type Palette, type Values } from "@/lib/results"

export function WholeLifeCard({ v, sfN, P }: { v: Values; sfN: number; P: Palette }) {
  if (n(v, "AC_ALL") == null) return null
  const WLC_ND = n(v, "WLC_ND"), op = WLC_ND != null && !!(n(v, "B6_ND") || n(v, "B7_ND"))
  const stored = n(v, "BIO_STORED") || 0, up = n(v, "UP_ALL") || 0, MD = n(v, "M_D")
  const col = (label: string, sub: string, ac: number, b6: number, b7: number, total: number): StackCol => ({
    label, sub, total: sf(total, sfN), totalLabel: "Net ",
    segs: [
      { label: "Upfront A1-A5", short: "A1-A5", value: up, color: P.stages[0] },
      { label: "In-use & EoL B-C", short: "B-C", value: ac - up - stored, color: P.stages[1] },
      { label: "Operational B6-B7", short: "B6-B7", value: op ? b6 + b7 : 0, color: P.stages[2], ink: "#3a2e00" },
      { label: "Sequestered A1-A3", short: "Sequestered", value: stored, color: P.stages[3] },
    ],
  })
  const g = (k: string) => n(v, k) || 0
  const cols: StackCol[] = op
    ? [col("Non-decarbonised", "today's factors", g("AC_ALL"), g("B6_ND"), g("B7_ND"), g("WLC_ND")),
       col("Decarbonised", "PS Table 15 · FES grid", g("AC_DEC"), g("B6_D"), g("B7_D"), g("WLC_D"))]
    : [col("Embodied A-C", "operational not assessed", g("AC_ALL"), 0, 0, g("AC_ALL"))]
  cols.forEach((c) => c.segs.forEach((s) => { s.text = sf(s.value, sfN) }))       // stage figures to the reporting precision
  const items = cols[0].segs.filter((s) => s.value).map((s) => ({ label: s.label, color: s.color }))
  if (MD) {                                                                        // module D: its own column, never stacked on A-C
    cols.push({ label: "Module D", sub: "memo · not netted off A-C", weight: 0.55, total: null,
      segs: [{ label: "Module D (beyond the system boundary)", short: "D", value: MD, text: sf(MD, sfN), color: P.module_d }] })
    items.push({ label: "Module D (memo)", color: P.module_d })
  }
  const S = (k: string) => fmt(sf(n(v, k), sfN))
  return (
    <ChartCard title="Whole life by stage" wide
      note={<>kgCO2e/m² GIA over the RSP, incl. contingency on embodied carbon. B-C includes B2-B4, C1-C4 and the biogenic carbon released at end of
        life; the carbon stored in bio-based products (A1-A3) is shown below the line (-1/+1, so it nets to zero over A-C). Module D, where there
        is any, is its own column: benefits beyond the system boundary, before contingency, reported separately as the PS requires.{" "}
        {op ? "Both grid scenarios as the PS requires (4.11.4)." : "B6 / B7 not assessed: set the operational basis on step 6."}</>}>
      <div className="grid gap-6 @3xl/main:grid-cols-[3fr_2fr]">
        <div className="min-w-0">
          <StackColumnsChart cols={cols} unit="kgCO2e/m² GIA" title="whole life carbon by stage" />
          <Legend items={items} />
        </div>
        {op && (
          <div className="min-w-0">
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/60 text-xs text-muted-foreground">
                    <th className="px-3 py-2 text-left font-medium">kgCO2e/m² GIA over the RSP</th>
                    <th className="px-3 py-2 text-right font-medium">Non-decarb.</th><th className="px-3 py-2 text-right font-medium">Decarb.</th>
                  </tr>
                </thead>
                <tbody className="num divide-y">
                  <tr><td className="px-3 py-1.5">Upfront A1-A5</td><td className="px-3 py-1.5 text-right">{S("UP_ALL")}</td><td className="px-3 py-1.5 text-right">{S("UP_ALL")}</td></tr>
                  <tr><td className="px-3 py-1.5">Embodied A-C (incl. B2-B4, C1-C4, biogenic)</td><td className="px-3 py-1.5 text-right">{S("AC_ALL")}</td><td className="px-3 py-1.5 text-right">{S("AC_DEC")}</td></tr>
                  <tr><td className="px-3 py-1.5">B6 operational energy</td><td className="px-3 py-1.5 text-right">{S("B6_ND")}</td><td className="px-3 py-1.5 text-right">{S("B6_D")}</td></tr>
                  <tr><td className="px-3 py-1.5">B7 operational water</td><td className="px-3 py-1.5 text-right">{fmt(n(v, "B7_ND"), 1)}</td><td className="px-3 py-1.5 text-right">{fmt(n(v, "B7_D"), 1)}</td></tr>
                  <tr className="font-semibold"><td className="px-3 py-1.5">Whole life A-C + B6 + B7</td><td className="px-3 py-1.5 text-right">{S("WLC_ND")}</td><td className="px-3 py-1.5 text-right">{S("WLC_D")}</td></tr>
                  {MD ? (
                    <tr className="text-muted-foreground"><td className="px-3 py-1.5">Module D (memo, not netted)</td><td className="px-3 py-1.5 text-right">{S("M_D")}</td>
                      <td className="px-3 py-1.5 text-right">{fmt(sf(n(v, "D_DEC") ?? MD, sfN))}</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              {String(v.OP_STATUS || "")}
              {n(v, "EUI") != null && <> EUI {fmt(n(v, "EUI"))} kWh/m²/yr{n(v, "EUI_LIM") ? ` (UKNZCBS limit ${fmt(n(v, "EUI_LIM"))})` : ""}.</>}
            </p>
          </div>
        )}
      </div>
    </ChartCard>
  )
}
