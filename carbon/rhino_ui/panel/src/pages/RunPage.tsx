// Step 7: office settings, checks, take-off, workbook. Drafted by an AI agent (Claude) - review before trusting.
import { ExternalLink, FileSpreadsheet, FolderOpen, ImageOff, LoaderCircle, Play, RotateCcw, Ruler, Sheet, Eye } from "lucide-react"
import { Button } from "@/components/ui/button"
import { FieldGrid, Note, Notice, Section } from "@/components/blocks"
import { Choice, FormField, PathInput, idOf } from "@/components/form"
import { act, setValue } from "@/lib/bridge"
import type { Model, PageProps } from "@/lib/model"

type Run = { rows: (string | number)[][]; names: string[]; ready: boolean; messages: string[] }
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

      <Section title="2. Workbook" lead="Builds the Excel workbook; Excel then calculates it in the background and the results open here.">
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
          <Button type="button" size="sm" variant={run.ready ? "default" : "outline"} disabled={!run.ready || m.blocked || running}
            onClick={() => act("create_workbook")}>
            <Play />Create workbook and calculate
          </Button>
          {!run.ready && <span className="text-xs text-muted-foreground">Run the take-off first.</span>}
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
