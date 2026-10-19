"""
WLCA dialog - state, office settings and config builders  v0.1  (draft for review)

Drafted by an AI agent (Claude) - review before trusting.

Plain Python (no Rhino), so it can be unit-tested. The Rhino dialog (wlca_dialog.py) edits a `state`
dict, saves it in the .3dm, and uses the functions here to
  - check it                    validate(state)
  - build one take-off CONFIG   takeoff_config(state, option, office, base_config)
  - build the workbook config   calc_config(state, office, exports)

Office settings (library, benchmarks, targets, branding, site lumps, defaults) live in one JSON file kept
by the carbon team; relative paths in it are resolved against the file's own folder, so the same file works
from everyone's OneDrive.
"""
import copy
import json
import os

STATE_KEY = "WLCA_STATE_V1"          # document user-text key the dialog saves under
MAX_FACADE_TYPES = 3

FACADE_UNITISED = "unitised"         # glazing is part of the system (whole share routed to the CW build-up)
FACADE_PUNCHED = "punched"           # opaque wall with windows at the type's glazing ratio


def default_state():
    return {
        "version": 1,
        "project": {"name": "", "use_class": "Office", "riba_stage": 2, "start_year": 2027,
                    "demolished_gia_m2": 0.0, "assessor": "", "occupancy": None, "occ_days": None},
        "options": [],
        "schedule": {"path": "", "sheet": ""},
        # plan route (D5): "rhino" = typical floor read from Rhino layers (default), "pdf" = plan extract json, "none"
        "plan": {"route": "rhino", "walls_layer": "", "columns_layer": "", "stairs_layer": "", "pdf_json": "",
                 "json": "", "summary": []},
        "targets": {"show": {"UKNZCBS": True, "LETI": True, "RIBA": True, "GLA": True},
                    "sc_share": {"finishes": 1.0, "ffe": 1.0, "services": 1.0},
                    "catb_allowance": None, "scenario": "GLA aspirational", "budget_target": "UKNZCBS"},
        "output": {"folder": "", "workbook": ""},
        # B6 / B7 (PS 5.3 / 5.4): basis for the whole building; energy and water per option
        "operational": {"route": "Not assessed", "op_year": None, "dh_factor": 0.0},
    }


def default_option(name, layer="", source="layer", file_path=""):
    return {
        "name": name, "include": True, "source": source, "layer": layer, "file": file_path,
        "facade": [{"build_up": "CW-UNIT-01", "kind": FACADE_UNITISED, "share": 1.0, "wwr": None}],
        "structure": {"frame": "RC flat slab", "grid_x_m": 9.0, "grid_y_m": 8.0, "column_size_m": 0.75,
                      "sources": {}},
        "operational": {"elec": None, "gas": None, "dh": None, "pv_self": None, "pv_export": None, "water": None, "eui": None},
    }


# ------------------------------------------------------------------------------------- office settings
def load_office(path):
    """Read the office settings JSON and resolve relative paths against its folder."""
    with open(path, encoding="utf-8") as f:
        office = json.load(f)
    base = os.path.dirname(os.path.abspath(path))

    def res(p):
        return p if not p or os.path.isabs(p) else os.path.normpath(os.path.join(base, p))
    office["library_xlsx"] = res(office.get("library_xlsx"))
    office["targets_xlsx"] = res(office.get("targets_xlsx"))
    if office.get("benchmarks"):
        office["benchmarks"]["path"] = res(office["benchmarks"].get("path"))
    if (office.get("branding") or {}).get("logo"):
        office["branding"]["logo"] = res(office["branding"]["logo"])
    office["_path"] = os.path.abspath(path)
    return office


def facade_catalogue(office):
    """Facade types offered in the dialog: [{id, code, label, kind, glazing_build_up?}] from the office settings.
    `code` is the wall's build-up; `id` (default = code) tells types apart that share a wall but not a window,
    e.g. brick on SFS with aluminium or with timber-aluminium windows. Options store the id."""
    cat = [dict(f) for f in (office.get("facade_types") or [
        {"code": "CW-UNIT-01", "label": "Unitised curtain wall", "kind": FACADE_UNITISED},
        {"code": "EW-SFS-BRK-01", "label": "SFS + brick, punched windows", "kind": FACADE_PUNCHED},
    ])]
    for f in cat:
        f.setdefault("id", f["code"])
    return cat


