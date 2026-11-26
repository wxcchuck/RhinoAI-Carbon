// The model Rhino sends (wlca_web.py WLCAWindow.model) and the saved settings inside it (wlca_state.py).
// Drafted by an AI agent (Claude) - review before trusting. Only the parts the panel reads are typed.

export type Option = {
  name: string
  include: boolean
  source: "layer" | "file"
  layer: string
  file: string
  // later steps (substructure, structure, facade, operational) are drawn by the current panel for now
  [k: string]: unknown
}

export type State = {
  project: {
    name: string
    use_class: string
    riba_stage: number
    start_year: number | null
    demolished_gia_m2: number | null
    assessor: string
    occupancy: number | null
    occ_days: number | null
    scopes?: Partial<Record<ScopeKey, boolean>>
    /** Reporting method (D21): RICS PS edition of the headline. Targets are judged on their own scheme's edition. */
    rics_edition?: 1 | 2
  }
  options: Option[]
  schedule: { path: string; sheet: string }
  plan: { route: string; walls_layer: string; columns_layer: string; stairs_layer: string; pdf_json: string; summary: string[] }
  output: { folder: string; last_workbook?: string; [k: string]: unknown }
  [k: string]: unknown
}

/** Scope of assessment (step 1): upfront A1-A5, life cycle embodied A-C excl. B6 & B7, whole life A-C. One or more. */
export type ScopeKey = "upfront" | "embodied" | "wlc"
export type Scope = { up: boolean; emb: boolean; wlc: boolean; ac: boolean }

/** The ticked scopes; ac = any scope that reports A-C (life cycle embodied or whole life). A state without scopes shows everything. */
export function scopeOf(m: { state: State }): Scope {
  const sc = m.state.project.scopes
  if (!sc) return { up: true, emb: true, wlc: true, ac: true }
  const up = !!sc.upfront, emb = !!sc.embodied, wlc = !!sc.wlc
  return { up, emb, wlc, ac: emb || wlc }
}

/** RICS PS edition the headline is reported on: 2 = 2nd (incl. contingency), 1 = 1st (2017: no contingency, demolition separate). */
export function editionOf(m: { state: State }): 1 | 2 {
  return String(m.state.project.rics_edition ?? 2) === "1" ? 1 : 2
}

export type Check = { level: "error" | "note"; text: string }

export type Model = {
  type: "model"
  title: string
  steps: string[]
  state: State
  lists: {
    uses: string[]
    stages: string[]
    massing_layers: string[]
    all_layers: string[]
    sheets: string[]
    plan_routes: [string, string][]
    [k: string]: unknown
  }
  office: { path?: string; source?: string; loaded: boolean; error?: string | null }
  schedule: { text: string; level: "good" | "warn" | "muted" }
  checks: Check[]
  blocked: boolean
  calc: { status: "" | "running" | "done" | "failed"; message: string }
  results: unknown
  ui?: { current?: string; package?: string }
  [k: string]: unknown
}

/** Steps flagged by the checks: "... (step 3)" in an error text marks step index 2. */
export function stepFlags(m: Model): Set<number> {
  const flags = new Set<number>()
  for (const c of m.checks) {
    if (c.level !== "error") continue
    const hit = /\(step (\d)\)/.exec(c.text)
    if (hit) flags.add(Number(hit[1]) - 1)
  }
  return flags
}

export const numText = (v: unknown) =>
  v == null || v === "" ? "" : (Number(v) + 0).toLocaleString("en-GB", { maximumFractionDigits: 2 })

/** Figures as the current panel shows them: en-GB grouping, up to `d` decimals. */
export const fmt = (v: unknown, d = 0) =>
  typeof v === "number" && isFinite(v) ? (v + 0).toLocaleString("en-GB", { maximumFractionDigits: d }) : "–"   // + 0: no "-0"

/** A share as typed into a % field (Rhino parses "60%" or "60" back to 0.6). */
export const pct = (v: unknown) => (v == null || v === "" ? "" : Math.round(Number(v) * 100) + "%")

/** Props every step page gets: the model and the option shown on the per-option steps (3 to 5). */
export type PageProps = { m: Model; sel: number; setSel: (i: number) => void; goTo: (step: number) => void }
