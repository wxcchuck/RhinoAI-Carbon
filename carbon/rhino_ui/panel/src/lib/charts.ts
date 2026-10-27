// Chart helpers and data shapes for the WLCA panel. Drafted by an AI agent (Claude) - review before trusting.
// The charts themselves are shadcn/ui charts (Recharts): components/charts.tsx (bars, doughnut) and
// components/charts-rich.tsx (against targets, whole life by stage, trajectory). The shapes below are the ones the
// SVG charts of rhino_ui/web/charts.js took, so the cards build the same data as the classic panel.

export const fmt = (v: unknown, d = 0) =>
  v == null || typeof v !== "number" || isNaN(v) ? "–"
    : (v + 0).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d })

/** Significant figures (PS 6.1.4: building-level results to 2 s.f. at RIBA 0-2, 3 s.f. from RIBA 3). */
export function sf(v: number, n: number): number
export function sf(v: number | null | undefined, n: number): number | null | undefined
export function sf(v: number | null | undefined, n: number) {
  if (v == null || isNaN(v) || v === 0) return v
  const p = Math.pow(10, n - Math.ceil(Math.log10(Math.abs(v))))
  return Math.round(v * p) / p
}

export type Part = { label: string; value: number | null | undefined; color: string }

export type Line = { label: string; short?: string; value: number; color: string }
export type Col = { label: string; sub?: string; segs: Part[]; total: number | null; lines?: Line[] }

export type Seg = { label: string; short?: string; value: number; color: string; ink?: string; text?: number }
export type StackCol = { label: string; sub?: string; segs: Seg[]; total: number | null; totalLabel?: string; weight?: number }

export type Series = { label: string; color: string; x: number[]; y: (number | null)[]; dash?: boolean; dot?: boolean; width?: number; end?: boolean; endValue?: number | null }
export type Event = { x: number; label: string; title?: string }

/** Lighten a colour for lines and coloured text on the dark theme (fills keep the office colours). */
export function forDark(hex: string, dark: boolean) {
  if (!dark) return hex
  const h = hex.replace("#", "")
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
  if (lum >= 0.45) return hex
  const t = Math.min(0.65, 0.45 - lum + 0.25)          // mix toward white just enough to read on the dark card
  const mix = (c: number) => Math.round((c + (1 - c) * t) * 255).toString(16).padStart(2, "0")
  return "#" + mix(r) + mix(g) + mix(b)
}
