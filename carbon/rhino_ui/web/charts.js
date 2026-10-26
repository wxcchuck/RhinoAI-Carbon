// Small SVG charts for the WLCA window - no libraries, works offline.
// Drafted by an AI agent (Claude) - review before trusting.
(function () {
  "use strict";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (v, d = 0) => (v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d }));
  // significant figures (PS 6.1.4: building-level results to 2 s.f. at RIBA 0-2, 3 s.f. from RIBA 3)
  function sf(v, n) {
    if (v == null || isNaN(v) || v === 0) return v;
    const p = Math.pow(10, n - Math.ceil(Math.log10(Math.abs(v))));
    return Math.round(v * p) / p;
  }

  /** Horizontal bars: rows [{label, value, color, note}], one value label per bar. */
  function hbars(rows, o = {}) {
    const W = 420, labW = o.labelWidth || 140, valW = 48, rowH = 26, barH = 14, top = 4;   // drawn near 1:1 in a card
    const max = Math.max(1e-9, ...rows.map((r) => Math.max(0, r.value || 0)), o.max || 0);
    const plotW = W - labW - valW;
    const H = top + rows.length * rowH + 4;
    let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="${esc(o.title || "bar chart")}">`;
    rows.forEach((r, i) => {
      const y = top + i * rowH, v = Math.max(0, r.value || 0), w = Math.max(v > 0 ? 2 : 0, (v / max) * plotW);
      s += `<text class="lab" x="${labW - 8}" y="${y + rowH / 2 + 4}" text-anchor="end">${esc(r.label)}</text>`;
      s += `<rect x="${labW}" y="${y + (rowH - barH) / 2}" width="${w}" height="${barH}" rx="2" fill="${r.color}"><title>${esc(r.label)}: ${fmt(r.value)} ${esc(o.unit || "")}</title></rect>`;
      s += `<text class="val" x="${labW + w + 6}" y="${y + rowH / 2 + 4}">${r.value == null ? "–" : fmt(r.value)}</text>`;
    });
    if (o.marker) {   // a target line across the bars
      const x = labW + (o.marker.value / max) * plotW;
      s += `<line x1="${x}" x2="${x}" y1="0" y2="${H}" stroke="${o.marker.color}" stroke-width="2" stroke-dasharray="4 3"><title>${esc(o.marker.label)}</title></line>`;
    }
    return s + "</svg>";
  }

  /** Doughnut with a legend: parts [{label, value, color}]; centre text = total. */
  function donut(parts, o = {}) {
    const R = 70, r = 46, C = 80, total = parts.reduce((a, p) => a + Math.max(0, p.value || 0), 0);
    let s = `<svg viewBox="0 0 160 160" width="160" height="160" role="img" aria-label="${esc(o.title || "doughnut")}">`;
    let a0 = -Math.PI / 2;
    const gap = parts.filter((p) => p.value > 0).length > 1 ? 0.012 : 0;   // a thin surface gap between segments
    parts.forEach((p) => {
      const v = Math.max(0, p.value || 0);
      if (!total || !v) return;
      const a1 = a0 + (v / total) * 2 * Math.PI;
      const s0 = a0 + gap, s1 = a1 - gap, large = s1 - s0 > Math.PI ? 1 : 0;
      const pt = (rad, a) => `${C + rad * Math.cos(a)},${C + rad * Math.sin(a)}`;
      const d = v === total
        ? `M${C},${C - R} A${R},${R} 0 1,1 ${C - 0.01},${C - R} L${C - 0.01},${C - r} A${r},${r} 0 1,0 ${C},${C - r} Z`
        : `M${pt(R, s0)} A${R},${R} 0 ${large},1 ${pt(R, s1)} L${pt(r, s1)} A${r},${r} 0 ${large},0 ${pt(r, s0)} Z`;
      s += `<path d="${d}" fill="${p.color}"><title>${esc(p.label)}: ${fmt(v)} (${fmt((100 * v) / total)}%)</title></path>`;
      a0 = a1;
    });
    s += `<text x="${C}" y="${C - 2}" text-anchor="middle" style="font-size:20px;font-weight:600">${esc(o.center != null ? o.center : fmt(total))}</text>`;
    s += `<text x="${C}" y="${C + 16}" text-anchor="middle" class="lab" style="font-size:11px">${esc(o.unit || "")}</text></svg>`;
    let leg = '<div class="legend">';
    parts.forEach((p) => {
      const pc = total ? (100 * Math.max(0, p.value || 0)) / total : 0;
      leg += `<div><span class="sw" style="background:${p.color}"></span>${esc(p.label)} <span class="lv">${fmt(p.value)} · ${fmt(pc)}%</span></div>`;
    });
    return `<div class="donut-wrap">${s}${leg}</div></div>`;
  }

  /** One project-vs-target strip for the targets table: project bar (before + contingency) and a target tick. */
  function bullet(before, incl, target, o = {}) {
    const W = 180, H = 18, max = Math.max(incl || 0, target || 0) * 1.1 || 1, x = (v) => (v / max) * W;
    let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="project against target">`;
    if (incl != null) {
      s += `<rect x="0" y="4" width="${x(before)}" height="10" fill="${o.project}"><title>Before contingency ${fmt(before)}</title></rect>`;
      s += `<rect x="${x(before)}" y="4" width="${Math.max(0, x(incl) - x(before))}" height="10" fill="${o.cont}"><title>Contingency ${fmt(incl - before)}</title></rect>`;
    }
    s += `<rect x="${x(target) - 1}" y="0" width="2.5" height="${H}" fill="${o.target}"><title>Target ${fmt(target)}</title></rect>`;
    return s + "</svg>";
  }

  /** "Nice" axis step for a maximum: 1, 2 or 5 x 10^n giving about `n` ticks. */
  function niceStep(max, n = 5) {
    const raw = max / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
  }

  /**
   * Stacked columns against target lines (the "benchmarking" chart).
   * cols  [{label, sub, segs: [{label, value, color}], total, lines: [{label, value, color}]}]
   *       Each column is one reporting boundary; its target lines span that column only, because targets on
   *       different boundaries cannot share a line.
   * o     {unit, title, max, height}
   */
  function targetColumns(cols, o = {}) {
    const H = o.height || 330, left = 44, right = 8, top = 16, bottom = 58;
    const W = Math.max(300, 150 * cols.length + left + right), plotH = H - top - bottom, plotW = W - left - right;
    const peak = Math.max(1, o.max || 0, ...cols.map((c) => Math.max(c.total || 0, ...(c.lines || []).map((l) => l.value || 0))));
    const step = niceStep(peak * 1.08), ymax = Math.ceil((peak * 1.12) / step) * step;
    const y = (v) => top + plotH - (Math.max(0, v) / ymax) * plotH;
    let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="${esc(o.title || "project against targets")}">`;
    for (let t = 0; t <= ymax + 1e-9; t += step) {             // recessive grid
      s += `<line x1="${left}" x2="${W - right}" y1="${y(t)}" y2="${y(t)}" stroke="#e3e3e3" stroke-width="1"/>`;
      s += `<text class="lab" x="${left - 6}" y="${y(t) + 4}" text-anchor="end" style="font-size:11px">${fmt(t)}</text>`;
    }
    s += `<line x1="${left}" x2="${W - right}" y1="${y(0)}" y2="${y(0)}" stroke="#555" stroke-width="1.2"/>`;
    const slot = plotW / cols.length, bw = Math.min(64, slot * 0.42);
    cols.forEach((c, i) => {
      const cx = left + slot * (i + 0.5), x0 = cx - bw / 2;
      let acc = 0;
      c.segs.forEach((g) => {                                  // stack from the baseline; a 1 px surface gap between fills
        const v = Math.max(0, g.value || 0);
        if (!v) return;
        const y1 = y(acc + v), y0 = y(acc);
        s += `<rect x="${x0}" y="${y1}" width="${bw}" height="${Math.max(0.5, y0 - y1 - 1)}" fill="${g.color}"><title>${esc(g.label)}: ${fmt(v)} ${esc(o.unit || "")}</title></rect>`;
        acc += v;
      });
      if (c.total != null) s += `<text class="val" x="${cx}" y="${y(c.total) - 6}" text-anchor="middle" style="font-size:12px;font-weight:600">${fmt(c.total)}</text>`;
      // target lines across this column's slot, labels on the left, nudged apart when two are close
      const lines = (c.lines || []).slice().sort((a, b) => b.value - a.value);
      let lastY = -1e9;
      lines.forEach((l) => {
        const ly = y(l.value), x1 = cx - slot * 0.46, x2 = cx + slot * 0.46;
        s += `<line x1="${x1}" x2="${x2}" y1="${ly}" y2="${ly}" stroke="${l.color}" stroke-width="2" stroke-dasharray="6 4"><title>${esc(l.label)}: ${fmt(l.value)}</title></line>`;
        const ty = Math.max(ly - 4, lastY + 12);
        s += `<text x="${x1}" y="${ty}" style="font-size:10.5px;fill:${l.color};font-weight:600;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round">${esc(l.short || l.label)} ${fmt(l.value)}</text>`;
        lastY = ty;
      });
      s += `<text x="${cx}" y="${H - bottom + 16}" text-anchor="middle" style="font-size:11.5px;font-weight:600">${esc(c.label)}</text>`;
      String(c.sub || "").split(" · ").forEach((t, j) => {
        s += `<text class="lab" x="${cx}" y="${H - bottom + 30 + 13 * j}" text-anchor="middle" style="font-size:10.5px">${esc(t)}</text>`;
      });
    });
    s += `<text class="lab" transform="translate(11 ${top + plotH / 2}) rotate(-90)" text-anchor="middle" style="font-size:10.5px">${esc(o.unit || "")}</text>`;
    return s + "</svg>";
  }

  /** Legend for stacked segments: [{label, color}] (one entry per distinct label, in order). */
  function legend(items) {
    const seen = new Set();
    let h = '<div class="legend inline">';
    items.forEach((it) => {
      if (seen.has(it.label)) return;
      seen.add(it.label);
      h += `<span><span class="sw" style="background:${it.color}"></span>${esc(it.label)}</span>`;
    });
    return h + "</div>";
  }

  window.WlcaCharts = { hbars, donut, bullet, targetColumns, legend, fmt, sf, esc };
})();
