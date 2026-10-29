// Step 2: area schedule, typical floor plan and the detailed model. Drafted by an AI agent (Claude) - review before trusting.
import { RefreshCw, ScanLine } from "lucide-react"
import { Button } from "@/components/ui/button"
import { FieldGrid, Note, Notice, Section } from "@/components/blocks"
import { Choice, ChoiceInput, FormField, PathInput, idOf } from "@/components/form"
import { act } from "@/lib/bridge"
import type { PageProps } from "@/lib/model"
import { ModelSection } from "./ModelSection"

export function DrawingsPage({ m }: PageProps) {
  const s = m.state.schedule, pl = m.state.plan, L = m.lists
  const tone = m.schedule.level === "warn" ? "warn" : m.schedule.level === "good" ? "good" : "note"
  const layers: [string, string][] = [["", "(none)"], ...L.all_layers.map((x) => [x, x] as [string, string])]
  return (
    <div className="space-y-8">
      <Section title="Area schedule"
        lead="Excel file with levels, GEA and GIA; AOD, floor-to-floor, NIA and use are read when present. Without a schedule, levels come from the massing and the storey heights.">
        <div className="grid grid-cols-1 gap-x-5 gap-y-4 @2xl/main:grid-cols-[minmax(0,1fr)_14rem]">
          <FormField label="Schedule file" htmlFor={idOf(["schedule", "path"])}>
            <PathInput path={["schedule", "path"]} value={s.path} action="pick_schedule" placeholder="No schedule chosen" />
          </FormField>
          <FormField label="Sheet" htmlFor={idOf(["schedule", "sheet"])}>
            <ChoiceInput path={["schedule", "sheet"]} value={s.sheet} options={L.sheets.length ? L.sheets : [""]} disabled={!L.sheets.length} />
          </FormField>
        </div>
        <Notice tone={tone}>{m.schedule.text}</Notice>
      </Section>

      <Section title="Typical floor plan" lead="Cores, columns and stairs for the structure take-off. Without a plan, the office defaults are used and the rows are tagged [ASSUMED] in the workbook.">
        <FieldGrid>
          <FormField label="Read the plan from">
            <Choice value={pl.route} options={L.plan_routes} aria-label="Read the plan from" onChange={(v) => act("plan_route", { route: v })} />
          </FormField>
        </FieldGrid>

        {pl.route === "pdf" && (
          <div className="mt-4">
            <FormField label="Plan extract (.json)" htmlFor={idOf(["plan", "pdf_json"])}
              hint="Output of the plan extractor (WLCA_plan_extract). Check its overlay image before using it.">
              <PathInput path={["plan", "pdf_json"]} value={pl.pdf_json} action="pick_plan_json" />
            </FormField>
          </div>
        )}

        {pl.route === "rhino" && (
          <>
            <Note className="mt-4">
              Import or paste the typical floor plan (DWG, DGN or .3dm linework) into this model at true scale; it can sit anywhere.
              The layers fill themselves from the office layer names and the shapes on each layer. Change one only if it is wrong.
              Walls and columns may share a layer.
            </Note>
            <FieldGrid className="mt-4">
              {([["walls_layer", "Core walls"], ["columns_layer", "Columns"], ["stairs_layer", "Stairs"]] as const).map(([k, label]) => (
                <FormField key={k} label={label} htmlFor={idOf(["plan", k])}>
                  <ChoiceInput path={["plan", k]} value={pl[k] || ""} options={layers} />
                </FormField>
              ))}
            </FieldGrid>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => act("find_plan_layers")}><RefreshCw />Find layers again</Button>
              <Button type="button" size="sm" onClick={() => act("read_plan")}><ScanLine />Read plan</Button>
            </div>
            <PlanSummary lines={pl.summary || []} />
          </>
        )}
      </Section>

      <ModelSection m={m} />
    </div>
  )
}

/** What the plan reader found, in one block; anything it could not find as a warning of its own. */
function PlanSummary({ lines }: { lines: string[] }) {
  const warn = (l: string) => /^(No |Units)/.test(l)
  const found = lines.filter((l) => !warn(l))
  return (
    <>
      {found.length > 0 && <Notice tone="good">{found.join("\n")}</Notice>}
      {lines.filter(warn).map((l, i) => <Notice key={i} tone="warn">{l}</Notice>)}
    </>
  )
}
