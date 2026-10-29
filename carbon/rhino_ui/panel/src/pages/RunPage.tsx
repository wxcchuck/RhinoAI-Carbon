// Step 7: office settings, checks, take-off, workbook. Drafted by an AI agent (Claude) - review before trusting.
import { ExternalLink, FileSpreadsheet, FolderOpen, ImageOff, LoaderCircle, Play, RotateCcw, Ruler, Sheet, Eye } from "lucide-react"
import { Button } from "@/components/ui/button"
import { FieldGrid, Note, Notice, Section } from "@/components/blocks"
import { Choice, FormField, PathInput, idOf } from "@/components/form"
import { act, setValue } from "@/lib/bridge"
import type { Model, PageProps } from "@/lib/model"

type Src = "schedule" | "plan" | "massing" | "model"
type ReconRow = {
  key: string; label: string; unit: string; values: Partial<Record<Src, number | null>>; ref: Src | null
  diff: Partial<Record<Src, number | null>>; flag: boolean; group: "levels" | "totals" | "checks"; note: string; where: string
  choice: { key: string; options: [string, string][]; value: string } | null; digits: number
}
type Recon = { option: string; i: number; rows?: ReconRow[]; tolerance?: number; stale?: boolean }
type Run = { rows: (string | number)[][]; names: string[]; ready: boolean; messages: string[]; stale?: string[]; recon?: Recon[] }
type Logo = { path: string; url: string; exists: boolean }