# ------------------------------------------------------------------------------------- state I/O
def dumps(state):
    return json.dumps(state, sort_keys=True)


def loads(text):
    """State from the .3dm; missing keys are filled from the defaults so older saves keep working."""
    st = default_state()
    if not text:
        return st
    saved = json.loads(text)
    for k, v in saved.items():
        if isinstance(v, dict) and isinstance(st.get(k), dict):
            st[k].update(v)
        else:
            st[k] = v
    return st


# ------------------------------------------------------------------------------------- checks
def validate(state, office=None):
    """List of (level, message); level 'error' blocks the run, 'warning' is shown and allowed."""
    out = []
    p = state["project"]
    if not str(p.get("name", "")).strip():
        out.append(("error", "Project name is empty (step 1)."))
    opts = [o for o in state["options"] if o.get("include")]
    if not opts:
        out.append(("error", "No option is ticked to include (step 1)."))
    names = [o["name"].strip() for o in opts]
    if len(set(names)) != len(names) or any(not n for n in names):
        out.append(("error", "Option names must be filled in and different from each other (step 1)."))
    cat = {f["id"]: f for f in facade_catalogue(office or {})}
    for o in opts:
        tag = "Option '%s'" % o["name"]
        if o["source"] == "layer" and not o.get("layer"):
            out.append(("error", "%s: pick its massing layer (step 1)." % tag))
        if o["source"] == "file" and not o.get("file"):
            out.append(("error", "%s: pick its .3dm file (step 1)." % tag))
        fac = o.get("facade") or []
        if not 1 <= len(fac) <= MAX_FACADE_TYPES:
            out.append(("error", "%s: choose 1 to %d facade types (step 3)." % (tag, MAX_FACADE_TYPES)))
        tot = sum(float(f.get("share") or 0) for f in fac)
        if fac and abs(tot - 1.0) > 0.005:
            out.append(("error", "%s: facade shares add up to %.0f%%, not 100%% (step 3)." % (tag, tot * 100)))
        for f in fac:
            if cat and f["build_up"] not in cat:
                out.append(("error", "%s: facade type %s is not in the office library list (step 3)." % (tag, f["build_up"])))
            if f.get("kind") == FACADE_PUNCHED and not (0 <= float(f.get("wwr") or 0) <= 0.95):
                out.append(("error", "%s: glazing ratio for %s must be 0-95%% (step 3)." % (tag, f["build_up"])))
    sch = state["schedule"]
    if not sch.get("path"):
        out.append(("warning", "No area schedule: GIA and levels come from the massing and storey heights (step 2)."))
    pl = state["plan"]
    if pl.get("route") == "none" or (pl.get("route") == "rhino" and not pl.get("walls_layer") and not pl.get("columns_layer")) \
            or (pl.get("route") == "pdf" and not pl.get("pdf_json")):
        out.append(("warning", "No plan: cores, columns and stairs use office defaults and are tagged [ASSUMED] (step 2)."))
    op = state.get("operational") or {}
    if op.get("route", "").startswith("Engineer"):
        for o in opts:
            if not any((o.get("operational") or {}).get(k) for k in ("elec", "gas", "dh")):
                out.append(("error", "Option '%s': enter the predicted annual energy (step 5), or change the B6 basis." % o["name"]))
    if op.get("route", "Not assessed") != "Not assessed" and not all((o.get("operational") or {}).get("water") for o in opts):
        if p.get("occupancy"):
            out.append(("warning", "No engineer's water figure for some options: B7 uses the occupancy water budget (step 1)."))
        else:
            out.append(("warning", "No water figure and no occupancy: B7 is reported as not assessed (enter occupancy on step 1 "
                                   "or water on step 5)."))
    t = state["targets"]
    for k, v in t["sc_share"].items():
        if not 0 <= float(v) <= 1:
            out.append(("error", "Shell & core share for %s must be 0-100%% (step 5)." % k))
    if t.get("catb_allowance") not in (None, "") and float(t["catb_allowance"]) < 0:
        out.append(("error", "Cat B allowance cannot be negative (step 5)."))
    if not state["output"].get("folder"):
        out.append(("error", "Choose where to save the take-off and workbook (step 5)."))
    return out


