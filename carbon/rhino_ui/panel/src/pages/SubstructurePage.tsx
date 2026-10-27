// Step 3: basement, walls, piles, caps / raft, per option. Drafted by an AI agent (Claude) - review before trusting.
import { CopyCheck, Plus, Trash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { FieldGrid, Note, Notice, Section } from "@/components/blocks"
import { ChoiceInput, FormField, NumField, TextInput, idOf } from "@/components/form"
import { OptionPicker } from "@/components/option-picker"
import { act, setValue, type Path } from "@/lib/bridge"
import { fmt, type PageProps } from "@/lib/model"

type Level = { name: string; ftf: number | null; gea: number | null; gia: number | null }
type Sub = {
  basement?: { answer?: string | null; levels?: Level[]; ground_level?: number | null }
  retaining_walls: Record<string, number | string | null>
  piles: Record<string, number | string | boolean | null>
  caps_raft: Record<string, number | string | null>
}
type Basement = { levels: string[]; depth_m: number; ftf: number[]; gea: number[] } | null

export function SubstructurePage({ m, sel, setSel }: PageProps) {
  const i = Math.min(sel, m.state.options.length - 1)
  const o = m.state.options[i]
  const u = o.substructure as Sub
  const L = m.lists as Record<string, [string, string][]>
  const B = m.basement as Basement
  const ext = ((m.massing_z as ([number, number] | null)[] | undefined) || [])[i]
  const P = (...k: (string | number)[]): Path => ["options", i, "substructure", ...k]
  const bs = u.basement || {}
  const w = u.retaining_walls, p = u.piles, c = u.caps_raft
  const fromSchedule = !!(B && B.levels.length)

  return (
    <div className="space-y-8">
      <OptionPicker m={m} sel={i} setSel={setSel} />

      <Section title="Basement" code="1.2.1, 1.2.2">
        {fromSchedule ? (
          <Notice tone="good">
            From the area schedule: {B!.levels.length} level{B!.levels.length === 1 ? "" : "s"} below ground, {fmt(B!.depth_m, 2)} m deep.
            {"\n"}
            {B!.levels.map((n, k) => `${n} (${fmt(B!.ftf[k], 2)} m, GEA ${fmt(B!.gea[k])} m²)`).join(", ")}
            {"\n"}The lowest level's GEA is the lowest slab (1.2.1); the levels above it up to ground are basement suspended slabs (1.2.2).
          </Notice>
        ) : (
          <>
            <Notice tone={bs.answer === "none" || bs.answer === "levels" ? "note" : "warn"}>
              {B ? "The area schedule has no levels below ground." : "No area schedule on step 2."} Confirm whether there is a basement.
            </Notice>
            <FieldGrid className="mt-4">
              <FormField label="Basement" required htmlFor={idOf(P("basement", "answer"))}>
                <ChoiceInput path={P("basement", "answer")} value={bs.answer || ""} placeholder="Confirm…"
                  options={[["none", "No basement - confirmed"], ["levels", "Yes - enter the basement levels"]]} />
              </FormField>
            </FieldGrid>
            {bs.answer === "levels" && <BasementLevels i={i} levels={bs.levels || []} P={P} />}
          </>
        )}
        <FieldGrid className="mt-5">
          <NumField path={P("basement", "ground_level")} value={bs.ground_level} label="Ground floor level in the model (m)" />
        </FieldGrid>
        <Note>
          Blank: {B && B.levels ? "the schedule's ground AOD if it has one, else " : ""}the massing's lowest point
          {ext ? ` (this option's massing runs from ${fmt(ext[0], 2)} to ${fmt(ext[1], 2)} m)` : ""}. Massing below ground level is never
          counted as façade. Basement walls take the perimeter of the largest basement level measured on the massing; without a
          modelled basement, the ground-floor perimeter × √(basement GEA / ground GEA), never scaled down.
        </Note>
      </Section>

      <Section title="Basement walls" code="1.2.3">
        <FieldGrid>
          <FormField label="Basis" htmlFor={idOf(P("retaining_walls", "source"))} className="@md/main:col-span-2">
            <ChoiceInput path={P("retaining_walls", "source")} value={w.source as string} options={L.wall_sources} />
          </FormField>
          {w.source === "engineer" ? (
            <>
              <NumField path={P("retaining_walls", "volume_m3")} value={w.volume_m3} label="Wall volume, piled wall (m³)" />
              <NumField path={P("retaining_walls", "area_m2")} value={w.area_m2} label="Wall area (m²)" />
              <NumField path={P("retaining_walls", "perimeter_m")} value={w.perimeter_m} label="Perimeter (m)" />
              <NumField path={P("retaining_walls", "depth_m")} value={w.depth_m} label="Depth (m)" hint="Blank: the basement depth." />
            </>
          ) : (
            <>
              <FormField label="Wall type" htmlFor={idOf(P("retaining_walls", "type"))}>
                <ChoiceInput path={P("retaining_walls", "type")} value={w.type as string} options={L.wall_types} />
              </FormField>
              {w.type === "secant" && (
                <>
                  <NumField path={P("retaining_walls", "pile_diameter_m")} value={w.pile_diameter_m} label="Pile diameter (m)" required />
                  <NumField path={P("retaining_walls", "pile_spacing_m")} value={w.pile_spacing_m} label="Hard-to-hard spacing (m)" required />
                  <NumField path={P("retaining_walls", "pile_length_m")} value={w.pile_length_m} label="Pile length (m)" hint="Blank: depth × (1 + embedment)." />
                  <NumField path={P("retaining_walls", "embedment_ratio")} value={w.embedment_ratio} label="Embedment below formation" hint="× the retained height." />
                  <NumField path={P("retaining_walls", "liner_thickness_m")} value={w.liner_thickness_m} label="RC liner thickness (m)" hint="Blank: no liner." />
                </>
              )}
              <NumField path={P("retaining_walls", "perimeter_m")} value={w.perimeter_m} label="Basement perimeter (m)" hint="Blank: from the massing (see above)." />
            </>
          )}
        </FieldGrid>
        <Note>
          {w.source === "engineer"
            ? "The first figure given is used: volume (secant or contiguous piled wall), else area (RC wall), else perimeter × depth."
            : w.type === "secant"
              ? "Hard (reinforced) piles at the hard-to-hard spacing with one firm pile between each pair; overlaps are taken off the firm piles. The liner is perimeter × basement depth."
              : "RC wall area = perimeter × basement depth."}
        </Note>
      </Section>

      <Section title="Piles" code="1.1">
        <FieldGrid>
          <FormField label="Basis" htmlFor={idOf(P("piles", "source"))} className="@md/main:col-span-2">
            <ChoiceInput path={P("piles", "source")} value={p.source as string} options={L.pile_sources} />
          </FormField>
          {p.source === "assumed" && (
            <>
              <NumField path={P("piles", "diameter_m")} value={p.diameter_m} label="Pile diameter (m)" required />
              <NumField path={P("piles", "per_column")} value={p.per_column} label="Piles per column" required />
              <NumField path={P("piles", "length_m")} value={p.length_m} label="Pile length (m)" required />
              <NumField path={P("piles", "core_spacing_x_dia")} value={p.core_spacing_x_dia} label="Core pile spacing (× diameter)" />
            </>
          )}
          {p.source === "engineer" && (
            <>
              <NumField path={P("piles", "count")} value={p.count} label="Number of piles" required />
              <NumField path={P("piles", "diameter_m")} value={p.diameter_m} label="Pile diameter (m)" required />
              <NumField path={P("piles", "length_m")} value={p.length_m} label="Pile length (m)" required />
            </>
          )}
        </FieldGrid>
        {p.source === "assumed" && (
          <>
            <div className="mt-4 flex items-center gap-2.5">
              <Checkbox id={idOf(P("piles", "core_group"))} checked={!!p.core_group}
                onCheckedChange={(v) => setValue(P("piles", "core_group"), v === true, "bool")} />
              <Label htmlFor={idOf(P("piles", "core_group"))} className="font-normal">
                Pile group under the core (core area from the plan or the schedule)
              </Label>
            </div>
            <Note>Columns arriving at the lowest level × piles per column, plus a group under the core at the core spacing. Bored, no site investigation yet.</Note>
          </>
        )}
      </Section>

      <Section title="Pile caps or raft" code="1.1">
        <FieldGrid>
          <FormField label="Basis" htmlFor={idOf(P("caps_raft", "source"))} className="@md/main:col-span-2">
            <ChoiceInput path={P("caps_raft", "source")} value={c.source as string} options={L.cap_sources} />
          </FormField>
          {c.source === "assumed" && (
            <>
              <NumField path={P("caps_raft", "depth_m")} value={c.depth_m} label="Column cap depth (m)" required />
              <NumField path={P("caps_raft", "edge_m")} value={c.edge_m} label="Cap edge beyond pile (m)" />
              <NumField path={P("caps_raft", "core_thickness_m")} value={c.core_thickness_m} label="Core cap thickness (m)" required />
              <NumField path={P("caps_raft", "core_margin_m")} value={c.core_margin_m} label="Core cap margin all round (m)" />
            </>
          )}
          {c.source === "raft" && <NumField path={P("caps_raft", "raft_thickness_m")} value={c.raft_thickness_m} label="Raft thickness (m)" required />}
          {c.source === "engineer" && <NumField path={P("caps_raft", "volume_m3")} value={c.volume_m3} label="Caps or raft volume (m³)" required />}
        </FieldGrid>
        {c.source === "assumed" && <Note>One cap per column sized for its piles at the core spacing, and one cap over the core area plus the margin. Follows the assumed piles only.</Note>}
        {c.source === "raft" && <Note>Raft under the lowest level: thickness × the lowest level's GEA. Its top is the lowest slab (1.2.1, counted there), so this row takes the thickness less that slab. With piles it is a piled raft.</Note>}
      </Section>

      <div className="border-t pt-5">
        {m.state.options.length > 1 && (
          <Button type="button" variant="outline" size="sm" onClick={() => act("copy_substructure", { i })}>
            <CopyCheck />Use these settings for every option
          </Button>
        )}
        <Note>
          Rows resting on these assumptions are tagged [ASSUMED] in the workbook; replace them with the engineer's figures when there are
          some. The lowest slab (1.2.1) and basement slabs (1.2.2) come from the schedule or the massing.
        </Note>
      </div>
    </div>
  )
}

// narrow docked panel: tighter number columns; headers wrap
const COLS = "grid-cols-[minmax(0,1fr)_4.75rem_4.75rem_4.75rem_2rem] @xl/main:grid-cols-[minmax(0,1fr)_7rem_7rem_7rem_2.25rem]"

function BasementLevels({ i, levels, P }: { i: number; levels: Level[]; P: (...k: (string | number)[]) => Path }) {
  return (
    <div className="mt-4">
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className={`grid ${COLS} gap-2 border-b bg-muted/60 px-3 py-2 text-xs font-medium text-muted-foreground`}>
          <span>Level, top down from ground</span>
          <span>Floor to floor (m)<span className="text-destructive">*</span></span>
          <span>GEA (m²)</span>
          <span>GIA (m²)</span>
          <span />
        </div>
        <ul className="divide-y">
          {levels.map((x, j) => (
            <li key={j} className={`grid ${COLS} items-center gap-2 px-3 py-2`}>
              <TextInput path={P("basement", "levels", j, "name")} value={x.name} aria-label="Level name" />
              {(["ftf", "gea", "gia"] as const).map((k) => (
                <TextInput key={k} path={P("basement", "levels", j, k)} kind="num" numeric aria-label={k.toUpperCase()}
                  value={x[k] == null ? "" : (x[k] as number).toLocaleString("en-GB", { maximumFractionDigits: 2 })} />
              ))}
              <Button type="button" variant="ghost" size="icon" className="size-8 text-muted-foreground" aria-label={`Remove ${x.name}`}
                title="Remove this level" onClick={() => act("remove_basement_level", { i, j })}>
                <Trash />
              </Button>
            </li>
          ))}
        </ul>
      </div>
      <Button type="button" variant="outline" size="sm" className="mt-3" onClick={() => act("add_basement_level", { i })}>
        <Plus />Add basement level
      </Button>
      <Note>
        GEA and GIA blank: measured on the massing below ground level (the massing must include the basement). The depth is the sum of the
        floor-to-floor heights; the lowest level's GEA is the lowest slab (1.2.1), the levels above it the basement slabs (1.2.2).
      </Note>
    </div>
  )
}
