// WLCA window: draws the steps and results from the model Rhino sends, and sends edits / actions back.
// Drafted by an AI agent (Claude) - review before trusting.
//   page -> Rhino : host.postMessage(JSON) {type:"ready"} | {type:"set", path, value, kind} | {type:"action", name, args}
//   Rhino -> page : window.wlca.receive(model)  (wlca_web.py WLCAWebForm.model)
// All checks and calculations happen in Python / Excel; this file only draws and forwards.
(function () {
  "use strict";
  const { hbars, donut, bullet, fmt, sf, esc } = window.WlcaCharts;
  const host = window.chrome && window.chrome.webview ? window.chrome.webview : window.eto || null;
  let M = null;              // the latest model from Rhino
  let step = 0;              // page shown
  let sel = 0;               // option shown on the facade / structure pages
  let resTab = 0;            // option shown on the results page (-1 = compare)
  let busy = "";             // text shown while Rhino works on an action

  // ------------------------------------------------------------------ bridge
  function send(msg) {
    if (host) host.postMessage(JSON.stringify(msg));
    else console.log("[wlca] no host:", msg);
  }
  window.wlca = {
    receive(model) {
      M = model;
      busy = "";
      if (M.calc && M.calc.status === "done" && window.wlca._jumpToResults) { step = 6; window.wlca._jumpToResults = false; }
      render();
    },
    _jumpToResults: false,
  };
  function act(name, args, label) {
    busy = label || "";
    if (name === "create_workbook" || name === "calculate") window.wlca._jumpToResults = true;
    renderFooter();
    send({ type: "action", name, args: args || {} });
  }

  // ------------------------------------------------------------------ small builders
  const id = (path) => "f-" + path.join("-");
  const attrPath = (path) => esc(JSON.stringify(path));
  const S = () => M.state;
  function input(path, value, kind = "text", cls = "", extra = "") {
    const v = value == null ? "" : value;
    return `<input type="text" id="${id(path)}" class="${cls}" data-path="${attrPath(path)}" data-kind="${kind}" value="${esc(v)}" ${extra}>`;
  }
  function select(path, options, current, kind = "text", extra = "") {
    const opts = options.map((o) => (Array.isArray(o) ? o : [o, o]));
    const has = opts.some(([v]) => String(v) === String(current));
    let s = `<select id="${id(path)}" data-path="${attrPath(path)}" data-kind="${kind}" ${extra}>`;
    if (!has) s += `<option value="" selected>(choose)</option>`;
    for (const [v, l] of opts) s += `<option value="${esc(v)}"${String(v) === String(current) ? " selected" : ""}>${esc(l)}</option>`;
    return s + "</select>";
  }
  const check = (path, on, text) =>
    `<label class="check"><input type="checkbox" id="${id(path)}" data-path="${attrPath(path)}" data-kind="bool"${on ? " checked" : ""}>${esc(text)}</label>`;
  const button = (text, action, args, o = {}) =>
    `<button type="button" class="${o.primary ? "primary" : ""} ${o.cls || ""}" data-action="${action}" data-args="${esc(JSON.stringify(args || {}))}"${o.disabled ? " disabled" : ""}>${esc(text)}</button>`;
  const field = (label, control, o = {}) =>
    `<div class="field${o.wide ? " wide" : ""}"><label class="${o.req ? "req" : ""}" for="${o.for || ""}">${esc(label)}</label><div>${control}</div></div>`;
  const pct = (v) => (v == null ? "" : Math.round(v * 100) + "%");
  const numText = (v) => (v == null || v === "" ? "" : (Number(v) + 0).toLocaleString("en-GB", { maximumFractionDigits: 2 }));
  const note = (t) => `<p class="note">${esc(t)}</p>`;
  const keyNote = '<p class="key"><span class="req"></span> Fields marked * are needed to run the assessment; the rest have defaults or are optional.</p>';

  // ------------------------------------------------------------------ pages
  function pageProject() {
    const p = S().project, L = M.lists;
    let h = keyNote + "<h2>Project</h2><div class='grid'>";
    h += field("Project name", input(["project", "name"], p.name), { req: true, for: id(["project", "name"]) });
    h += field("Use class", select(["project", "use_class"], L.uses, p.use_class));
    h += field("RIBA stage", select(["project", "riba_stage"], L.stages, String(p.riba_stage), "int"));
    h += field("Construction start year", input(["project", "start_year"], p.start_year, "int", "num"));
    h += field("Existing GIA demolished (m²)", input(["project", "demolished_gia_m2"], numText(p.demolished_gia_m2), "num0", "num"));
    h += field("Assessor", input(["project", "assessor"], p.assessor));
    h += field("Estimated occupancy (people)", input(["project", "occupancy"], numText(p.occupancy), "num", "num"));
    h += field("Occupied days per year", input(["project", "occ_days"], numText(p.occ_days), "num", "num"));
    h += "</div>";
    h += note("Occupancy sets the project's water budget (B7) against the RIBA 2030 Climate Challenge potable water target: workplaces for offices, residents for homes, pupils for schools. Days default to 250 (office), 365 (homes), 190 (schools).");
    h += "<h2>Design options</h2>" + note("Each option is one massing layer in this file, or another .3dm. Facade and structure are set per option on steps 3 and 4, so options can share a massing.");
    h += "<table class='form' style='width:100%;max-width:1100px'><tr><th>Include</th><th class='req'>Option name</th><th>Massing from</th><th class='req'>Layer / file</th><th></th></tr>";
    S().options.forEach((o, i) => {
      const where = o.source === "layer"
        ? select(["options", i, "layer"], L.massing_layers, o.layer)
        : `<div class="row">${input(["options", i, "file"], o.file, "text", "fill")}${button("…", "pick_3dm", { i })}</div>`;
      h += `<tr><td>${check(["options", i, "include"], o.include, "")}</td><td style="width:200px">${input(["options", i, "name"], o.name)}</td>
        <td style="width:130px"><select data-act="option_source" data-i="${i}">${[["layer", "This file"], ["file", "Other .3dm"]].map(([v, l]) => `<option value="${v}"${o.source === v ? " selected" : ""}>${l}</option>`).join("")}</select></td>
        <td>${where}</td><td style="width:80px">${button("Remove", "remove_option", { i }, { disabled: S().options.length < 2 })}</td></tr>`;
    });
    h += "</table><div class='row' style='margin-top:8px'>" + button("+ Option", "add_option") + button("Duplicate last option", "duplicate_option") + "</div>";
    return h + note("Tick at least one option. Option names must be different from each other.");
  }

  function pageDrawings() {
    const s = S().schedule, pl = S().plan, L = M.lists;
    let h = "<h2>Area schedule</h2>" + note("Excel file with levels, GEA and GIA (optional: AOD, floor-to-floor, NIA, use). Without it, levels come from the massing and the storey heights.");
    h += `<div class="row" style="max-width:1100px">${input(["schedule", "path"], s.path, "text", "fill")}${button("Browse…", "pick_schedule")}<span style="width:160px">${select(["schedule", "sheet"], L.sheets.length ? L.sheets : [""], s.sheet)}</span></div>`;
    h += `<div class="msg ${M.schedule.level === "warn" ? "warn" : M.schedule.level === "good" ? "good" : "note"}">${esc(M.schedule.text)}</div>`;
    h += "<h2>Typical floor plan (cores, columns, stairs)</h2>";
    h += `<div class="row" style="max-width:420px"><select class="fill" data-act="plan_route">${L.plan_routes.map(([v, l]) => `<option value="${v}"${pl.route === v ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></div>`;
    if (pl.route === "pdf") {
      h += `<div class="row" style="max-width:1100px;margin-top:8px">${input(["plan", "pdf_json"], pl.pdf_json, "text", "fill")}${button("Browse…", "pick_plan_json")}</div>`;
      h += note("Output of the plan extractor (WLCA_plan_extract). Check its overlay image before using it.");
    } else if (pl.route === "rhino") {
      h += note("Import or paste the typical floor plan (DWG, DGN or .3dm linework) into this model at true scale - it can sit anywhere. The layers below fill themselves from the office layer names and the shapes on each layer; change one only if it is wrong. Walls and columns may share a layer.");
      const names = [["", "(none)"]].concat(L.all_layers.map((x) => [x, x]));
      h += "<div class='grid'>";
      for (const [k, lbl] of [["walls_layer", "Core walls"], ["columns_layer", "Columns"], ["stairs_layer", "Stairs"]])
        h += field(lbl, select(["plan", k], names, pl[k] || ""), { wide: true });
      h += "</div><div class='row' style='margin-top:8px'>" + button("Find layers again", "find_plan_layers", {}, {}) + button("Read plan", "read_plan", {}, { primary: true }) + "</div>";
      for (const line of pl.summary || []) h += `<div class="msg ${/^(No |Units)/.test(line) ? "warn" : "note"}">${esc(line)}</div>`;
    }
    return h;
  }

  function optionPicker() {
    const n = S().options.length;
    sel = Math.min(sel, n - 1);
    return `<div class="row" style="margin-bottom:6px"><label>Option</label><select data-ui="sel" style="width:260px">${S().options.map((o, i) => `<option value="${i}"${i === sel ? " selected" : ""}>${esc(o.name)}</option>`).join("")}</select></div>`;
  }

  function pageFacade() {
    const o = S().options[sel] || S().options[0], cat = M.lists.facade_types;
    const punched = o.facade.some((f) => f.kind !== "unitised");
    let h = keyNote + optionPicker() + "<h2>Facade types and their share</h2>";
    h += note("Up to three types; shares are of the whole net facade and must add up to 100%. Curtain-wall types carry their glazing in the system; other types take a glazing ratio.");
    h += `<table class="form" style="width:100%;max-width:1100px"><tr><th class="req">Type (from the office library)</th><th class="req">Share</th><th class="${punched ? "req" : ""}">Glazing ratio</th><th></th></tr>`;
    o.facade.forEach((f, j) => {
      const typeSel = `<select data-act="facade_type" data-i="${sel}" data-j="${j}">${cat.map((c) => `<option value="${esc(c.id)}"${c.id === f.build_up ? " selected" : ""}>${esc(c.label)} (${esc(c.code)})</option>`).join("")}</select>`;
      const wwr = f.kind === "unitised" ? '<span class="muted">in the system</span>' : input(["options", sel, "facade", j, "wwr"], pct(f.wwr), "pct", "num");
      h += `<tr><td>${typeSel}</td><td style="width:100px">${input(["options", sel, "facade", j, "share"], pct(f.share), "pct", "num")}</td><td style="width:120px">${wwr}</td>
        <td style="width:80px">${button("Remove", "remove_facade", { i: sel, j }, { disabled: o.facade.length < 2 })}</td></tr>`;
    });
    const tot = o.facade.reduce((a, f) => a + (Number(f.share) || 0), 0);
    h += `</table><div class="row" style="margin-top:8px">${button("+ Add a type", "add_facade", { i: sel }, { disabled: o.facade.length >= 3 })}
      <span class="${Math.abs(tot - 1) < 0.005 ? "chip meets" : "chip above"}">Shares add up to ${Math.round(tot * 100)}%</span></div>`;
    return h + note("The list shows the facade types in the office library. A new type is added to the library once and then appears here for every project.");
  }

  function pageStructure() {
    const o = S().options[sel] || S().options[0], s = o.structure;
    let h = optionPicker() + "<h2>Frame</h2><div class='grid'>";
    h += field("Frame system", select(["options", sel, "structure", "frame"], M.lists.frames, s.frame), { wide: true });
    h += "</div>" + note("Steel and timber frames use the PF Stage 1 rates per m² of floor; their columns are scaled with height (tagged [ASSUMED]). Cores stay RC.");
    h += "<div class='grid'>";
    h += field("Column grid x (m)", input(["options", sel, "structure", "grid_x_m"], s.grid_x_m, "num", "num"));
    h += field("Column grid y (m)", input(["options", sel, "structure", "grid_y_m"], s.grid_y_m, "num", "num"));
    h += field("Column size (m, square)", input(["options", sel, "structure", "column_size_m"], s.column_size_m, "num", "num"));
    h += "</div>";
    return h + note("Cores, columns and stairs come from the plan on step 2 when there is one; otherwise these values and the office defaults are used and the rows are tagged [ASSUMED] in the workbook. Foundations and basement walls use the office defaults (piles 750 mm, 3 per column, 25 m; secant wall + 200 RC liner) until the engineer's figures are entered.");
  }

  function pageTargets() {
    const t = S().targets, op = S().operational, L = M.lists;
    let h = keyNote + "<h2>Targets to compare against</h2><div>";
    h += check(["targets", "show", "UKNZCBS"], t.show.UKNZCBS, "UKNZCBS upfront limits (offices: shell & core limit)");
    h += check(["targets", "show", "LETI"], t.show.LETI, "LETI bands");
    h += check(["targets", "show", "RIBA"], t.show.RIBA, "RIBA 2030 Climate Challenge");
    h += check(["targets", "show", "GLA"], t.show.GLA, "GLA London Plan Guidance") + "</div>";
    h += "<h2>UKNZCBS offices</h2><div class='grid'>";
    for (const [k, lbl] of [["finishes", "Shell & core share - finishes"], ["ffe", "Shell & core share - FF&E"], ["services", "Shell & core share - services"]])
      h += field(lbl, input(["targets", "sc_share", k], pct(t.sc_share[k]), "pct", "num"));
    h += field("Cat B + loose FF&E (kgCO2e/m²)", input(["targets", "catb_allowance"], numText(t.catb_allowance), "num", "num"));
    h += "</div>" + note("Cat B blank = UKNZCBS whole-building limit not assessed.");
    h += "<h2>Scenario and budget</h2><div class='grid'>";
    h += field("Elements not yet designed - scenario", select(["targets", "scenario"], L.scenarios, t.scenario));
    h += field("Carbon budget against", select(["targets", "budget_target"], L.budgets, t.budget_target));
    h += "</div><h2>Operational energy and water (B6 / B7)</h2>";
    h += note("Whole life carbon needs a predictive energy model (CIBSE TM54 or equivalent - never Part L). Without one, the 'Indicative' basis uses each option's EUI estimate, else the UKNZCBS limit, x GIA (all electric).");
    const route = L.op_routes.indexOf(op.route) >= 0 ? op.route : (String(op.route || "").startsWith("Indicative") ? L.op_routes[1] : L.op_routes[2]);
    h += "<div class='grid'>";
    h += field("Basis", select(["operational", "route"], L.op_routes, route), { wide: true });
    h += field("First year of operation", input(["operational", "op_year"], op.op_year, "int", "num"));
    h += field("District heat factor (kgCO2e/kWh)", input(["operational", "dh_factor"], op.dh_factor || "", "num0", "num"));
    h += "</div>";
    const inc = S().options.map((o, i) => [o, i]).filter(([o]) => o.include);
    if (route !== "Not assessed" || inc.some(([o]) => Object.values(o.operational || {}).some((v) => v != null && v !== ""))) {
      const eng = route.startsWith("Engineer");
      h += "<table class='form' style='margin-top:10px'><tr><th>Per year</th>" + inc.map(([o]) => `<th style="width:130px;color:var(--ink);font-weight:600">${esc(o.name)}</th>`).join("") + "</tr>";
      for (const [k, lbl] of L.op_fields) {
        const r = eng && ["elec", "gas", "dh"].includes(k);
        h += `<tr><th class="${r ? "req" : ""}">${esc(lbl)}</th>` + inc.map(([o, i]) => `<td>${input(["options", i, "operational", k], numText((o.operational || {})[k]), "num", "num", 'style="width:120px"')}</td>`).join("") + "</tr>";
      }
      h += "</table>";
      if (eng) h += '<p class="note" style="color:var(--req)">* Engineer basis: at least one of grid electricity, gas or district heat for every option.</p>';
      h += note("Engineer basis: kWh from the energy model (TM54 mid-range). Indicative basis: only the EUI row is used (blank = UKNZCBS limit). Water from the public health engineer; blank = occupancy x RIBA 2025 target. PV used on site counts in the EUI at no carbon; PV exported is reported in D2.");
    }
    h += "<h2 class='req'>Where to save</h2>";
    h += `<div class="row" style="max-width:1100px">${input(["output", "folder"], S().output.folder, "text", "fill")}${button("Browse…", "pick_folder")}</div>`;
    return h + note("Take-off exports go to a 'takeoff' folder inside it; the workbook is saved there too. Everything set here is written into the workbook - nothing has to be typed in Excel.");
  }

  function pageRun() {
    const o = M.office, out = S().output;
    let h = "<h2>Office settings</h2>";
    h += `<div class="row" style="max-width:1100px"><span class="fill ${o.loaded ? "muted" : ""}" style="${o.loaded ? "" : "color:var(--warn)"};word-break:break-all">${esc(o.path || "(none)")}</span>${button("Choose…", "pick_office_settings")}${button("Use default", "reset_office_settings", {}, { disabled: o.source !== "chosen on this PC" })}</div>`;
    h += o.error ? `<div class="msg warn">${esc(o.error)}</div>` : note(`Library, benchmarks, targets and branding come from this file (${o.source}).`);
    h += "<h2>Checks</h2>";
    if (!M.checks.length) h += '<div class="msg good">Everything needed is filled in.</div>';
    for (const c of M.checks) h += `<div class="msg ${c.level === "error" ? "error" : "note"}">${c.level === "error" ? "Fix: " : "Note: "}${esc(c.text)}</div>`;
    h += "<h2>1  Take-off</h2>";
    h += `<div class="row">${button("Run take-off", "run_takeoff", {}, { primary: !M.run.ready, disabled: M.blocked })}<span class="muted">Measures every ticked option and draws floor plates and GIA curves on the WLCA layers for checking.</span></div>`;
    h += '<div class="msg warn">Before running, turn on the massing layers (step 1) and the plan layers (step 2), with their parent layers - the take-off and the plan reader skip anything on a layer that is off, and objects hidden with Hide (use Show first). Easiest: turn all layers on.</div>';
    if (M.layers_off.length) h += `<div class="row"><div class="msg warn fill">These layers are off now: ${esc(M.layers_off.join("; "))}</div>${button("Turn these layers on", "turn_layers_on")}</div>`;
    if (M.run.rows.length) {
      h += "<table class='data' style='margin-top:8px'><tr><th>Quantity</th>" + M.run.names.map((n) => `<th class="n">${esc(n)}</th>`).join("") + "</tr>";
      for (const r of M.run.rows) h += `<tr><td>${esc(r[0])}</td>${r.slice(1).map((v) => `<td class="n">${esc(v)}</td>`).join("")}</tr>`;
      h += "</table>";
    }
    for (const m of M.run.messages) h += `<div class="msg warn">${esc(m)}</div>`;
    h += "<h2>2  Workbook</h2><div class='grid'>";
    const fonts = M.lists.fonts || [];
    const missing = fonts.length && fonts.indexOf(out.font) < 0;
    h += field("Font", `<input type="text" style="max-width:260px" id="${id(["output", "font"])}" list="fontlist" data-path="${attrPath(["output", "font"])}" data-kind="text" value="${esc(out.font || "Arial")}">
      <datalist id="fontlist">${fonts.map((f) => `<option value="${esc(f)}">`).join("")}</datalist>
      <div class="small" style="color:${missing ? "var(--warn)" : "var(--muted)"}">${missing ? "Not installed on this PC - Excel will show a substitute" : "Used on every sheet, charts included"}</div>`, { wide: true });
    h += field("Company logo (optional)", `<div class="row">${input(["output", "logo"], M.logo.path, "text", "fill")}${button("Browse…", "pick_logo")}${button("No logo", "logo_none")}</div>`, { wide: true });
    h += "</div>";
    if (M.logo.url) h += `<img class="logo-preview" src="${esc(M.logo.url)}" alt="logo preview">`;
    else if (M.logo.path) h += '<div class="msg warn">Logo file not found.</div>';
    h += note("The logo goes at the top left of the Dashboard. The font is stored by name: people opening the workbook without it see Excel's substitute, so use a common font (Arial, Calibri) for files that leave the office.");
    h += `<div class="row">${button("Create workbook and calculate", "create_workbook", {}, { primary: M.run.ready, disabled: !M.run.ready || M.blocked || M.calc.status === "running" })}
      <span class="muted">Builds the Excel workbook, then Excel (hidden) calculates it and the results open here.</span></div>`;
    h += calcStatus();
    if (out.last_workbook) h += `<div class="row" style="margin-top:6px"><span class="fill small" style="color:var(--good);word-break:break-all">Saved: ${esc(out.last_workbook)}</span>${button("Open in Excel", "open_workbook")}${button("Open folder", "open_folder")}</div>`;
    return h;
  }

  function calcStatus() {
    const c = M.calc || {};
    if (c.status === "running") return `<div class="msg note"><span class="busy"></span>${esc(c.message)}</div>`;
    if (c.status === "failed") return `<div class="row"><div class="msg warn fill">${esc(c.message)}</div>${button("Calculate results", "calculate")}</div>`;
    return "";
  }

  // ------------------------------------------------------------------ results
  const BOUNDARY = { UP_X8: "A1-A5 excl. ext. works", UP_ALL: "A1-A5 all elements", UP_SC: "A1-A5 shell & core, excl. ext. works",
    UP_WB: "A1-A5 incl. Cat B + loose FF&E", AC_X8: "A-C excl. ext. works", AC_ALL: "A-C (excl. B6/B7)" };
  function palette() {
    const b = M.branding || {}, hx = (c, d) => "#" + String(c || d).replace("#", "");
    return {
      project: hx(b.project, "1F4E79"), target: hx(b.target, "7F2A3C"), cont: hx(b.contingency_bar, "8FB9BE"),
      modules: (b.modules || ["1F5F66", "5B8DB8", "2C4A68", "B8C4C8", "B5A82A"]).map((c) => hx(c)),
      groups: (b.groups || ["8C6D4F", "2F4F4F", "5B8DB8", "E07B1A", "7A3B5A", "79A88B", "D9534F", "9FB3BC"]).map((c) => hx(c)),
      basis: (b.basis || ["1F5F66", "E07B1A", "9FB3BC", "B8C4C8", "D9D2C5"]).map((c) => hx(c)),
    };
  }
  const chip = (v) => `<span class="chip ${{ Meets: "meets", "Meets before contingency only": "before", Above: "above" }[v] || "na"}">${esc(v)}</span>`;

  function pageResults() {
    const R = M.results;
    let h = "";
    if (!R) {
      h += "<h2>Results</h2>" + calcStatus();
      if (!(M.calc && M.calc.status)) h += note(S().output.last_workbook
        ? "The last workbook has not been calculated yet."
        : "Run the take-off and create the workbook on step 6 - the results then appear here.");
      if (S().output.last_workbook && M.calc.status !== "running") h += `<div class="row">${button("Calculate results", "calculate")}${button("Open in Excel", "open_workbook")}</div>`;
      return h;
    }
    const opts = R.options, sfN = (R.stage || 2) <= 2 ? 2 : 3;
    if (resTab >= opts.length) resTab = 0;
    h += '<div class="tabs">' + opts.map((o, i) => `<button type="button" data-ui="restab" data-i="${i}" class="${resTab === i ? "on" : ""}">${esc(o.values.NAME || "Option " + o.k)}</button>`).join("");
    if (opts.length > 1) h += `<button type="button" data-ui="restab" data-i="-1" class="${resTab === -1 ? "on" : ""}">Compare options</button>`;
    h += `<span class="grow"></span>${button("Open in Excel", "open_workbook")}${button("Recalculate", "calculate", {}, { disabled: M.calc.status === "running" })}</div>`;
    h += calcStatus();
    h += resTab === -1 ? compareView(R, sfN) : optionView(R, opts[resTab], sfN);
    h += note("Results are read from the calculated workbook (" + (R.workbook || "") + "). Building-level figures are shown to " + sfN + " significant figures (PS 6.1.4); all figures incl. the PS Table 10 contingency unless stated. The workbook holds every assumption and breakdown.");
    return h;
  }

  function optionView(R, o, sfN) {
    const v = o.values, P = palette();
    const tile = (t, val, unit, sub) => `<div class="tile"><div class="t">${esc(t)}</div><div class="v">${val == null ? "–" : fmt(sf(val, sfN))}</div><div class="u">${esc(unit)}${sub ? " · " + esc(sub) : ""}</div></div>`;
    let h = '<div class="tiles">';
    h += tile("Upfront carbon A1-A5", v.UP_ALL, "kgCO2e/m² GIA", v.UP_T != null ? fmt(sf(v.UP_T, sfN)) + " tCO2e" : "");
    h += tile("Embodied carbon A-C", v.AC_ALL, "kgCO2e/m² GIA", "excl. B6/B7");
    if (v.WLC_ND != null && (v.B6_ND || v.B7_ND)) {
      h += tile("Whole life carbon - non-decarbonised", v.WLC_ND, "kgCO2e/m² GIA", "A-C + B6 + B7");
      h += tile("Whole life carbon - decarbonised", v.WLC_D, "kgCO2e/m² GIA", "PS Table 15 / FES grid");
    }
    h += "</div>";
    if (v.QA_FLAGS) h += `<div class="msg warn">${fmt(v.QA_FLAGS)} QA flag(s) open - check sheet O${o.k}_QA in the workbook before using these figures.</div>`;
    // targets
    if (R.targets.length) {
      h += '<div class="card"><h2>Against targets</h2><table class="data"><tr><th>Target</th><th>Boundary</th><th class="n">Project incl. contingency</th><th class="n">Target</th><th class="n">Margin</th><th>Result</th><th></th></tr>';
      R.targets.forEach((t, i) => {
        const val = v[t.key], before = val == null ? null : val / (1 + R.cont), verdict = o.verdicts[i];
        h += `<tr><td>${esc(t.label)}</td><td class="muted">${esc(BOUNDARY[t.key] || t.key)}</td><td class="n">${val == null ? "–" : fmt(sf(val, sfN))}</td>
          <td class="n">${fmt(t.target)}</td><td class="n">${val == null ? "" : fmt(t.target - sf(val, sfN))}</td><td>${chip(verdict)}</td>
          <td>${bullet(before, val, t.target, { project: P.project, cont: P.cont, target: P.target })}</td></tr>`;
      });
      h += "</table>" + note("Targets are bare thresholds; the project figure includes the contingency, as the PS requires for reporting (4.10). Bar: project before contingency, contingency, and the target line.") + "</div>";
    }
    // charts
    h += '<div class="charts">';
    const basis = [["Modelled - project information", v.B_MOD], ["Modelled - assumed quantities", v.B_ASM], ["Benchmarked", v.B_BM], ["Site lumps (A5.1 / A5.2)", v.B_SITE], ["Contingency (PS Table 10)", v.B_CONT]]
      .map(([label, value], i) => ({ label, value, color: P.basis[i % P.basis.length] }));
    h += `<div class="card"><h2>Basis of A1-A5</h2>${donut(basis, { center: fmt(sf(v.UP_ALL, sfN)), unit: "kgCO2e/m²", title: "basis of the A1-A5 figure" })}
      ${note("How much of the upfront figure rests on project information, on assumed quantities, on benchmarks for elements not yet designed, on site lumps and on the contingency.")}</div>`;
    const mods = [["A1-A3 (product)", v.M_A13], ["A4 (transport)", v.M_A4], ["A5 (construction)", v.M_A5], ["B4 (replacement)", v.M_B4], ["C1-C4 (end of life)", v.M_C]]
      .map(([label, value], i) => ({ label, value, color: P.modules[i % P.modules.length] }));
    h += `<div class="card"><h2>By life-cycle module</h2>${hbars(mods, { unit: "kgCO2e/m²", title: "by life-cycle module" })}<p class="note">kgCO2e/m² GIA incl. contingency. D (memo, outside A-C): ${fmt(v.M_D)}.</p></div>`;
    const groups = M.group_labels.map((label, i) => ({ label, value: v["E_" + i], color: P.groups[i % P.groups.length] }));
    groups.push({ label: "Contingency", value: v.E_CONT, color: P.cont });
    h += `<div class="card"><h2>A1-A5 by element group</h2>${hbars(groups, { unit: "kgCO2e/m²", title: "A1-A5 by element group" })}<p class="note">kgCO2e/m² GIA, before contingency; contingency shown as its own bar.</p></div>`;
    if (v.WLC_ND != null && (v.B6_ND || v.B7_ND)) {
      h += `<div class="card"><h2>Operational and whole life</h2><table class="data"><tr><th>kgCO2e/m² GIA over the RSP</th><th class="n">Non-decarbonised</th><th class="n">Decarbonised</th></tr>
        <tr><td>Embodied A-C</td><td class="n">${fmt(sf(v.AC_ALL, sfN))}</td><td class="n">${fmt(sf(v.AC_DEC, sfN))}</td></tr>
        <tr><td>B6 operational energy</td><td class="n">${fmt(sf(v.B6_ND, sfN))}</td><td class="n">${fmt(sf(v.B6_D, sfN))}</td></tr>
        <tr><td>B7 operational water</td><td class="n">${fmt(v.B7_ND, 1)}</td><td class="n">${fmt(v.B7_D, 1)}</td></tr>
        <tr><td><b>Whole life A-C + B6 + B7</b></td><td class="n"><b>${fmt(sf(v.WLC_ND, sfN))}</b></td><td class="n"><b>${fmt(sf(v.WLC_D, sfN))}</b></td></tr></table>
        <p class="note">${esc(v.OP_STATUS || "")}${v.EUI != null ? ` · EUI ${fmt(v.EUI)} kWh/m²/yr${v.EUI_LIM ? " (UKNZCBS limit " + fmt(v.EUI_LIM) + ")" : ""}` : ""}</p></div>`;
    }
    h += "</div>";
    if (v.BIO_STORED) h += note(`Biogenic carbon stored in products: ${fmt(v.BIO_STORED)} kgCO2e/m² GIA (reported separately, not in A1-A5; released at end of life within A-C).`);
    return h;
  }

  function compareView(R, sfN) {
    const P = palette(), opts = R.options, names = opts.map((o) => o.values.NAME || "Option " + o.k);
    const rows = [["Upfront A1-A5", "UP_ALL"], ["Embodied A-C", "AC_ALL"], ["Embodied A-C decarbonised", "AC_DEC"],
      ["Whole life - non-decarbonised", "WLC_ND"], ["Whole life - decarbonised", "WLC_D"], ["EUI (kWh/m²/yr)", "EUI"], ["QA flags open", "QA_FLAGS"]];
    let h = '<div class="card"><h2>Options side by side</h2><table class="data"><tr><th>kgCO2e/m² GIA</th>' + names.map((n) => `<th class="n">${esc(n)}</th>`).join("") + "</tr>";
    for (const [lbl, k] of rows) {
      if (opts.every((o) => o.values[k] == null)) continue;
      h += `<tr><td>${esc(lbl)}</td>${opts.map((o) => `<td class="n">${o.values[k] == null ? "–" : fmt(k === "QA_FLAGS" || k === "EUI" ? o.values[k] : sf(o.values[k], sfN))}</td>`).join("")}</tr>`;
    }
    R.targets.forEach((t, i) => {
      h += `<tr><td class="muted">${esc(t.label)} (${fmt(t.target)})</td>${opts.map((o) => `<td class="n">${chip(o.verdicts[i])}</td>`).join("")}</tr>`;
    });
    h += "</table></div><div class='charts'>";
    for (const [lbl, k] of [["Upfront A1-A5", "UP_ALL"], ["Embodied A-C", "AC_ALL"]]) {
      const bars = opts.map((o, i) => ({ label: names[i], value: o.values[k], color: P.project }));
      h += `<div class="card"><h2>${esc(lbl)}</h2>${hbars(bars, { unit: "kgCO2e/m²", title: lbl, labelWidth: 170 })}<p class="note">kgCO2e/m² GIA incl. contingency.</p></div>`;
    }
    return h + "</div>";
  }

  // ------------------------------------------------------------------ frame
  const PAGES = [pageProject, pageDrawings, pageFacade, pageStructure, pageTargets, pageRun, pageResults];
  function stepFlags() {
    const flags = new Set();
    for (const c of M.checks) if (c.level === "error") { const m = /\(step (\d)\)/.exec(c.text); if (m) flags.add(Number(m[1]) - 1); }
    return flags;
  }
  function renderNav() {
    const flags = stepFlags();
    document.getElementById("nav").innerHTML = M.steps.map((s, i) =>
      (i === 6 ? "<hr>" : "") + `<button type="button" data-step="${i}" class="${i === step ? "on" : ""}"><span class="n">${i < 6 ? i + 1 : "◆"}</span>${esc(s)}${flags.has(i) ? '<span class="flag" title="Something to fix on this step"></span>' : ""}</button>`).join("")
      + '<hr><button type="button" data-action="classic" class="classic" title="The earlier Rhino dialog, same settings">Classic dialog</button>';
  }
  function renderFooter() {
    const st = document.getElementById("status");
    st.innerHTML = busy ? `<span class="busy"></span>${esc(busy)}` : M && M.calc && M.calc.status === "running" ? '<span class="busy"></span>Excel is calculating…' : "";
    document.getElementById("back").disabled = step === 0 || !!busy;
    document.getElementById("next").disabled = step === 6 || !!busy;
    document.querySelectorAll("#main button").forEach((b) => { if (busy) b.disabled = true; });
  }
  function render() {
    if (!M) return;
    document.title = M.title;
    // keep focus, caret and any text not yet sent while the page is redrawn
    const a = document.activeElement, keep = a && a.id && a.id.startsWith("f-") ? { id: a.id, value: a.value, s: a.selectionStart, e: a.selectionEnd } : null;
    const main = document.getElementById("main"), scroll = main.scrollTop;
    renderNav();
    let html;
    try { html = PAGES[step](); } catch (err) { html = `<div class="msg error">This page could not be drawn: ${esc(err && err.stack || err)}</div>`; }
    main.innerHTML = html;
    main.scrollTop = scroll;
    if (keep) {
      const el = document.getElementById(keep.id);
      if (el) { if (el.type === "text") el.value = keep.value; el.focus(); try { el.setSelectionRange(keep.s, keep.e); } catch (_) { /* selects */ } }
    }
    renderFooter();
  }
  function go(i) { step = Math.max(0, Math.min(6, i)); document.getElementById("main").scrollTop = 0; render(); }

  // ------------------------------------------------------------------ events
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t || t.disabled) return;
    if (t.dataset.step != null) return go(Number(t.dataset.step));
    if (t.id === "back") return go(step - 1);
    if (t.id === "next") return go(step + 1);
    if (t.dataset.ui === "restab") { resTab = Number(t.dataset.i); return render(); }
    if (t.dataset.action) {
      const labels = { run_takeoff: "Running the take-off in Rhino…", create_workbook: "Building the workbook…", read_plan: "Reading the plan…" };
      act(t.dataset.action, JSON.parse(t.dataset.args || "{}"), labels[t.dataset.action] || "Working…");
    }
  });
  document.addEventListener("change", (e) => {
    const t = e.target;
    if (t.dataset.ui === "sel") { sel = Number(t.value); return render(); }
    if (t.dataset.act === "option_source") return act("option_source", { i: Number(t.dataset.i), source: t.value });
    if (t.dataset.act === "plan_route") return act("plan_route", { route: t.value });
    if (t.dataset.act === "facade_type") return act("facade_type", { i: Number(t.dataset.i), j: Number(t.dataset.j), id: t.value });
    if (!t.dataset.path) return;
    const value = t.type === "checkbox" ? t.checked : t.value;
    send({ type: "set", path: JSON.parse(t.dataset.path), value, kind: t.dataset.kind || "text" });
  });
  document.addEventListener("keydown", (e) => {     // Enter commits a text field
    if (e.key === "Enter" && e.target.matches("input[type=text]")) e.target.blur();
  });

  send({ type: "ready" });
  if (!host) document.getElementById("main").innerHTML = '<p class="muted pad">Open this page from Rhino (WLCA command).</p>';
})();
