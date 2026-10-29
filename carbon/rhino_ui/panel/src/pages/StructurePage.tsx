// Step 4: frame system and column grid, per option. Drafted by an AI agent (Claude) - review before trusting.
import { FieldGrid, Note, Section } from "@/components/blocks"
import { ChoiceInput, FormField, NumField, idOf } from "@/components/form"
import { OptionPicker } from "@/components/option-picker"
import { ModelNotice } from "./ModelSection"
import type { PageProps } from "@/lib/model"

type Structure = { frame: string; grid_x_m: number | null; grid_y_m: number | null; column_size_m: number | null }

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
          <NumField path={P("column_size_m")} value={s.column_size_m} label="Column size (m, square)" />
        </FieldGrid>
        <Note>
          Cores, columns and stairs come from the plan on step 2 when there is one; otherwise these values and the office defaults are used
          and the rows are tagged [ASSUMED] in the workbook. Foundations and basement walls are set on step 3.
        </Note>
      </Section>
    </div>
  )
}
