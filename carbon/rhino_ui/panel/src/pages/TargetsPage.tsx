// Step 6: targets, UKNZCBS shares, scenario, operational energy and water, output folder.
// Drafted by an AI agent (Claude) - review before trusting.
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { FieldGrid, Note, Section } from "@/components/blocks"
import { ChoiceInput, FormField, NumField, PathInput, TextInput, idOf } from "@/components/form"
import { setValue } from "@/lib/bridge"
import type { PageProps } from "@/lib/model"

type Targets = {
  show: Record<string, boolean>
  sc_share: Record<string, number | null>
  catb_allowance: number | null
  scenario: string
  budget_target: string
}
type Operational = { route: string; op_year: number | null; dh_factor: number | null }

const SHOW: [string, string][] = [
  ["UKNZCBS", "UKNZCBS upfront limits (offices: shell & core limit)"],
  ["LETI", "LETI bands"],
  ["RIBA", "RIBA 2030 Climate Challenge"],
  ["GLA", "GLA London Plan Guidance"],
]

export function TargetsPage({ m }: PageProps) {
  const t = m.state.targets as Targets
  const op = m.state.operational as Operational
  const L = m.lists as Record<string, unknown>
  const routes = L.op_routes as string[]
  const fields = L.op_fields as [string, string][]
  const route = routes.includes(op.route) ? op.route : String(op.route || "").startsWith("Indicative") ? routes[1] : routes[2]
  const inc = m.state.options.map((o, i) => [o, i] as const).filter(([o]) => o.include)
  const anyOp = inc.some(([o]) => Object.values((o.operational as Record<string, unknown>) || {}).some((v) => v != null && v !== ""))
  const eng = route.startsWith("Engineer")

  return (
    <div className="space-y-8">
      <Section title="Targets to compare against" lead="Shown on the Results page and the workbook Dashboard.">
        <div className="grid gap-3 @2xl/main:grid-cols-2">
          {SHOW.map(([k, label]) => (
            <div key={k} className="flex items-center gap-2.5">
              <Checkbox id={idOf(["targets", "show", k])} checked={!!t.show[k]}
                onCheckedChange={(v) => setValue(["targets", "show", k], v === true, "bool")} />
              <Label htmlFor={idOf(["targets", "show", k])} className="font-normal">{label}</Label>
            </div>
          ))}
        </div>
      </Section>

      <Section title="UKNZCBS offices"
        lead="The share of each element group that is shell & core. The rest counts as Cat A and is taken off A1-A5 (excl. external works) for the UKNZCBS offices shell & core limit only (5.1.6.2).">
        <FieldGrid>
          <NumField path={["targets", "sc_share", "finishes"]} value={t.sc_share.finishes} kind="pct" label="Shell & core share: finishes (3)" />
          <NumField path={["targets", "sc_share", "ffe"]} value={t.sc_share.ffe} kind="pct" label="Shell & core share: FF&E (4)" />
          <NumField path={["targets", "sc_share", "services"]} value={t.sc_share.services} kind="pct" label="Shell & core share: services (5)" />
        </FieldGrid>
        <Note>
          100% takes nothing off: the strict default, which overstates the shell & core figure if the design includes Cat A. Example: services
          60% takes 40% of services off. Headline figures, LETI, RIBA, GLA, the UKNZCBS whole-building limit and other uses are not affected.
        </Note>
        <FieldGrid className="mt-5">
          <NumField path={["targets", "catb_allowance"]} value={t.catb_allowance} label="Cat B + loose FF&E (kgCO2e/m²)"
            hint="Added to the whole building for the UKNZCBS whole-building limit. Blank: that limit is not assessed." />
        </FieldGrid>
      </Section>

      <Section title="Scenario and budget">
        <FieldGrid>
          <FormField label="Elements not yet designed: scenario" htmlFor={idOf(["targets", "scenario"])}>
            <ChoiceInput path={["targets", "scenario"]} value={t.scenario} options={L.scenarios as string[]} />
          </FormField>
          <FormField label="Carbon budget against" htmlFor={idOf(["targets", "budget_target"])}>
            <ChoiceInput path={["targets", "budget_target"]} value={t.budget_target} options={L.budgets as string[]} />
          </FormField>
        </FieldGrid>
      </Section>

      <Section title="Operational energy and water" code="B6, B7"
        lead="Whole life carbon needs a predictive energy model (CIBSE TM54 or equivalent, never Part L). Without one, the Indicative basis uses each option's EUI estimate, else the UKNZCBS limit, × GIA (all electric).">
        <FieldGrid>
          <FormField label="Basis" htmlFor={idOf(["operational", "route"])} className="@md/main:col-span-2">
            <ChoiceInput path={["operational", "route"]} value={route} options={routes} />
          </FormField>
          <NumField path={["operational", "op_year"]} value={op.op_year} kind="int" label="First year of operation" />
          <NumField path={["operational", "dh_factor"]} value={op.dh_factor || null} kind="num0" label="District heat factor (kgCO2e/kWh)" />
        </FieldGrid>

        {(route !== "Not assessed" || anyOp) && (
          <div className="mt-5 overflow-x-auto rounded-lg border bg-card">
            <table className="w-full min-w-max text-sm">
              <thead>
                <tr className="border-b bg-muted/60 text-xs text-muted-foreground">
                  <th scope="col" className="px-3 py-2 text-left font-medium">Per year</th>
                  {inc.map(([o]) => <th key={o.name} scope="col" className="px-2 py-2 text-left font-semibold text-foreground">{o.name}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y">
                {fields.map(([k, label]) => {
                  const req = eng && ["elec", "gas", "dh"].includes(k)
                  return (
                    <tr key={k}>
                      <th scope="row" className="px-3 py-1.5 text-left font-normal whitespace-nowrap">
                        {label}{req && <span className="text-destructive">*</span>}
                      </th>
                      {inc.map(([o, i]) => {
                        const v = ((o.operational as Record<string, number | null>) || {})[k]
                        return (
                          <td key={i} className="px-2 py-1.5">
                            <TextInput path={["options", i, "operational", k]} kind="num" numeric className="w-32" aria-label={`${o.name}: ${label}`}
                              value={v == null ? "" : v.toLocaleString("en-GB", { maximumFractionDigits: 2 })} />
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        {(route !== "Not assessed" || anyOp) && (
          <Note>
            {eng && <span className="text-destructive">Engineer basis: at least one of grid electricity, gas or district heat for every option. </span>}
            Engineer basis: kWh from the energy model (TM54 mid-range). Indicative basis: only the EUI row is used (blank: UKNZCBS limit). Water
            from the public health engineer; blank: occupancy × RIBA 2025 target. PV used on site counts in the EUI at no carbon; PV exported is
            reported in D2.
          </Note>
        )}
      </Section>

      <Section title="Where to save">
        <FormField label="Output folder" required htmlFor={idOf(["output", "folder"])}>
          <PathInput path={["output", "folder"]} value={m.state.output.folder} action="pick_folder" />
        </FormField>
        <Note>
          Take-off exports go to a "takeoff" folder inside it, and the workbook is saved there too. Everything set here is written into the
          workbook; nothing has to be typed in Excel.
        </Note>
      </Section>
    </div>
  )
}
