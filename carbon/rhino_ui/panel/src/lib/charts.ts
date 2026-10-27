// Small SVG charts for the WLCA panel - no libraries, works offline. Drafted by an AI agent (Claude) - review before trusting.
// Ported from rhino_ui/web/charts.js (same geometry and rules); each returns an SVG string the page sets as markup.
// Text, grid and halo colours come from the theme (CSS variables, light and dark); data colours from the office branding.

export const esc = (s: unknown) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!)

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

// theme-driven strokes and fills (style attributes, so CSS variables apply)
const GRID = 'style="stroke:var(--chart-grid)"'
const AXIS = 'style="stroke:var(--chart-axis)" stroke-width="1.2"'
const HALO = "paint-order:stroke;stroke:var(--card);stroke-width:3px;stroke-linejoin:round"

/** "Nice" axis step for a maximum: 1, 2 or 5 x 10^n giving about `n` ticks. */
function niceStep(max: number, n = 5) {
  const raw = max / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p
}

const open = (W: number, H: number, title: string, fixed = false) =>
  `<svg class="wlca-chart" viewBox="0 0 ${W} ${H}" ${fixed ? `width="${W}" height="${H}"` : `width="100%" style="max-width:${W}px"`} role="img" aria-label="${esc(title)}">`

export type Bar = { label: string; value: number | null | undefined; color: string; sep?: boolean; muted?: boolean }

/** Horizontal bars, one value label per bar; negative values (module D) left of a zero line; sep starts a separated group. */
export function hbars(rows: Bar[], o: { unit?: string; title?: string; labelWidth?: number; max?: number } = {}) {
  const W = 420, labW = o.labelWidth || 140, valW = 48, rowH = 26, barH = 14, top = 4
  const max = Math.max(1e-9, ...rows.map((r) => Math.max(0, r.value || 0)), o.max || 0)
  const min = Math.min(0, ...rows.map((r) => Math.min(0, r.value || 0)))
  const plotW = W - labW - valW, k = plotW / (max - min), x0 = labW - min * k
  const H = top + rows.length * rowH + rows.filter((r) => r.sep).length * 8 + 4
  let s = open(W, H, o.title || "bar chart")
  let y = top
  rows.forEach((r) => {
    if (r.sep) {
      s += `<line x1="0" x2="${W}" y1="${y + 4}" y2="${y + 4}" ${GRID} stroke-dasharray="3 3"/>`
      y += 8
    }
    const v = r.value || 0, w = Math.max(v ? 2 : 0, Math.abs(v) * k), bx = v < 0 ? x0 - w : x0
    s += `<text class="lab" x="${labW - 8}" y="${y + rowH / 2 + 4}" text-anchor="end"${r.muted ? ' style="font-style:italic"' : ""}>${esc(r.label)}</text>`
    s += `<rect x="${bx}" y="${y + (rowH - barH) / 2}" width="${w}" height="${barH}" rx="2" fill="${r.color}"><title>${esc(r.label)}: ${fmt(r.value)} ${esc(o.unit || "")}</title></rect>`
    s += `<text class="val num" x="${(v < 0 ? x0 : x0 + w) + 6}" y="${y + rowH / 2 + 4}">${r.value == null ? "–" : fmt(r.value)}</text>`
    y += rowH
  })
  if (min < 0) s += `<line x1="${x0}" x2="${x0}" y1="${top}" y2="${H - 4}" style="stroke:var(--chart-axis)"/>`
  return s + "</svg>"
}

export type Part = { label: string; value: number | null | undefined; color: string }

