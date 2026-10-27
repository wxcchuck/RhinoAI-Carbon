// Results read from the calculated workbook (wlca_results.read_results) and what the Results page derives from them.
// Drafted by an AI agent (Claude) - review before trusting.
import { useEffect, useState } from "react"

export type Values = Record<string, number | string | null | undefined> & { NAME?: string }
export type Traj = {
  t: number[]; year: number[]; emb_nd: number[]; emb_d: number[]; wlc_nd: number[]; wlc_d: number[]
  bio: number[] | null; b4: number[][]
}
export type ResOption = { k: number; values: Values; traj: Traj | null; verdicts: string[] }
export type Target = { label: string; key: string; target: number }
export type Results = {
  calculated: boolean; cont: number; stage: number; sc: { fin: number; ffe: number; mep: number }; catb: number | null
  options: ResOption[]; targets: Target[]; workbook: string
}

/** A number from the results, or undefined. */
export const n = (v: Values, k: string): number | undefined => (typeof v[k] === "number" ? (v[k] as number) : undefined)

export const BOUNDARY: Record<string, string> = {
  UP_X8: "A1-A5 excl. ext. works", UP_ALL: "A1-A5 all elements", UP_SC: "A1-A5 shell & core, excl. ext. works",
  UP_WB: "A1-A5 incl. Cat B + loose FF&E", AC_X8: "A-C excl. ext. works", AC_ALL: "A-C (excl. B6/B7)",
}

export type Palette = {
  project: string; target: string; cont: string; target_ac: string; stages: string[]; module_d: string
  modules: string[]; b23: string[]; groups: string[]; basis: string[]
}

/** Chart colours: the office branding (office settings), else the defaults the workbook Dashboard uses. */
export function palette(b: Record<string, unknown> = {}): Palette {
  const hx = (c: unknown, d: string) => "#" + String(c || d).replace("#", "")
  const list = (k: string, d: string[]) => ((b[k] as string[] | undefined) || d).map((c) => hx(c, c))
  return {
    project: hx(b.project, "1F4E79"), target: hx(b.target, "7F2A3C"), cont: hx(b.contingency_bar, "8FB9BE"),
    target_ac: hx(b.target_lifecycle, "C2600F"),
    stages: list("stages", ["1F4E79", "5B8DB8", "E3B448", "6BAA75"]),          // upfront, B-C, operational, sequestered
    module_d: hx(b.module_d, "8C9A9E"),
    modules: list("modules", ["1F5F66", "5B8DB8", "2C4A68", "B8C4C8", "B5A82A"]), // A1-A3, A4, A5, B4, C1-C4
    b23: list("modules_b23", ["C98A3E", "E6C190"]),                              // B2, B3
    groups: list("groups", ["8C6D4F", "2F4F4F", "5B8DB8", "E07B1A", "7A3B5A", "79A88B", "D9534F", "9FB3BC"]),
    basis: list("basis", ["1F5F66", "E07B1A", "9FB3BC", "B8C4C8", "D9D2C5"]),
  }
}

export const OPTION_COLOURS = ["#1F4E79", "#E07B1A", "#4F9A8C", "#7A3B5A", "#B5A82A", "#5B8DB8"]

/** UI choices on the Results page that should survive leaving the page and coming back (not saved with the model). */
const sticky = new Map<string, unknown>()
export function useSticky<T>(key: string, init: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => (sticky.has(key) ? (sticky.get(key) as T) : init))
  return [v, (x: T) => { sticky.set(key, x); setV(x) }]
}

/** True while the panel shows the dark theme (follows the class the theme switch sets). */
export function useDark() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"))
  useEffect(() => {
    const ob = new MutationObserver(() => setDark(document.documentElement.classList.contains("dark")))
    ob.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] })
    return () => ob.disconnect()
  }, [])
  return dark
}