# ------------------------------------------------------------------------------------- facade mix
EXPORT_COLS = ["project_id", "element_id", "nrm_code", "build_up_code", "quantity", "unit", "method",
               "stage", "model_version", "author", "source_layer", "include", "notes"]


def apply_facade_mix(rows, option, office, glazed_code="CW-UNIT-01", opaque_code="EW-SFS-BRK-01"):
    """Re-split the take-off's facade into the option's mix of up to three types.

    The take-off measures the net facade (after louvres and entrance doors) and writes it as one glazed row
    (2.5.2, `glazed_code`) and one opaque row (2.5.1, `opaque_code`). Those two rows are replaced by one row
    per type and part, each a share of the net facade:
      unitised type  -> share x net, reported 2.5.2 with the type's build-up (glazing is part of the system)
      punched type   -> share x (1 - glazing ratio) x net, 2.5.1, the type's build-up
                        share x glazing ratio x net, 2.6 windows (RICS element category), the type's
                        glazing build-up (2.5.2 with the curtain wall stand-in if the type names none)
    Soffits, louvres, doors and every other row are kept as they are."""
    cat = dict((f["id"], f) for f in facade_catalogue(office or {}))
    glz = [r for r in rows if r["build_up_code"] == glazed_code and str(r["nrm_code"]) == "2.5.2"]
    opq = [r for r in rows if r["build_up_code"] == opaque_code and str(r["nrm_code"]) == "2.5.1"]
    if not glz and not opq:
        return list(rows)
    net = sum(float(r["quantity"]) for r in glz + opq)
    tmpl = (glz or opq)[0]
    out = [r for r in rows if r not in glz and r not in opq]
    n = 0
    for f in option["facade"]:
        info = cat.get(f["build_up"], {})
        s = float(f["share"])
        label = info.get("label", f["build_up"])
        wall = info.get("code", f["build_up"])
        if f.get("kind", info.get("kind")) == FACADE_UNITISED:
            parts = [("2.5.2", wall, s, "%s, %.0f%% of net facade (glazing in the system)" % (label, s * 100))]
        else:
            w = float(f.get("wwr") or 0)
            win = info.get("glazing_build_up")
            parts = [("2.5.1", wall, s * (1 - w), "%s, opaque: %.0f%% of net facade x (1 - %.0f%% glazing)" % (label, s * 100, w * 100)),
                     ("2.6" if win else "2.5.2", win or glazed_code, s * w,
                      "%s, windows: %.0f%% of net facade x %.0f%% glazing" % (label, s * 100, w * 100))]
        for code, bu, frac, note in parts:
            if frac <= 0:
                continue
            n += 1
            r = dict(tmpl)
            r.update({"element_id": "%s-F%d" % (tmpl["element_id"], n), "nrm_code": code, "build_up_code": bu,
                      "quantity": round(net * frac, 1), "unit": "m2",
                      "notes": "Facade mix (dialog): %s; net facade %.1f m2 after louvres and doors" % (note, net)})
            out.append(r)
    return out


def read_export(path):
    """(header, rows) from a take-off CSV (same format the take-off writes)."""
    import csv
    header, lines = {}, []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            if line.startswith("#"):
                k, _, v = line[1:].partition(":")
                header[k.strip()] = v.strip()
            else:
                lines.append(line)
    return header, list(csv.DictReader(lines))