export function RunPage({ m, goTo }: PageProps) {
  const office = m.office
  const run = m.run as Run
  const logo = m.logo as Logo
  const layersOff = (m.layers_off as string[]) || []
  const out = m.state.output as { font?: string; last_workbook?: string }
  const fonts = (m.lists.fonts as string[]) || []
  const cur = out.font || "Arial"
  const missing = fonts.length > 0 && !fonts.includes(cur)
  const fontOpts: [string, string][] = [...(missing ? [[cur, `${cur} (not installed here)`] as [string, string]] : []),
    ...(fonts.length ? fonts : [cur]).map((f) => [f, f] as [string, string])]
  const running = m.calc?.status === "running"

  return (
    <div className="space-y-8">
      <Section title="Office settings" lead="The build-up library, benchmarks, targets and branding come from this file.">
        <div className="flex flex-wrap items-center gap-2">
          <code className="min-w-0 flex-1 rounded-md bg-muted px-2.5 py-1.5 text-xs break-all">{office.path || "(none)"}</code>
          <Button type="button" variant="outline" size="sm" onClick={() => act("pick_office_settings")}><FolderOpen />Choose…</Button>
          <Button type="button" variant="ghost" size="sm" disabled={office.source !== "chosen on this PC"}
            onClick={() => act("reset_office_settings")}><RotateCcw />Use default</Button>
        </div>
        {office.error ? <Notice tone="error">{office.error}</Notice> : <Note>Source: {office.source}.</Note>}
      </Section>

      <Section title="Checks">
        {m.checks.length === 0 && <Notice tone="good">Everything needed is filled in.</Notice>}
        {m.checks.map((c, k) => {
          const at = /\(step (\d)\)/.exec(c.text)
          return (
            <Notice key={k} tone={c.level === "error" ? "error" : "note"}
              action={at && <Button type="button" variant="outline" size="sm" className="bg-card" onClick={() => goTo(Number(at[1]) - 1)}>Go to step {at[1]}</Button>}>
              {c.level === "error" ? "Fix: " : ""}{c.text}
            </Notice>
          )
        })}
      </Section>

      <Section title="1. Take-off" lead="Measures every ticked option and draws floor plates and GIA curves on the WLCA layers for checking.">
        <Button type="button" size="sm" variant={run.ready ? "outline" : "default"} disabled={m.blocked} onClick={() => act("run_takeoff")}>
          <Ruler />Run take-off
        </Button>
        {m.blocked && <span className="ml-3 text-xs text-muted-foreground">Fix the checks above first.</span>}
        <Notice tone="warn">
          Before running, turn on the massing layers (step 1) and the plan layers (step 2), with their parent layers. The take-off and the
          plan reader skip anything on a layer that is off, and objects hidden with Hide (use Show first). Easiest: turn all layers on.
        </Notice>
        {layersOff.length > 0 && (
          <Notice tone="warn" action={<Button type="button" variant="outline" size="sm" onClick={() => act("turn_layers_on")}><Eye />Turn these layers on</Button>}>
            These layers are off now: {layersOff.join("; ")}
          </Notice>
        )}
        {run.rows.length > 0 && <TakeoffTable run={run} />}
        {run.messages.map((t, k) => <Notice key={k} tone="warn">{t}</Notice>)}
      </Section>

      <Section title="2. Reconciliation" lead={`Each quantity from every source that has it; under each value its difference from the reference (bold), with ⚠ beyond ±${Math.round(100 * ((run.recon || [])[0]?.tolerance ?? 0.05))}%. Core height and basement depth are chosen here; the rest are set on the step each row names.`}>
        {!(run.recon || []).some((r) => (r.rows || []).length) && <Note>Run the take-off to see the reconciliation.</Note>}
        {(run.recon || []).filter((r) => (r.rows || []).length).map((r) => <ReconTable key={r.option} r={r} goTo={goTo} />)}
      </Section>

      <Section title="3. Workbook" lead="Builds the Excel workbook; Excel then calculates it in the background and the results open here.">
        <FieldGrid>
          <FormField label="Font" htmlFor={idOf(["output", "font"])} className="@md/main:col-span-2"
            hint={missing ? <span className="text-warn">Not installed on this PC: Excel will show a substitute.</span>
              : `${fonts.length} fonts on this PC; used on every sheet, charts included.`}>
            <Choice id={idOf(["output", "font"])} value={cur} options={fontOpts} onChange={(v) => setValue(["output", "font"], v)} />
          </FormField>
        </FieldGrid>
        <div className="mt-4 grid gap-1.5">
          <FormField label="Company logo (optional)" htmlFor={idOf(["output", "logo"])}>
            <div className="flex min-w-0 flex-wrap gap-2">
              <div className="min-w-0 flex-1"><PathInput path={["output", "logo"]} value={logo.path} action="pick_logo" /></div>
              <Button type="button" variant="ghost" size="sm" className="h-8" onClick={() => act("logo_none")}><ImageOff />No logo</Button>
            </div>
          </FormField>
          {logo.url ? <img src={logo.url} alt="Logo preview" className="mt-2 max-h-14 max-w-60 rounded border bg-white object-contain p-1.5" />
            : logo.path ? <Notice tone="warn">Logo file not found.</Notice> : null}
        </div>
        <Note>
          The logo goes at the top left of the Dashboard. The font is stored by name: people opening the workbook without it see Excel's
          substitute, so use a common font (Arial, Calibri) for files that leave the office.
        </Note>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant={run.ready ? "default" : "outline"} disabled={!run.ready || m.blocked || running || (run.stale || []).length > 0}
            onClick={() => act("create_workbook")}>
            <Play />Create workbook and calculate
          </Button>
          {!run.ready && <span className="text-xs text-muted-foreground">Run the take-off first.</span>}
          {run.ready && (run.stale || []).length > 0 && <span className="text-xs text-warn">Choices changed: run the take-off again first.</span>}
        </div>
        <CalcStatus m={m} />
        {out.last_workbook && (
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border bg-card px-3 py-2">
            <FileSpreadsheet className="size-4 text-good" aria-hidden />
            <span className="min-w-0 flex-1 text-sm break-all">Saved: {out.last_workbook}</span>
            <Button type="button" variant="outline" size="sm" onClick={() => act("open_workbook")}><ExternalLink />Open in Excel</Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => act("open_folder")}><FolderOpen />Open folder</Button>
          </div>
        )}
      </Section>
    </div>
  )
}

export function CalcStatus({ m }: { m: Model }) {
  const c = m.calc || { status: "", message: "" }
  if (c.status === "running")
    return (
      <div role="status" className="mt-3 flex items-center gap-2.5 rounded-md bg-accent px-3 py-2.5 text-sm text-accent-foreground">
        <LoaderCircle className="size-4 shrink-0 animate-spin" aria-hidden />{c.message}
      </div>
    )
  if (c.status === "failed")
    return (
      <Notice tone="warn" action={<Button type="button" variant="outline" size="sm" onClick={() => act("calculate")}><Sheet />Calculate results</Button>}>
        {c.message}
      </Notice>
    )
  return null
}