/** Doughnut: parts [{label, value, color}]; centre text = total (the legend is drawn by the page). */
export function donut(parts: Part[], o: { center?: string; unit?: string; title?: string } = {}) {
  const R = 70, r = 46, C = 80, total = parts.reduce((a, p) => a + Math.max(0, p.value || 0), 0)
  let s = open(160, 160, o.title || "doughnut", true)
  let a0 = -Math.PI / 2
  const gap = parts.filter((p) => (p.value || 0) > 0).length > 1 ? 0.012 : 0
  parts.forEach((p) => {
    const v = Math.max(0, p.value || 0)
    if (!total || !v) return
    const a1 = a0 + (v / total) * 2 * Math.PI
    const s0 = a0 + gap, s1 = a1 - gap, large = s1 - s0 > Math.PI ? 1 : 0
    const pt = (rad: number, a: number) => `${C + rad * Math.cos(a)},${C + rad * Math.sin(a)}`
    const d = v === total
      ? `M${C},${C - R} A${R},${R} 0 1,1 ${C - 0.01},${C - R} L${C - 0.01},${C - r} A${r},${r} 0 1,0 ${C},${C - r} Z`
      : `M${pt(R, s0)} A${R},${R} 0 ${large},1 ${pt(R, s1)} L${pt(r, s1)} A${r},${r} 0 ${large},0 ${pt(r, s0)} Z`
    s += `<path d="${d}" fill="${p.color}"><title>${esc(p.label)}: ${fmt(v)} (${fmt((100 * v) / total)}%)</title></path>`
    a0 = a1
  })
  s += `<text class="num" x="${C}" y="${C - 2}" text-anchor="middle" style="font-size:20px;font-weight:600">${esc(o.center != null ? o.center : fmt(total))}</text>`
  s += `<text x="${C}" y="${C + 16}" text-anchor="middle" class="lab" style="font-size:11px">${esc(o.unit || "")}</text></svg>`
  return s
}

export type Line = { label: string; short?: string; value: number; color: string }
export type Col = { label: string; sub?: string; segs: Part[]; total: number | null; lines?: Line[] }

/**
 * Stacked columns against target lines (the "benchmarking" chart). Each column is one reporting boundary; its
 * target lines span that column only, because targets on different boundaries cannot share a line.
 */
export function targetColumns(cols: Col[], o: { unit?: string; title?: string; max?: number; height?: number } = {}) {
  const H = o.height || 330, left = 52, right = 8, top = 16, bottom = 58
  const W = Math.max(300, 150 * cols.length + left + right), plotH = H - top - bottom, plotW = W - left - right
  const peak = Math.max(1, o.max || 0, ...cols.map((c) => Math.max(c.total || 0, ...(c.lines || []).map((l) => l.value || 0))))
  const step = niceStep(peak * 1.08), ymax = Math.ceil((peak * 1.12) / step) * step
  const y = (v: number) => top + plotH - (Math.max(0, v) / ymax) * plotH
  let s = open(W, H, o.title || "project against targets")
  for (let t = 0; t <= ymax + 1e-9; t += step) {
    s += `<line x1="${left}" x2="${W - right}" y1="${y(t)}" y2="${y(t)}" ${GRID}/>`
    s += `<text class="lab num" x="${left - 6}" y="${y(t) + 4}" text-anchor="end" style="font-size:11px">${fmt(t)}</text>`
  }
  s += `<line x1="${left}" x2="${W - right}" y1="${y(0)}" y2="${y(0)}" ${AXIS}/>`
  const slot = plotW / cols.length, bw = Math.min(64, slot * 0.42)
  cols.forEach((c, i) => {
    const cx = left + slot * (i + 0.5), x0 = cx - bw / 2
    let acc = 0
    c.segs.forEach((g) => {
      const v = Math.max(0, g.value || 0)
      if (!v) return
      const y1 = y(acc + v), y0 = y(acc)
      s += `<rect x="${x0}" y="${y1}" width="${bw}" height="${Math.max(0.5, y0 - y1 - 1)}" fill="${g.color}"><title>${esc(g.label)}: ${fmt(v)} ${esc(o.unit || "")}</title></rect>`
      acc += v
    })
    if (c.total != null) s += `<text class="val num" x="${cx}" y="${y(c.total) - 6}" text-anchor="middle" style="font-size:12px;font-weight:600">${fmt(c.total)}</text>`
    const lines = (c.lines || []).slice().sort((a, b) => b.value - a.value)
    let lastY = -1e9
    lines.forEach((l) => {
      const ly = y(l.value), x1 = cx - slot * 0.46, x2 = cx + slot * 0.46
      s += `<line x1="${x1}" x2="${x2}" y1="${ly}" y2="${ly}" stroke="${l.color}" stroke-width="2" stroke-dasharray="6 4"><title>${esc(l.label)}: ${fmt(l.value)}</title></line>`
      const ty = Math.max(ly - 4, lastY + 12)
      s += `<text x="${x1}" y="${ty}" style="font-size:10.5px;fill:${l.color};font-weight:600;${HALO}">${esc(l.short || l.label)} ${fmt(l.value)}</text>`
      lastY = ty
    })
    s += `<text x="${cx}" y="${H - bottom + 16}" text-anchor="middle" style="font-size:11.5px;font-weight:600">${esc(c.label)}</text>`
    String(c.sub || "").split(" · ").forEach((t, j) => {
      s += `<text class="lab" x="${cx}" y="${H - bottom + 30 + 13 * j}" text-anchor="middle" style="font-size:10.5px">${esc(t)}</text>`
    })
  })
  s += `<text class="lab" transform="translate(11 ${top + plotH / 2}) rotate(-90)" text-anchor="middle" style="font-size:10.5px">${esc(o.unit || "")}</text>`
  return s + "</svg>"
}

