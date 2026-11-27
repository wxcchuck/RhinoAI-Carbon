// Step 4: frame system and column grid, per option. Drafted by an AI agent (Claude) - review before trusting.
import { FileText, Plus, Trash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { FieldGrid, Note, Section } from "@/components/blocks"
import { ChoiceInput, FormField, NumField, TextInput, idOf } from "@/components/form"
import { act } from "@/lib/bridge"
import { OptionPicker } from "@/components/option-picker"
import { ModelNotice } from "./ModelSection"
import type { PageProps } from "@/lib/model"

type Band = { from: string; to: string; sizes: string }
type Structure = { frame: string; grid_x_m: number | null; grid_y_m: number | null; column_size_m: number | null
  plan_level?: string; column_sections?: Band[]; column_schedule?: { pdf?: string; page?: number; summary?: string; error?: string } }

export function StructurePage({ m, sel, setSel }: PageProps) {
  const i = Math.min(sel, m.state.options.length - 1)
  const s = m.state.options[i].structure as Structure
  const P = (k: string) => ["options", i, "structure", k]
  return (
    <div className="space-y-8">
      <OptionPicker m={m} sel={i} setSel={setSel} />
      <ModelNotice m={m} option={i} groups={["floors", "columns", "beams", "core_walls", "stairs"]} />
      <Section title="Frame" code="2.1, 2.2"
        lead="Steel and timber frames use the PF Stage 1 rates per m² of floor; their columns are scaled with height and tagged [ASSUMED]. Cores stay RC.">
        <FieldGrid>
          <FormField label="Frame system" htmlFor={idOf(P("frame"))} className="@md/main:col-span-2">
            <ChoiceInput path={P("frame")} value={s.frame} options={m.lists.frames as string[]} />
          </FormField>
        </FieldGrid>
      </Section>
      <Section title="Column grid">
        <FieldGrid>
          <NumField path={P("grid_x_m")} value={s.grid_x_m} label="Column grid x (m)" />
          <NumField path={P("grid_y_m")} value={s.grid_y_m} label="Column grid y (m)" />
          <NumField path={P("column_size_m")} value={s.column_size_m} label="Column size without a plan (m, square)" />
        </FieldGrid>
        <Note>
          Cores, columns and stairs come from the plan on step 2 when there is one; otherwise these values and the office defaults are used
          and the rows are tagged [ASSUMED] in the workbook. Foundations and basement walls are set on step 3.
        </Note>
      </Section>
      <ColumnSections m={m} i={i} s={s} />
    </div>
  )
}

// Column sections (D22, D23): the plan shows one level; the section of each level comes from the engineer's sections by band
// (typed, or read from the engineer's PDF column schedule), else a floors-carried rule from the plan level, else the plan section.
function ColumnSections({ m, i, s }: { m: PageProps["m"]; i: number; s: Structure }) {
  const levels = m.levels || []
  const bands = s.column_sections || []
  const src = s.column_schedule || {}
  const P = (...k: (string | number)[]) => ["options", i, "structure", ...k]
  const opts = [["", levels.length ? "Not set - plan section on every level" : "No area schedule"] as [string, string]]
    .concat(levels.map((n) => [n, n] as [string, string]))
  return (
    <Section title="Column sections" code="2.1.1"
      lead="The plan on step 2 shows one level, but columns usually get smaller towards the top. Each level's section comes from the engineer's sections below; levels they don't cover follow the floors each column carries: smaller above the plan level (not below 350 × 350 mm), larger below it (at most 1.5 × the plan section).">
      <FieldGrid>
        <FormField label="Level the plan shows" htmlFor={idOf(P("plan_level"))} className="@md/main:col-span-2">
          <ChoiceInput path={P("plan_level")} value={s.plan_level ?? ""} options={opts} />
        </FormField>
      </FieldGrid>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => act("read_column_pdf", { i }, "Reading the column schedule…")}>
          <FileText />Read from the engineer's PDF…
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => act("add_column_band", { i })}>
          <Plus />Add a band
        </Button>
      </div>
      {src.error ? (
        <p role="alert" className="mt-2 text-sm text-destructive">{src.error}</p>
      ) : src.summary ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Read from <span className="font-medium text-foreground">{baseName(src.pdf)}</span> - {src.summary}. Check them against the drawing.
        </p>
      ) : null}

      {bands.length === 0 ? (
        <p className="mt-3 rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
          No engineer's sections - the plan section and the rule are used.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {bands.map((b, j) => (
            <li key={j} className="rounded-lg border bg-card p-3">
              <div className="flex items-end gap-2">
                <label className="grid flex-1 gap-1 text-xs font-medium text-muted-foreground">
                  From level
                  <TextInput path={P("column_sections", j, "from")} value={b.from} placeholder="00" />
                </label>
                <label className="grid flex-1 gap-1 text-xs font-medium text-muted-foreground">
                  To level
                  <TextInput path={P("column_sections", j, "to")} value={b.to} placeholder="01" />
                </label>
                <Button type="button" variant="ghost" size="icon" className="size-9 shrink-0 text-muted-foreground"
                  aria-label={`Remove band ${b.from}-${b.to}`} title="Remove this band" onClick={() => act("remove_column_band", { i, j })}>
                  <Trash />
                </Button>
              </div>
              <label className="mt-2 grid gap-1 text-xs font-medium text-muted-foreground">
                Column sizes (mm), one per column type
                <TextInput path={P("column_sections", j, "sizes")} value={b.sizes} placeholder="450x1100, 450x1700, 350x900" />
              </label>
            </li>
          ))}
        </ul>
      )}
      <Note>
        The PDF reader looks for a table of levels (Level 01, Roof, B1 …) with column sizes as text (450x1400, D600) - not a scan - and groups
        neighbouring levels with the same sizes into bands, replacing the ones here. The first read installs the PDF library pymupdf into
        Rhino's Python (once). Sizes in a band are averaged, one per column type; level names follow the area schedule (01 matches 1). The
        workbook quantity is in metres of the column build-up, scaled to each level's section.
      </Note>
    </Section>
  )
}

const baseName = (p?: string) => (p || "").split(/[\\/]/).pop() || ""