def write_export(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        for k, v in header.items():
            f.write("# %s: %s\n" % (k, v))
        f.write(",".join(EXPORT_COLS) + "\n")
        for r in rows:
            f.write(",".join('"%s"' % str(r.get(c, "")).replace('"', "'") for c in EXPORT_COLS) + "\n")


# ------------------------------------------------------------------------------------- config builders
def takeoff_config(state, option, office, base_config):
    """CONFIG for wlca_massing_takeoff.run() for one option (base_config = the script's own CONFIG)."""
    cfg = copy.deepcopy(base_config)
    p = state["project"]
    cfg.update({
        "project_id": p["name"], "use_class": p["use_class"], "riba_stage": int(p["riba_stage"]),
        "existing_gia_demolished_m2": float(p.get("demolished_gia_m2") or 0), "author": p.get("assessor") or "XX",
        "model_version": option["name"], "bake": True, "write_files": True,
        "output_dir": os.path.join(state["output"]["folder"], "takeoff"),
        "file_stem": safe_stem(option["name"]) + "_takeoff",
    })
    cfg["massing_layers"] = [option["layer"]] if option["source"] == "layer" and option.get("layer") else None
    if state["schedule"].get("path"):
        cfg["area_schedule"] = {"path": state["schedule"]["path"], "sheet": state["schedule"].get("sheet") or None}
    pl = state["plan"]
    if pl.get("route") == "pdf" and pl.get("pdf_json"):
        cfg["structure"]["plan_json"] = pl["pdf_json"]
    elif pl.get("route") == "rhino" and pl.get("json"):
        cfg["structure"]["plan_json"] = pl["json"]          # written by the dialog's plan reader before the take-off
    s = option["structure"]
    cfg["structure"].update({"grid_x_m": float(s["grid_x_m"]), "grid_y_m": float(s["grid_y_m"]),
                             "column_size_m": float(s["column_size_m"]), "frame": s.get("frame") or "RC flat slab"})
    # facade: the take-off writes one glazed and one opaque row; apply_facade_mix() re-splits them per option
    cfg["wwr"] = {"N": 0.5, "E": 0.5, "S": 0.5, "W": 0.5}
    defaults = (office or {}).get("takeoff_defaults") or {}
    for k, v in defaults.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def calc_config(state, office, exports):
    """Config for wlca_calc_template.build(); exports = [(option, csv_path)] from the take-off run."""
    t = state["targets"]
    params = copy.deepcopy(office.get("params") or {})
    params.update({
        "construction_start_year": int(state["project"]["start_year"]),
        "show_targets": dict((k, "Y" if v else "N") for k, v in t["show"].items()),
        "scenario": t["scenario"], "budget_target": t["budget_target"],
        "sc_share": dict(t["sc_share"]),
        "catb_allowance": None if t.get("catb_allowance") in (None, "") else float(t["catb_allowance"]),
    })
    options = []
    op = state.get("operational") or {}
    params.update({"op_route": op.get("route") or "Not assessed", "dh_factor": float(op.get("dh_factor") or 0),
                   "occupancy": state["project"].get("occupancy"), "occ_days": state["project"].get("occ_days")})
    if op.get("op_year"):
        params["op_year"] = int(op["op_year"])
    for o, csv in exports:      # facade rows are already split by apply_facade_mix: no routing in the workbook
        options.append({"name": o["name"], "takeoff_csv": csv, "facade_route": "As exported",
                        "operational": dict((k, v) for k, v in (o.get("operational") or {}).items() if v not in (None, ""))})
    out = state["output"]
    wb = out.get("workbook") or (safe_stem(state["project"]["name"]) + "_WLCA.xlsx")
    return {
        "options": options, "library_xlsx": office["library_xlsx"], "benchmarks": office["benchmarks"],
        "targets_xlsx": office.get("targets_xlsx"), "site": office.get("site") or {}, "params": params,
        "branding": office.get("branding") or {},
        "out": wb if os.path.isabs(wb) else os.path.join(out["folder"], wb),
    }


def plan_summary(plan, notes):
    """Lines the dialog shows after reading a plan (Rhino route)."""
    c, k, st = plan["core"], plan["columns"], plan["stairs"]
    lines = ["Core walls: %.0f m per floor, %s mm average (%d pieces)" % (
                 c["wall_length_m_per_floor"] or 0, "%.0f" % (1000 * c["mean_thickness_m"]) if c["mean_thickness_m"] else "-", c["pieces"]),
             "Columns: %d per floor%s" % (k["count_per_floor"], ", %.2f m %s" % (k["size_m"], "/".join(k["shapes"])) if k["size_m"] else ""),
             "Stairs: %d%s" % (st["count"], " - %s flights, %s treads, %.2f m wide, going %.2f m" % (
                 "/".join(str(x) for x in st["flights_per_stair"]), "/".join(str(x) for x in sorted(set(st["treads_per_flight"]))),
                 st["flight_width_m"], st["going_m"]) if st["count"] else " (office defaults will be used)")]
    return lines + list(notes)


def safe_stem(name):
    keep = "".join(c if c.isalnum() or c in "-_ " else "_" for c in str(name)).strip()
    return "_".join(keep.split()) or "option"
