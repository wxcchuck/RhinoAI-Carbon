// Step 2, detailed model: one line per layer (or more), mapping modelled objects to build-ups. The rules and the
// measuring live in Python (wlca_modelled.py, wlca_modelled_rhino.py). Drafted by an AI agent (Claude) - review before trusting.
import { Box, Copy, Ruler, Trash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Note, Notice, Section } from "@/components/blocks"
import { ChoiceInput, TextInput } from "@/components/form"
import { act, setValue } from "@/lib/bridge"
import { fmt, type Model } from "@/lib/model"
import { useSticky } from "@/lib/results"
import { cn } from "@/lib/utils"

type Rule = { layer: string; rics: string; measure: string; build_up: string; factor: number; replaces: string; source: string; note: string }
type View = { n: number | null; open: number | null; q: number | null; unit: string; share: number | null }
type BuildUp = [string, string, string, string]          // code, label, unit, RICS code

const UNIT: Record<string, string> = { m2: "m²", m3: "m³", nr: "nr", m: "m" }
const LINE = "grid gap-2 @3xl/main:grid-cols-[minmax(9rem,12rem)_minmax(0,1fr)_6.5rem_4.5rem_minmax(9rem,13rem)_6.5rem_4rem] @3xl/main:items-center"

export function ModelSection({ m }: { m: Model }) {
  const md = (m.state.modelled || {}) as { rules?: Rule[]; summary?: string[]; report?: Record<string, string[]>; measured?: unknown }
  const rules = md.rules || []
  const view = (m.model_rules || []) as View[]
  const L = m.lists as Record<string, unknown>
  const measures = (L.measures || []) as [string, string][]
  const units = (L.measure_units || {}) as Record<string, string>
  const bus = (L.build_ups || []) as BuildUp[]
  const codes = (L.rics_codes || []) as string[]
  const groups = (L.replace_groups || []) as [string, string][]
  const [showIgnored, setShowIgnored] = useSticky("model.ignored", false)

  // lines grouped by layer, in table order; k = the line's index in the saved table
  const layers: { layer: string; lines: number[] }[] = []
  rules.forEach((r, k) => {
    const last = layers[layers.length - 1]
    if (last && last.layer === r.layer) last.lines.push(k)
    else layers.push({ layer: r.layer, lines: [k] })
  })
  const isOn = (g: { lines: number[] }) => g.lines.some((k) => rules[k].measure !== "ignore")
  const shown = layers.filter((g) => showIgnored || isOn(g))
  const hidden = layers.length - shown.length
  const opts = m.state.options

  return (
    <Section title="Modelled elements"
      lead="Slabs, frames, walls or façade modelled in this file are taken off as modelled and replace the massing estimate for the same elements. Each layer gets a line: what it is, how it is measured and its build-up. Layers that follow the office names fill themselves; anything else stays ignored until you set it.">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" onClick={() => act("scan_model", {}, "Reading the model layers…")}><Box />{rules.length ? "Read the model again" : "Read the model"}</Button>
        {rules.length > 0 && (
          <Button type="button" variant="outline" size="sm" onClick={() => act("measure_model", {}, "Measuring…")}><Ruler />Measure again</Button>
        )}
        {layers.length > 0 && (
          <label className="ml-auto inline-flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox checked={showIgnored} onCheckedChange={(v) => setShowIgnored(v === true)} />
            Show ignored layers{hidden ? ` (${hidden})` : ""}
          </label>
        )}
      </div>
      {(md.summary || []).map((s, i) => <Notice key={i} tone={/could not/.test(s) ? "warn" : "note"}>{s}</Notice>)}

      {rules.length > 0 && (
        <>
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <span className="text-muted-foreground">Options that use the model:</span>
            {opts.map((o, i) => (
              <label key={i} className="inline-flex items-center gap-2">
                <Checkbox checked={o.use_modelled !== false} onCheckedChange={(v) => setValue(["options", i, "use_modelled"], v === true, "bool")} />
                {o.name || `Option ${i + 1}`}
              </label>
            ))}
          </div>

          <div className={cn("mt-4 hidden gap-2 px-3 text-xs font-medium text-muted-foreground @3xl/main:grid", LINE)}>
            <span>Measure</span><span>Build-up</span><span>RICS</span><span>Factor</span><span>Replaces</span>
            <span className="text-right">Quantity</span><span />
          </div>
          <ul className="mt-1 space-y-2">
            {shown.map((g) => {
              const v0 = view[g.lines[0]] || ({} as View)
              const parts = g.layer.split("::")
              return (
                <li key={g.layer} className={cn("rounded-lg border bg-card px-3 py-2.5", !isOn(g) && "bg-muted/40")}>
                  <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="font-medium break-all">{parts[parts.length - 1]}</span>
                    {parts.length > 1 && <span className="text-xs text-muted-foreground">{parts.slice(0, -1).join(" › ")}</span>}
                    <span className="num ml-auto text-xs text-muted-foreground">
                      {v0.n == null ? "not measured" : `${fmt(v0.n)} objects${v0.open ? `, ${fmt(v0.open)} open` : ""}`}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {g.lines.map((k) => <RuleLine key={k} k={k} r={rules[k]} v={view[k] || ({} as View)} measures={measures} units={units}
                      bus={bus} codes={codes} groups={groups} several={g.lines.length > 1} />)}
                  </div>
                </li>
              )
            })}
          </ul>
          <Note>
            Volume and plan area are exact for pieces with flat tops and vertical sides (slabs, panels, bricks, columns, glass). Face area is
            one side of a wall-like piece. "Share of the massing façade" splits the massing's net façade between the share lines by their
            modelled face areas - the model says what the façade is made of, the massing how much façade there is. An object with user text
            WLCA_BUILDUP=&lt;code&gt; is taken off on its own with that build-up. A layer named RICS_&lt;code&gt;_…_&lt;build-up&gt; maps itself.
          </Note>
        </>
      )}
      {Object.entries(md.report || {}).filter(([, lines]) => lines.length).map(([name, lines]) => (
        <Notice key={name} tone="good">{`Last run, ${name}:\n` + lines.join("\n")}</Notice>
      ))}
    </Section>
  )
}