export type Seg = { label: string; short?: string; value: number; color: string; ink?: string; text?: number }
export type StackCol = { label: string; sub?: string; segs: Seg[]; total: number | null; totalLabel?: string; weight?: number }

/** Stacked columns with labelled segments; negative segments hang below the axis (e.g. sequestered biogenic carbon). */
export function stackColumns(cols: StackCol[], o: { unit?: string; title?: string; height?: number } = {}) {
  const H = o.height || 380, left = 54, right = 70, top = 18, bottom = 46
  const wt = (c: StackCol) => c.weight || 1, slots = cols.reduce((a, c) => a + wt(c), 0)
  const W = Math.max(300, 230 * slots + left + right), plotW = W - left - right
  const pos = (c: StackCol) => c.segs.reduce((a, g) => a + Math.max(0, g.value || 0), 0)
  const neg = (c: StackCol) => c.segs.reduce((a, g) => a + Math.min(0, g.value || 0), 0)
  const hi = Math.max(1, ...cols.map(pos)), lo = Math.min(0, ...cols.map(neg))
  const step = niceStep((hi - lo) * 1.08), ymax = Math.ceil((hi * 1.1) / step) * step
  const fine = step / 5, ymin = lo < 0 ? -Math.max(fine, Math.ceil((-lo * 1.3) / fine) * fine) : 0
  const plotH = H - top - bottom, y = (v: number) => top + ((ymax - v) / (ymax - ymin)) * plotH
  let s = open(W, H, o.title || "stacked columns")
  for (let t = Math.ceil(ymin / step) * step; t <= ymax + 1e-9; t += step) {
    s += `<line x1="${left}" x2="${W - right}" y1="${y(t)}" y2="${y(t)}" ${GRID}/>`
    s += `<text class="lab num" x="${left - 6}" y="${y(t) + 4}" text-anchor="end" style="font-size:11px">${fmt(t + 0)}</text>`
  }
  s += `<line x1="${left}" x2="${W - right}" y1="${y(0)}" y2="${y(0)}" ${AXIS}/>`
  const slot = plotW / slots
  let at = 0
  cols.forEach((c) => {
    const bw = Math.min(124, slot * 0.52) * Math.min(1, wt(c) * 1.4), cx = left + slot * (at + wt(c) / 2), x0 = cx - bw / 2
    at += wt(c)
    let up = 0, down = 0
    c.segs.forEach((g) => {
      const v = g.value || 0
      if (!v) return
      const a = v > 0 ? up : down + v, b = v > 0 ? up + v : down
      const y1 = y(b), y0 = y(a), hgt = Math.max(0.5, y0 - y1 - 1)
      s += `<rect x="${x0}" y="${y1}" width="${bw}" height="${hgt}" fill="${g.color}"><title>${esc(g.label)}: ${fmt(v)} ${esc(o.unit || "")}</title></rect>`
      const shown = g.text != null ? g.text : v
      if (hgt >= 30) {
        s += `<text x="${cx}" y="${y1 + hgt / 2 - 2}" text-anchor="middle" style="font-size:11px;fill:${g.ink || "#fff"}">${esc(g.label)}</text>`
        s += `<text class="num" x="${cx}" y="${y1 + hgt / 2 + 12}" text-anchor="middle" style="font-size:11.5px;font-weight:600;fill:${g.ink || "#fff"}">${fmt(shown)}</text>`
      } else {
        s += `<text class="lab" x="${x0 + bw + 6}" y="${y1 + hgt / 2 + 4}" style="font-size:10.5px">${esc(g.short || g.label)} ${fmt(shown)}</text>`
      }
      if (v > 0) up += v
      else down += v
    })
    if (c.total != null) s += `<text class="val num" x="${cx}" y="${y(up) - 6}" text-anchor="middle" style="font-size:12px;font-weight:600">${esc(c.totalLabel || "")}${fmt(c.total)}</text>`
    s += `<text x="${cx}" y="${H - bottom + 18}" text-anchor="middle" style="font-size:11.5px;font-weight:600">${esc(c.label)}</text>`
    String(c.sub || "").split(" · ").forEach((t, j) => {
      if (t) s += `<text class="lab" x="${cx}" y="${H - bottom + 32 + 13 * j}" text-anchor="middle" style="font-size:10.5px">${esc(t)}</text>`
    })
  })
  s += `<text class="lab" transform="translate(11 ${top + plotH / 2}) rotate(-90)" text-anchor="middle" style="font-size:10.5px">${esc(o.unit || "")}</text>`
  return s + "</svg>"
}