function TakeoffTable({ run }: { run: Run }) {
  return (
    <div className="mt-4 overflow-x-auto rounded-lg border bg-card">
      <table className="w-full min-w-max text-sm">
        <thead>
          <tr className="border-b bg-muted/60 text-xs text-muted-foreground">
            <th scope="col" className="px-3 py-2 text-left font-medium">Quantity</th>
            {run.names.map((n) => <th key={n} scope="col" className="px-3 py-2 text-right font-semibold text-foreground">{n}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y">
          {run.rows.map((r, k) => (
            <tr key={k}>
              <th scope="row" className="px-3 py-1.5 text-left font-normal">{r[0]}</th>
              {r.slice(1).map((v, j) => <td key={j} className="num px-3 py-1.5 text-right">{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const SOURCES: [Src, string][] = [["schedule", "Schedule"], ["plan", "Plans"], ["massing", "Massing"], ["model", "Model"]]
const GROUPS: Record<string, string> = { levels: "GEA per level", totals: "Building totals", checks: "Model checks" }

function fmtVal(v: number | null | undefined, unit: string, digits: number) {
  if (v == null) return "–"
  if (unit === "%") return `${(100 * v).toFixed(0)}%`
  if (Math.abs(v) < 0.5 && !digits) return "0"
  return v.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function fmtDiff(d: number) {
  const p = 100 * d
  return `${p > 0 ? "+" : p < 0 ? "−" : ""}${Math.abs(p).toFixed(1)}%`
}

function ReconTable({ r, goTo }: { r: Recon; goTo: (i: number) => void }) {
  const rows = r.rows || []
  const tol = r.tolerance ?? 0.05
  const used = SOURCES.filter(([s]) => rows.some((x) => x.values && x.values[s] != null))
  const span = 2 + used.length
  let grp = ""
  return (
    <div className="mt-3 space-y-2">
      <h3 className="text-sm font-semibold">Option {r.option}</h3>
      {r.stale && <Notice tone="warn">A choice below changed since the take-off ran: run the take-off again to apply it.</Notice>}
      <div className="overflow-x-auto rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/60 text-xs text-muted-foreground">
              <th scope="col" className="min-w-48 px-3 py-2 text-left font-medium">Quantity</th>
              {used.map(([s, t]) => <th key={s} scope="col" className="px-2 py-2 text-right font-medium whitespace-nowrap">{t}</th>)}
              <th scope="col" className="px-3 py-2 text-left font-medium whitespace-nowrap">Used / set on</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((x) => {
              const head = x.group !== grp ? (grp = x.group, GROUPS[x.group] || x.group) : null
              const step = /step (\d)/.exec(x.where || "")
              return [
                head && (
                  <tr key={`h-${x.key}`} className="bg-muted/40">
                    <th scope="colgroup" colSpan={span} className="px-3 py-1.5 text-left text-xs font-semibold">{head}</th>
                  </tr>
                ),
                <tr key={x.key} className="align-top">
                  <th scope="row" className="px-3 py-1.5 text-left font-normal">
                    {x.label}{x.unit && x.unit !== "%" && x.group !== "checks" ? <span className="text-muted-foreground"> ({x.unit.replace("m2", "m²").replace("m3", "m³")})</span> : null}
                    {x.note && x.group !== "checks" && <div className="mt-0.5 max-w-sm text-xs text-muted-foreground">{x.note}</div>}
                  </th>
                  {x.group === "checks"
                    ? <td colSpan={used.length} className="px-2 py-1.5 text-left"><span className="text-warn" aria-hidden>⚠ </span>{x.note}</td>
                    : <>
                      {used.map(([s]) => {
                        const d = x.diff?.[s]
                        const out = d != null && Math.abs(d) > tol
                        return (
                          <td key={s} className={`num px-2 py-1.5 text-right whitespace-nowrap ${s === x.ref ? "font-semibold" : ""}`}>
                            {s in (x.values || {}) ? fmtVal(x.values[s], x.unit, x.digits) : ""}
                            {d != null && (
                              <div className={`text-xs ${out ? "font-semibold text-warn" : "text-muted-foreground"}`}>
                                {out && <span aria-label="beyond the tolerance">⚠ </span>}{fmtDiff(d)}
                              </div>
                            )}
                          </td>
                        )
                      })}
                    </>}
                  <td className="px-3 py-1 text-left whitespace-nowrap">
                    {x.choice
                      ? <Choice aria-label={`${x.label}: source used`} className="h-7 w-48" value={x.choice.value}
                        options={x.choice.options} onChange={(v) => act("reconcile_choice", { i: r.i, key: x.choice!.key, value: v })} />
                      : step
                        ? <Button type="button" variant="link" size="sm" className="h-auto p-0 text-xs" title={x.where}
                          onClick={() => goTo(Number(step[1]) - 1)}>Step {step[1]}</Button>
                        : <span className="text-xs text-muted-foreground">{x.where}</span>}
                  </td>
                </tr>,
              ]
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