function RuleLine({ k, r, v, measures, units, bus, codes, groups, several }: {
  k: number; r: Rule; v: View; measures: [string, string][]; units: Record<string, string>; bus: BuildUp[]; codes: string[]
  groups: [string, string][]; several: boolean
}) {
  const on = r.measure !== "ignore"
  const unit = units[r.measure] || ""
  const fit = bus.filter((b) => !on || b[2] === unit)
  const buOpts: [string, string][] = [["", "(choose)"], ...fit.map((b) => [b[0], b[1]] as [string, string])]
  if (r.build_up && !fit.some((b) => b[0] === r.build_up)) buOpts.push([r.build_up, `${r.build_up} (not per ${unit || "this measure"})`])
  const codeOpts = r.rics && !codes.includes(r.rics) ? [r.rics, ...codes] : codes
  const P = (f: string) => ["modelled", "rules", k, f]
  return (
    <div className={LINE}>
      <ChoiceInput path={P("measure")} value={r.measure} options={measures} aria-label="Measure" />
      {on ? (
        <>
          <ChoiceInput path={P("build_up")} value={r.build_up} options={buOpts} aria-label="Build-up" />
          <ChoiceInput path={P("rics")} value={r.rics} options={[["", "–"], ...codeOpts.map((c) => [c, c] as [string, string])]} aria-label="RICS element" />
          <TextInput path={P("factor")} value={r.factor} kind="num" numeric aria-label="Factor" />
          <ChoiceInput path={P("replaces")} value={r.replaces} options={groups} aria-label="Replaces" />
          <span className="num text-right text-sm" title={v.share != null ? `${(v.share * 100).toFixed(1)}% of the modelled façade` : undefined}>
            {v.q == null ? "–" : `${fmt(v.q)} ${UNIT[v.unit] || v.unit}`}
            {v.share != null && <span className="block text-xs text-muted-foreground">{(v.share * 100).toFixed(1)}% of façade</span>}
          </span>
        </>
      ) : (
        <span className="text-sm text-muted-foreground @3xl/main:col-span-5">{r.note || "Ignored"}</span>
      )}
      <div className="flex justify-end gap-0.5">
        <Button type="button" variant="ghost" size="icon" className="size-8 text-muted-foreground" title="Add another line for this layer"
          aria-label="Add another line for this layer" onClick={() => act("add_model_rule", { k })}><Copy /></Button>
        <Button type="button" variant="ghost" size="icon" className="size-8 text-muted-foreground" disabled={!several && !on}
          title={several ? "Remove this line" : "Ignore this layer"} aria-label={several ? "Remove this line" : "Ignore this layer"}
          onClick={() => act("remove_model_rule", { k })}><Trash /></Button>
      </div>
      {on && r.note && <p className="text-xs text-muted-foreground @3xl/main:col-span-7">{r.note}</p>}
    </div>
  )
}
