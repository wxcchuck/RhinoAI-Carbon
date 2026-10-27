// Step 1: project and design options. Drafted by an AI agent (Claude) - review before trusting.
import { CopyPlus, FolderOpen, Plus, Trash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { FieldGrid, Note, Section } from "@/components/blocks"
import { Choice, ChoiceInput, FormField, TextInput, idOf } from "@/components/form"
import { act, setValue } from "@/lib/bridge"
import { numText, type Model } from "@/lib/model"

export function ProjectPage({ m }: { m: Model }) {
  const p = m.state.project, L = m.lists
  return (
    <div className="space-y-8">
      <Section title="Project" lead="Who the assessment is for and when it is built. Occupancy sets the water budget (B7) against the RIBA 2030 Climate Challenge potable water target.">
        <FieldGrid>
          <FormField label="Project name" required htmlFor={idOf(["project", "name"])}>
            <TextInput path={["project", "name"]} value={p.name} />
          </FormField>
          <FormField label="Use class" htmlFor={idOf(["project", "use_class"])}>
            <ChoiceInput path={["project", "use_class"]} value={p.use_class} options={L.uses} />
          </FormField>
          <FormField label="RIBA stage" htmlFor={idOf(["project", "riba_stage"])}>
            <ChoiceInput path={["project", "riba_stage"]} kind="int" value={String(p.riba_stage)} options={L.stages} />
          </FormField>
          <FormField label="Construction start year" htmlFor={idOf(["project", "start_year"])}>
            <TextInput path={["project", "start_year"]} value={p.start_year} kind="int" numeric />
          </FormField>
          <FormField label="Existing GIA demolished (m²)" htmlFor={idOf(["project", "demolished_gia_m2"])}>
            <TextInput path={["project", "demolished_gia_m2"]} value={numText(p.demolished_gia_m2)} kind="num0" numeric />
          </FormField>
          <FormField label="Assessor" htmlFor={idOf(["project", "assessor"])}>
            <TextInput path={["project", "assessor"]} value={p.assessor} />
          </FormField>
          <FormField label="Estimated occupancy (people)" htmlFor={idOf(["project", "occupancy"])}
            hint="Workplaces for offices, residents for homes, pupils for schools.">
            <TextInput path={["project", "occupancy"]} value={numText(p.occupancy)} kind="num" numeric />
          </FormField>
          <FormField label="Occupied days per year" htmlFor={idOf(["project", "occ_days"])}
            hint="Blank: 250 for offices, 365 for homes, 190 for schools.">
            <TextInput path={["project", "occ_days"]} value={numText(p.occ_days)} kind="num" numeric />
          </FormField>
        </FieldGrid>
      </Section>

      <Section title="Design options"
        lead="Each option is a massing layer in this file or another .3dm. Substructure, structure and façade are set per option on steps 3 to 5, so options can share a massing.">
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className="hidden grid-cols-[2rem_minmax(8rem,12rem)_9rem_minmax(0,1fr)_2.25rem] gap-3 border-b bg-muted/60 px-3 py-2 text-xs font-medium text-muted-foreground @2xl/main:grid">
            <span>Use</span><span>Option name<span className="text-destructive">*</span></span><span>Massing from</span><span>Layer or file<span className="text-destructive">*</span></span><span />
          </div>
          <ul className="divide-y">
            {m.state.options.map((o, i) => (
              <li key={i} className="grid grid-cols-[2rem_minmax(0,1fr)_2.25rem] items-center gap-x-3 gap-y-2 px-3 py-2.5 @2xl/main:grid-cols-[2rem_minmax(8rem,12rem)_9rem_minmax(0,1fr)_2.25rem]">
                <Checkbox checked={o.include} aria-label={`Include ${o.name}`}
                  onCheckedChange={(v) => setValue(["options", i, "include"], v === true, "bool")} />
                <TextInput path={["options", i, "name"]} value={o.name} aria-label="Option name" />
                <Button type="button" variant="ghost" size="icon" className="size-8 text-muted-foreground @2xl/main:order-last"
                  disabled={m.state.options.length < 2} aria-label={`Remove ${o.name}`} title="Remove this option"
                  onClick={() => act("remove_option", { i })}>
                  <Trash />
                </Button>
                <div className="col-start-2 @2xl/main:col-start-auto">
                  <Choice value={o.source} aria-label="Massing from"
                    options={[["layer", "This file"], ["file", "Other .3dm"]]}
                    onChange={(v) => act("option_source", { i, source: v })} />
                </div>
                <div className="col-span-2 col-start-2 min-w-0 @2xl/main:col-span-1 @2xl/main:col-start-auto">
                  {o.source === "layer" ? (
                    <Choice value={o.layer} options={L.massing_layers} aria-label="Massing layer" placeholder="Choose the massing layer"
                      onChange={(v) => setValue(["options", i, "layer"], v)} />
                  ) : (
                    <div className="flex gap-2">
                      <TextInput path={["options", i, "file"]} value={o.file} className="min-w-0 flex-1" aria-label="Massing file" />
                      <Button type="button" variant="outline" size="icon" className="size-8" aria-label="Choose the .3dm"
                        onClick={() => act("pick_3dm", { i })}>
                        <FolderOpen />
                      </Button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => act("add_option")}><Plus />Add option</Button>
          <Button type="button" variant="outline" size="sm" onClick={() => act("duplicate_option")}><CopyPlus />Duplicate last option</Button>
        </div>
        <Note>Tick at least one option. Option names must differ from each other.</Note>
      </Section>
    </div>
  )
}