export type Series = { label: string; color: string; x: number[]; y: (number | null)[]; dash?: boolean; dot?: boolean; width?: number; end?: boolean; endValue?: number | null }
export type Event = { x: number; label: string; title?: string }

/** Cumulative lines over years (the trajectory chart); events = dotted verticals labelled at the top. */
export function lineChart(series: Series[], events: Event[], o: { unit?: string; title?: string; x2?: (x: number) => string; width?: number; height?: number } = {}) {
  const W = o.width || 760, H = o.height || 340, left = 52, right = 16, top = 46, bottom = 44
  const xs = series.flatMap((s_) => s_.x), ys = series.flatMap((s_) => s_.y).filter((v): v is number => v != null)
  if (!xs.length || !ys.length) return ""
  const x0 = Math.min(...xs), x1 = Math.max(...xs), ymax0 = Math.max(1, ...ys), ymin0 = Math.min(0, ...ys)
  const step = niceStep(ymax0 - ymin0), ymax = Math.ceil((ymax0 * 1.05) / step) * step, ymin = ymin0 < 0 ? -Math.ceil(-ymin0 / step) * step : 0
  const px = (x: number) => left + ((x - x0) / Math.max(1e-9, x1 - x0)) * (W - left - right)
  const py = (v: number) => top + ((ymax - v) / (ymax - ymin)) * (H - top - bottom)
  let s = open(W, H, o.title || "trajectory")
  for (let t = ymin; t <= ymax + 1e-9; t += step) {
    s += `<line x1="${left}" x2="${W - right}" y1="${py(t)}" y2="${py(t)}" ${GRID}/>`
    s += `<text class="lab num" x="${left - 6}" y="${py(t) + 4}" text-anchor="end" style="font-size:11px">${fmt(t + 0)}</text>`
  }
  for (let x = x0; x <= x1; x += 10) {
    s += `<text class="lab num" x="${px(x)}" y="${H - bottom + 16}" text-anchor="middle" style="font-size:11px">${x}</text>`
    if (o.x2) s += `<text class="lab" x="${px(x)}" y="${H - bottom + 30}" text-anchor="middle" style="font-size:10px">${esc(o.x2(x))}</text>`
  }
  s += `<line x1="${left}" x2="${W - right}" y1="${py(0)}" y2="${py(0)}" ${AXIS}/>`
  const rowsEnd = [-1e9, -1e9, -1e9]
  ;(events || []).forEach((e) => {
    const ex = px(e.x)
    s += `<line x1="${ex}" x2="${ex}" y1="${top - 6}" y2="${py(ymin)}" style="stroke:var(--chart-event)" stroke-dasharray="2 3"/>`
    const w = 6.2 * e.label.length
    let row = rowsEnd.findIndex((end) => ex - w / 2 > end + 6)
    if (row < 0) row = 2
    rowsEnd[row] = ex + w / 2
    s += `<text class="lab" x="${ex}" y="${top - 30 + 12 * row}" text-anchor="middle" style="font-size:10px;font-weight:600;${HALO}">${esc(e.label)}<title>${esc(e.title || e.label)}</title></text>`
  })
  const ends: { y: number; x: number; c: string; t: string }[] = []
  series.forEach((sr) => {
    const pts = sr.x.map((x, i) => (sr.y[i] == null ? null : `${px(x).toFixed(1)},${py(sr.y[i] as number).toFixed(1)}`)).filter(Boolean).join(" ")
    s += `<polyline points="${pts}" fill="none" stroke="${sr.color}" stroke-width="${sr.width || 2}" ${sr.dot ? 'stroke-dasharray="1.5 3.5" stroke-linecap="round"' : sr.dash ? 'stroke-dasharray="7 4"' : ""}><title>${esc(sr.label)}</title></polyline>`
    const n = sr.y.length - 1
    if (sr.end !== false && sr.y[n] != null) ends.push({ y: py(sr.y[n] as number) - 6, x: px(sr.x[n]) - 2, c: sr.color, t: fmt(sr.endValue != null ? sr.endValue : sr.y[n]) })
  })
  ends.sort((a, b) => a.y - b.y)
  for (let i = 1; i < ends.length; i++) if (ends[i].y < ends[i - 1].y + 12) ends[i].y = ends[i - 1].y + 12
  ends.forEach((e) => {
    s += `<text class="num" x="${e.x}" y="${e.y}" text-anchor="end" style="font-size:11px;font-weight:600;fill:${e.c};${HALO}">${e.t}</text>`
  })
  s += `<text class="lab" transform="translate(12 ${top + (H - top - bottom) / 2}) rotate(-90)" text-anchor="middle" style="font-size:10.5px">${esc(o.unit || "")}</text>`
  return s + "</svg>"
}

/** One project-vs-target strip: project bar (before + contingency) and a target tick. */
export function bullet(before: number, incl: number | null, target: number, o: { project: string; cont: string; target: string }) {
  const W = 180, H = 18, max = Math.max(incl || 0, target || 0) * 1.1 || 1, x = (v: number) => (v / max) * W
  let s = open(W, H, "project against target", true)
  if (incl != null) {
    s += `<rect x="0" y="4" width="${x(before)}" height="10" fill="${o.project}"><title>Before contingency ${fmt(before)}</title></rect>`
    s += `<rect x="${x(before)}" y="4" width="${Math.max(0, x(incl) - x(before))}" height="10" fill="${o.cont}"><title>Contingency ${fmt(incl - before)}</title></rect>`
  }
  s += `<rect x="${x(target) - 1}" y="0" width="2.5" height="${H}" fill="${o.target}"><title>Target ${fmt(target)}</title></rect>`
  return s + "</svg>"
}

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
