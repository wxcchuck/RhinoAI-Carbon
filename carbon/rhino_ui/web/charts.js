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

  window.WlcaCharts = { hbars, donut, bullet, fmt, sf, esc };
})();
