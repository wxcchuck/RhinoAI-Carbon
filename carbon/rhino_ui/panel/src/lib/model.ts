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
  }
  options: Option[]
  schedule: { path: string; sheet: string }
  plan: { route: string; walls_layer: string; columns_layer: string; stairs_layer: string; pdf_json: string; summary: string[] }
  output: { folder: string; last_workbook?: string; [k: string]: unknown }
  [k: string]: unknown
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
