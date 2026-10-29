"""
WLCA dialog - state, office settings and config builders  v0.1  (draft for review)

Drafted by an AI agent (Claude) - review before trusting.

Plain Python (no Rhino), so it can be unit-tested. The WLCA window (wlca_web.py) edits a `state`
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
                    "catb_allowance": None, "scenario": "GLA aspirational", "budget_target": "UKNZCBS",
                    "chart": None},        # targets drawn on the Results page (labels); None = a default few
        # font: one family for the whole workbook; logo: None = the office settings logo, "" = none, else an image file
        "output": {"folder": "", "workbook": "", "font": "Arial", "logo": None},
        # B6 / B7 (PS 5.3 / 5.4): basis for the whole building; energy and water per option
        "operational": {"route": "Not assessed", "op_year": None, "dh_factor": 0.0},
        # detailed model (step 2): one rule per line - layer, RICS element, measure, build-up, factor, what it replaces
        # (wlca_modelled.py); measured = the last measurement of those layers; report = what the last run replaced
        "modelled": {"rules": [], "measured": None, "summary": [], "report": {}, "reconciliation": {}},
    }


def default_option(name, layer="", source="layer", file_path=""):
    return {
        "name": name, "include": True, "source": source, "layer": layer, "file": file_path,
        "facade": [{"build_up": "CW-UNIT-01", "kind": FACADE_UNITISED, "share": 1.0, "wwr": None}],
        "structure": {"frame": "RC flat slab", "grid_x_m": 9.0, "grid_y_m": 8.0, "column_size_m": 0.75,
                      "sources": {}},
        "operational": {"elec": None, "gas": None, "dh": None, "pv_self": None, "pv_export": None, "water": None, "eui": None},
        "substructure": default_substructure(),
        "use_modelled": True,          # take off the modelled elements of this model (step 2) for this option
    }


# Foundations and basement walls (step 3). Same keys and defaults as the take-off's CONFIG["substructure"]
# (wlca_massing_takeoff.py; a test keeps the two in step). source values: retaining walls "footprint" (assumed:
# ground-floor perimeter x basement depth) | "engineer"; piles and caps "assumed" | "engineer" | "none".
def default_substructure():
    return {
        "retaining_walls": {"source": "footprint", "type": "secant", "pile_diameter_m": 1.0, "pile_spacing_m": 1.2,
                            "pile_length_m": None, "embedment_ratio": 0.5, "liner_thickness_m": 0.20,
                            "perimeter_m": None, "depth_m": None, "area_m2": None, "volume_m3": None},
        "piles": {"source": "assumed", "diameter_m": 0.75, "per_column": 3, "length_m": 25.0,
                  "core_group": True, "core_spacing_x_dia": 3.0, "count": None},
        "caps_raft": {"source": "assumed", "depth_m": 1.2, "edge_m": 0.15, "core_thickness_m": 2.0, "core_margin_m": 0.5,
                      "raft_thickness_m": 1.0, "volume_m3": None},
        "basement_depth_m": None,
        # basement when the area schedule has none: answer None (not confirmed yet) | "none" | "levels";
        # levels top-down from ground {"name", "ftf", "gea", "gia"} (gea / gia None = measured on the massing)
        "basement": {"answer": None, "levels": [], "ground_level": None},
    }


def new_basement_level(n):
    return {"name": "B%d" % n, "ftf": 4.0, "gea": None, "gia": None}


WALL_SOURCES = [["footprint", "Assumed - basement perimeter x basement depth"], ["engineer", "Engineer's figures"]]
WALL_TYPES = [["secant", "Secant piled wall + RC liner"], ["rc_wall", "RC retaining wall"]]
PILE_SOURCES = [["assumed", "Assumed - bored piles under columns and core"], ["engineer", "Engineer's figures"],
                ["none", "None - not counted (the QA sheet flags the gap)"]]
CAP_SOURCES = [["assumed", "Assumed - caps under columns and core"], ["raft", "Raft - thickness x lowest level GEA"],
               ["engineer", "Engineer's volume"], ["none", "None"]]


def fill_substructure(option):
    """Give an option from an older save the substructure block, keeping anything it already has."""
    sub = option.get("substructure") or {}
    out = default_substructure()
    for k, v in sub.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    option["substructure"] = out
    return option


# ------------------------------------------------------------------------------------- office settings
SETTINGS_FILE = "wlca_office_settings.json"
PACKAGE_FILE = "wlca_package.json"        # optional, next to the scripts: {"office_settings": path, "name": ...}


def user_config_path():
    """Per-PC choices of this tool (e.g. which office settings file), outside the package so updates keep them."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "McNeel", "Rhinoceros", "8.0", "WLCA", "wlca_user.json")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def settings_candidates(pkg_dir, env=None, user_cfg=None):
    """Where to look for the office settings, in order: [(path, where it came from)].
    1 WLCA_OFFICE_SETTINGS environment variable; 2 the file chosen in the dialog on this PC; 3 the default the
    package was built with (wlca_package.json); 4 ..\07_Settings next to the scripts (shared-folder installs)."""
    env = os.environ if env is None else env
    user_cfg = read_json(user_config_path()) if user_cfg is None else user_cfg
    out = []
    if env.get("WLCA_OFFICE_SETTINGS"):
        out.append((env["WLCA_OFFICE_SETTINGS"], "environment variable WLCA_OFFICE_SETTINGS"))
    if user_cfg.get("office_settings"):
        out.append((user_cfg["office_settings"], "chosen on this PC"))
    pkg = read_json(os.path.join(pkg_dir, PACKAGE_FILE)) if pkg_dir else {}
    if pkg.get("office_settings"):
        p = pkg["office_settings"]
        out.append((p if os.path.isabs(p) else os.path.normpath(os.path.join(pkg_dir, p)), "package default"))
    if pkg_dir:
        out.append((os.path.normpath(os.path.join(pkg_dir, "..", "07_Settings", SETTINGS_FILE)), "next to the package folder"))
    return out


def find_office_settings(pkg_dir, env=None, user_cfg=None):
    """(path, source) of the first settings file that exists, else (first candidate or '', 'not found')."""
    cands = settings_candidates(pkg_dir, env, user_cfg)
    for p, src in cands:
        if p and os.path.isfile(p):
            return p, src
    return (cands[0][0] if cands else ""), "not found"


def _remember(key, value, cfg_path=None):
    """Store one per-PC choice in the user config (None or '' forgets it)."""
    cfg_path = cfg_path or user_config_path()
    cfg = read_json(cfg_path)
    if value:
        cfg[key] = value
    else:
        cfg.pop(key, None)
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)


def remember_office_settings(path):
    """Store the chosen settings file for this PC ('' forgets it)."""
    _remember("office_settings", path)


# Panel interface (XW 27/10/2026): "next" = web_next/ (React + Tailwind + shadcn/ui, built from rhino_ui/panel), the
# default since it covers every step; "classic" = web/ (plain HTML / JS), kept for anyone who switches back.
UI_CHOICES = ("classic", "next")
UI_DEFAULT = "next"
UI_PAGES = {"classic": ("web", "index.html"), "next": ("web_next", "index.html")}


def ui_choice(cfg_path=None):
    v = read_json(cfg_path or user_config_path()).get("ui")
    return v if v in UI_CHOICES else UI_DEFAULT


def remember_ui(choice, cfg_path=None):
    _remember("ui", choice if choice in UI_CHOICES and choice != UI_DEFAULT else None, cfg_path)     # only a departure from the default is stored


def ui_page(pkg_dir, choice):
    """index.html of the chosen interface; the classic page when the new one is not in this package."""
    want = os.path.join(pkg_dir, *UI_PAGES.get(choice, UI_PAGES["classic"]))
    return want if os.path.isfile(want) else os.path.join(pkg_dir, *UI_PAGES["classic"])


def package_info(pkg_dir):
    """Name and version shown in the dialog title (from wlca_package.json; defaults for a plain script folder)."""
    pkg = read_json(os.path.join(pkg_dir, PACKAGE_FILE)) if pkg_dir else {}
    return pkg.get("name") or "WLCA", pkg.get("version") or ""
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



_BASEMENT_CACHE = {}


def basement_from_schedule(path, sheet=None):
    """Levels below ground in the area schedule, as the take-off will read them: {levels, depth_m, lowest_gea,
    ground_gea, ftf, gea}, or None (no schedule, unreadable, or no ground level). Cached per file version."""
    if not path or not os.path.exists(path):
        return None
    key = (path, sheet or "", os.path.getmtime(path))
    if key not in _BASEMENT_CACHE:
        _BASEMENT_CACHE.clear()
        _BASEMENT_CACHE[key] = _read_basement(path, sheet)
    return _BASEMENT_CACHE[key]


def _read_basement(path, sheet):
    try:
        import wlca_core as core
        lv = core.parse_area_schedule({"path": path, "sheet": sheet or None}, [])
        gi = core.ground_index(lv)
    except Exception:
        return None
    if gi is None:
        return None
    below = lv[:gi]
    return {"levels": [x["name"] for x in below], "depth_m": round(sum(float(x["ftf"] or 0) for x in below), 2),
            "lowest_gea": float(lv[0]["gea"] or 0), "ground_gea": float(lv[gi]["gea"] or 0),
            "ftf": [float(x["ftf"] or 0) for x in below], "gea": [float(x["gea"] or 0) for x in below]}

# ------------------------------------------------------------------------------------- state I/O
# File paths in the state. Each is saved as it is (absolute) and, when it lies in or under the model's folder, also
# relative to that folder (under "_rel"), so a project folder that is moved or copied keeps working (v0.3.1).
PATH_FIELDS = [("schedule", "path"), ("output", "folder"), ("output", "last_workbook"), ("output", "logo"),
               ("plan", "json"), ("plan", "pdf_json")]
FOLLOWS_MODEL = ("output.folder",)       # always taken relative to the model when it was saved that way


def _path_slots(state):
    """(key, container, field) for every file path in the state."""
    out = [("%s.%s" % (g, k), state.get(g) or {}, k) for g, k in PATH_FIELDS]
    out += [("options.%d.file" % i, o, "file") for i, o in enumerate(state.get("options") or [])]
    return out


def relative_to(path, base):
    """`path` relative to folder `base` if it lies in or under it, else None."""
    if not path or not base or not os.path.isabs(path):
        return None
    try:
        r = os.path.relpath(path, base)
    except ValueError:                       # another drive
        return None
    if r == os.pardir or r.startswith(os.pardir + os.sep) or os.path.isabs(r):
        return None
    return r


def dumps(state, base=None):
    """State as saved in the .3dm. base = the model's folder (None for an unsaved model)."""
    out = dict(state)
    out.pop("_rel", None)
    if base:
        rel = {}
        for key, d, k in _path_slots(state):
            r = relative_to(d.get(k), base)
            if r is not None:
                rel[key] = r
        if rel:
            out["_rel"] = rel
    return json.dumps(out, sort_keys=True)


def resolve_paths(st, rel, base, exists=os.path.exists):
    """Re-anchor saved paths on the model's folder: the output folder always follows the model; an input file
    (schedule, plan, logo, option model) is taken from the model's folder when it is there, else from where it was."""
    for key, d, k in _path_slots(st):
        if key not in rel:
            continue
        here = os.path.normpath(os.path.join(base, rel[key]))
        if key in FOLLOWS_MODEL or exists(here) or not exists(d.get(k) or ""):
            d[k] = here
    return st


def loads(text, base=None, exists=os.path.exists):
    """State from the .3dm; missing keys are filled from the defaults so older saves keep working.
    base = the model's folder: paths saved relative to it are re-anchored there (resolve_paths)."""
    st = default_state()
    if not text:
        return st
    saved = json.loads(text)
    rel = saved.pop("_rel", None) or {}
    for k, v in saved.items():
        if isinstance(v, dict) and isinstance(st.get(k), dict):
            st[k].update(v)
        else:
            st[k] = v
    for o in st.get("options") or []:
        fill_substructure(o)
    if base and rel:
        resolve_paths(st, rel, base, exists)
    return st


# ------------------------------------------------------------------------------------- edits from the web window
def parse_pct(text, default=None):
    """'70%', '70' or '0.7' -> 0.7"""
    try:
        t = str(text).strip().rstrip("%").strip()
        v = float(t)
        return v / 100.0 if (v > 1 or str(text).strip().endswith("%")) else v
    except ValueError:
        return default


def parse_num(text, default=None):
    try:
        return float(str(text).replace(",", "").strip())
    except ValueError:
        return default


def convert_edit(kind, value, old=None):
    """A value typed in the window -> what the state holds. kind: text, bool, pct, num (blank = None),
    num0 (blank = 0), int."""
    if kind == "bool":
        return bool(value)
    if kind == "pct":
        return parse_pct(value, old)
    if kind == "num":
        return None if str(value).strip() == "" else parse_num(value, old)
    if kind == "num0":
        return 0.0 if str(value).strip() == "" else parse_num(value, old)
    if kind == "int":
        v = parse_num(value, None)
        return int(v) if v is not None else old
    return "" if value is None else str(value)


def apply_edit(state, path, value, kind="text"):
    """Set state[path...] from the window. Paths are lists of keys / list indices, e.g. ["options", 0, "facade", 1,
    "share"]. Returns the stored value; raises KeyError / IndexError for a path the state does not have."""
    d = state
    for p in path[:-1]:
        d = d[p]
    if isinstance(d, list):
        old = d[path[-1]]
    else:
        old = d.get(path[-1])
    d[path[-1]] = convert_edit(kind, value, old)
    if path[:2] == ["output", "font"] and not str(d[path[-1]]).strip():
        d[path[-1]] = "Arial"
    return d[path[-1]]


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
    sched_bsm = basement_from_schedule(state["schedule"].get("path"), state["schedule"].get("sheet"))
    for o in opts:
        tag = "Option '%s'" % o["name"]
        if o["source"] == "layer" and not o.get("layer"):
            out.append(("error", "%s: pick its massing layer (step 1)." % tag))
        if o["source"] == "file" and not o.get("file"):
            out.append(("error", "%s: pick its .3dm file (step 1)." % tag))
        fac = o.get("facade") or []
        if not 1 <= len(fac) <= MAX_FACADE_TYPES:
            out.append(("error", "%s: choose 1 to %d facade types (step 5)." % (tag, MAX_FACADE_TYPES)))
        tot = sum(float(f.get("share") or 0) for f in fac)
        if fac and abs(tot - 1.0) > 0.005:
            out.append(("error", "%s: facade shares add up to %.0f%%, not 100%% (step 5)." % (tag, tot * 100)))
        for f in fac:
            if cat and f["build_up"] not in cat:
                out.append(("error", "%s: facade type %s is not in the office library list (step 5)." % (tag, f["build_up"])))
            if f.get("kind") == FACADE_PUNCHED and not (0 <= float(f.get("wwr") or 0) <= 0.95):
                out.append(("error", "%s: glazing ratio for %s must be 0-95%% (step 5)." % (tag, f["build_up"])))
        out += check_substructure(o, tag, sched_bsm)
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
                out.append(("error", "Option '%s': enter the predicted annual energy (step 6), or change the B6 basis." % o["name"]))
    if op.get("route", "Not assessed") != "Not assessed" and not all((o.get("operational") or {}).get("water") for o in opts):
        if p.get("occupancy"):
            out.append(("warning", "No engineer's water figure for some options: B7 uses the occupancy water budget (step 1)."))
        else:
            out.append(("warning", "No water figure and no occupancy: B7 is reported as not assessed (enter occupancy on step 1 "
                                   "or water on step 6)."))
    t = state["targets"]
    for k, v in t["sc_share"].items():
        if not 0 <= float(v) <= 1:
            out.append(("error", "Shell & core share for %s must be 0-100%% (step 6)." % k))
    if t.get("catb_allowance") not in (None, "") and float(t["catb_allowance"]) < 0:
        out.append(("error", "Cat B allowance cannot be negative (step 6)."))
    logo = effective_logo(state, office)
    if logo and not os.path.exists(logo):
        out.append(("warning", "Logo file not found - the workbook is made without a logo (step 7)."))
    elif logo and os.path.splitext(logo)[1].lower() not in LOGO_TYPES:
        out.append(("warning", "Logo should be a PNG or JPG image - other files may not show in Excel (step 7)."))
    if not state["output"].get("folder"):
        out.append(("error", "Choose where to save the take-off and workbook (step 6)."))
    out += check_modelled(state, office)
    return out


# ------------------------------------------------------------------------------------- detailed model (step 2)
_LIB_CACHE = {}


def library_buildups(office):
    """{code: {"unit", "rics", "desc"}} from the office build-up library, cached on the file's path and time; {} if unreadable."""
    path = (office or {}).get("library_xlsx")
    if not path or not os.path.exists(path):
        return {}
    key = (path, os.path.getmtime(path))
    if key not in _LIB_CACHE:
        try:
            import wlca_modelled as wm
            _LIB_CACHE.clear()
            _LIB_CACHE[key] = wm.read_library(path)
        except Exception:
            return {}
    return _LIB_CACHE[key]


def active_rules(state):
    return [r for r in ((state.get("modelled") or {}).get("rules") or []) if r.get("measure", "ignore") != "ignore"]


def uses_model(option, state):
    return bool(option.get("use_modelled", True) and active_rules(state))


def check_modelled(state, office):
    """Step 2 checks on the rule table, when any included option takes off the model."""
    if not any(uses_model(o, state) for o in state["options"] if o.get("include")):
        return []
    import wlca_modelled as wm
    out = list(wm.check_rules(active_rules(state), library_buildups(office)))
    if not (state.get("modelled") or {}).get("measured"):
        out.append(("warning", "The model layers have not been measured yet - Measure model, or the run measures them (step 2)."))
    shares = [r for r in active_rules(state) if r["measure"] == "share"]
    if shares and not any(r["build_up"] and (library_buildups(office).get(r["build_up"]) or {}).get("rics", "").startswith(("2.5.2", "2.6"))
                          or str(r.get("rics", "")).startswith(("2.5.2", "2.6")) for r in shares):
        out.append(("warning", "The façade shares from the model have no glazing layer: the whole net façade becomes wall (step 2)."))
    return out


def rule_view(state):
    """Per rule line: objects, quantity (measure x factor) and unit from the last measurement - for the table."""
    import wlca_modelled as wm
    md = state.get("modelled") or {}
    stage = (state.get("project") or {}).get("riba_stage")
    layers = ((md.get("measured") or {}).get("layers")) or {}
    rules = md.get("rules") or []
    share_tot = 0.0
    for r in rules:
        if r.get("measure") == "share" and r["layer"] in layers:
            share_tot += float(layers[r["layer"]].get("face") or 0) * float(r.get("factor") or 1)
    out = []
    for r in rules:
        st = layers.get(r["layer"])
        m = r.get("measure", "ignore")
        g = r.get("replaces") or "none"
        v = {"n": st.get("n") if st else None, "open": st.get("open") if st else None, "q": None, "unit": wm.UNIT.get(m, ""),
             "share": None, "group": g, "mode": wm.resolve_mode(r.get("mode"), g, stage) if g != "none" and m != "share" else "replace"}
        if st and m not in wm.NO_TAKEOFF:
            v["q"] = round(float(st.get(wm.STAT[m]) or 0) * float(r.get("factor") or 1), 1)
            if m == "share" and share_tot > 0:
                v["share"] = round(v["q"] / share_tot, 4)
        out.append(v)
    return out


def after_rule_edit(state, k, field, lib):
    """Knock-on changes when a rule's field is edited on step 2."""
    import wlca_modelled as wm
    r = state["modelled"]["rules"][k]
    r["source"] = "edited"
    if field == "rics":
        r["replaces"] = wm.default_replaces(r["rics"])
        r["mode"] = wm.default_mode(r["replaces"])
    elif field == "replaces":
        r["mode"] = wm.default_mode(r["replaces"])
    elif field == "build_up" and r["build_up"] in lib:
        b = lib[r["build_up"]]
        if r.get("measure", "ignore") == "ignore" or wm.UNIT.get(r["measure"]) != b["unit"]:
            r["measure"] = wm.measure_for(r["build_up"], lib) or r.get("measure", "ignore")
        if not r.get("rics"):
            r["rics"] = b["rics"]
            r["replaces"] = wm.default_replaces(r["rics"])
            r["mode"] = wm.default_mode(r["replaces"])
    elif field == "measure" and r["measure"] == "share":
        r["replaces"], r["mode"] = "facade", "auto"
    return r


def finish_rows(rows, option, state, office, build_ups):
    """Rows the take-off wrote for one option -> rows exported: the facade mix of step 5, or, when the option takes off
    the model, the modelled rows in place of the derived rows they replace (facade shares from the model instead of
    the step 5 mix). Returns (rows, header extras, report lines, notes)."""
    glz, opq = build_ups["facade_glazed"], build_ups["facade_opaque"]
    md = state.get("modelled") or {}
    if not (uses_model(option, state) and md.get("measured")):
        return apply_facade_mix(rows, option, office, glazed_code=glz, opaque_code=opq), facade_header(option, office), [], []
    import wlca_modelled as wm
    lib = library_buildups(office)
    t = rows[0] if rows else {}
    meta = {k: t.get(k, "") for k in ("project_id", "stage", "model_version", "author")}
    mrows, shares, rep, notes = wm.modelled_rows(active_rules(state), md["measured"], lib, meta)
    snew, sold = [], []
    if shares:
        rows, snew, net, sold = wm.share_rows(rows, shares, build_ups, meta)
    else:
        rows = apply_facade_mix(rows, option, office, glazed_code=glz, opaque_code=opq)
    a13 = dict((c, b.get("a13")) for c, b in lib.items() if b.get("a13") is not None)
    rows, report = wm.apply_modelled(rows, mrows, rep, build_ups, snew, sold, a13)
    hdr = wm.facade_header_from_rows(rows, build_ups) or facade_header(option, office)
    return rows, hdr, wm.report_lines(report), notes


def glazing_mix(option, office):
    """Glazed share of the net facade in the option's step 5 mix (unitised types count whole)."""
    cat = dict((f["id"], f) for f in facade_catalogue(office or {}))
    g = 0.0
    for f in option.get("facade") or []:
        kind = f.get("kind", (cat.get(f.get("build_up")) or {}).get("kind"))
        g += float(f.get("share") or 0) * (1.0 if kind == FACADE_UNITISED else float(f.get("wwr") or 0))
    return g


def reconcile_option(rows, geom, option, state, office, build_ups, plan=None, objects=None):
    """Reconciliation rows (wlca_reconcile.reconcile) for one option, from the take-off's own rows and geometry.
    objects = {layer: per-piece records} from the last measurement (kept on the window, not in the state)."""
    import wlca_reconcile as wr
    md = state.get("modelled") or {}
    m = md.get("measured") or {}
    rules = active_rules(state) if uses_model(option, state) and m else []
    if objects:
        m = dict(m, layers=dict((p, dict(st, objects=objects.get(p))) for p, st in (m.get("layers") or {}).items()))
    return wr.reconcile(rows, geom, plan, rules, m, library_buildups(office), build_ups, option,
                        glazing_mix(option, office))


def store_reconciliation(state, option, recon, path=None):
    """Keep the rows for the Run step (state["modelled"]["reconciliation"][option name]) and write them next to the
    take-off CSV for the workbook's O<k>_Recon sheet."""
    import wlca_reconcile as wr
    doc = {"option": option["name"], "tolerance": wr.TOL, "rows": recon, "factors": wr.scale_factors(recon),
           "choices": dict(option.get("reconcile") or {}), "stale": False}
    state.setdefault("modelled", {}).setdefault("reconciliation", {})[option["name"]] = doc
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
    return doc


def set_reconcile_choice(state, i, key, value):
    """A Run step choice (core height / basement depth): stored on the option; the take-off must run again to apply it."""
    import wlca_reconcile as wr
    if key not in wr.CHOICES or value not in [v for v, _ in wr.CHOICES[key]]:
        raise ValueError("Unknown reconciliation choice %s = %s" % (key, value))
    o = state["options"][int(i)]
    o.setdefault("reconcile", {})[key] = value
    doc = ((state.get("modelled") or {}).get("reconciliation") or {}).get(o["name"])
    if doc:
        for r in doc["rows"]:
            if r.get("choice") and r["choice"]["key"] == key:
                r["choice"]["value"] = value
        ran = doc.get("choices") or {}
        doc["stale"] = any(ran.get(k, wr.CHOICES[k][0][0]) != v for k, v in o["reconcile"].items())


def reconcile_stale(state):
    """Names of the options whose Run step choices changed since the take-off ran."""
    rc = (state.get("modelled") or {}).get("reconciliation") or {}
    return [n for n, d in rc.items() if d.get("stale")]


def apply_reconcile(rows, recon, option, build_ups):
    """Derived core walls / basement walls scaled to the source chosen on the Run step (scale_factors()). Rows from
    the engineer's figures and secant piles of a given length are left as they are. Returns (rows, notes)."""
    import wlca_modelled as wm
    import wlca_reconcile as wr
    f = wr.scale_factors(recon)
    if not f:
        return rows, []
    ret = ((option.get("substructure") or {}).get("retaining_walls") or {})
    out, notes, n = [], [], {}
    for r in rows:
        k = wm.kind_of(r, build_ups)
        if k in f and r.get("method") != "Supplied" and \
                not (k == "basement_wall" and ret.get("pile_length_m") and "secant" in str(r.get("notes", "")).lower()):
            r = dict(r)
            r["quantity"] = round(float(r["quantity"]) * f[k], 3)
            r["notes"] = "%s; x %.3f to the modelled %s (Run step)" % (
                r.get("notes", ""), f[k], "core height" if k == "core_wall" else "basement depth")
            n[k] = n.get(k, 0) + 1
        out.append(r)
    for k, c in n.items():
        notes.append("%s: %d row(s) x %.3f to the model (Run step choice)" % ("Core walls" if k == "core_wall" else
                                                                             "Basement walls", c, f[k]))
    return out, notes


def check_substructure(option, tag, sched_basement=None):
    """Step 3 checks for one option: figures the chosen route needs. sched_basement: basement_from_schedule()."""
    out = []
    sub = option.get("substructure") or default_substructure()
    bsm = sub.get("basement") or {}
    if not (sched_basement and sched_basement["levels"]):
        where = "the area schedule has no levels below ground" if sched_basement else "there is no area schedule"
        if bsm.get("answer") not in ("none", "levels"):
            out.append(("error", "%s: %s - confirm there is no basement, or enter the basement levels (step 3)." % (tag, where)))
        elif bsm.get("answer") == "levels":
            lv = bsm.get("levels") or []
            if not lv:
                out.append(("error", "%s: enter at least one basement level, or confirm there is no basement (step 3)." % tag))
            for x in lv:
                if x.get("ftf") in (None, "") or float(x["ftf"]) <= 0:
                    out.append(("error", "%s: basement level %s needs a floor-to-floor height (step 3)." % (tag, x.get("name") or "?")))
                for k in ("gea", "gia"):
                    if x.get(k) not in (None, "") and float(x[k]) <= 0:
                        out.append(("error", "%s: basement level %s %s must be more than 0 (step 3)." % (tag, x.get("name") or "?", k.upper())))
            if any(x.get(k) in (None, "") for x in lv for k in ("gea", "gia")):
                out.append(("warning", "%s: blank basement GEA / GIA are measured on the massing below ground level - the massing "
                                       "must include the basement (step 3)." % tag))
    pos = lambda d, k: d.get(k) not in (None, "") and float(d[k]) > 0      # noqa: E731
    ret, p, c = sub["retaining_walls"], sub["piles"], sub["caps_raft"]
    if ret.get("source") == "engineer":
        if not (pos(ret, "volume_m3") or pos(ret, "area_m2") or pos(ret, "perimeter_m")):
            out.append(("error", "%s: basement walls from the engineer need a volume, an area or a perimeter (step 3)." % tag))
    elif ret.get("type", "secant") == "secant":
        for k, lbl in (("pile_diameter_m", "secant pile diameter"), ("pile_spacing_m", "secant hard-to-hard spacing")):
            if not pos(ret, k):
                out.append(("error", "%s: enter the %s (step 3)." % (tag, lbl)))
        if pos(ret, "pile_diameter_m") and pos(ret, "pile_spacing_m") and not \
                float(ret["pile_diameter_m"]) <= float(ret["pile_spacing_m"]) < 2 * float(ret["pile_diameter_m"]):
            out.append(("error", "%s: secant hard-to-hard spacing must be at least one and less than two pile diameters, "
                                 "so the firm pile overlaps both hard piles (step 3)." % tag))
    if ret.get("depth_m") not in (None, "") and float(ret["depth_m"]) < 0 or \
            sub.get("basement_depth_m") not in (None, "") and float(sub["basement_depth_m"]) < 0:
        out.append(("error", "%s: basement depth cannot be negative (step 3)." % tag))
    if p.get("source") == "engineer":
        if not all(pos(p, k) for k in ("count", "diameter_m", "length_m")):
            out.append(("error", "%s: piles from the engineer need the number, diameter and length (step 3)." % tag))
    elif p.get("source") == "assumed":
        if not all(pos(p, k) for k in ("diameter_m", "per_column", "length_m")):
            out.append(("error", "%s: assumed piles need a diameter, piles per column and a length (step 3)." % tag))
        if p.get("core_group") and not pos(p, "core_spacing_x_dia"):
            out.append(("error", "%s: enter the core pile spacing (step 3)." % tag))
    if c.get("source") == "engineer" and not pos(c, "volume_m3"):
        out.append(("error", "%s: pile caps / raft from the engineer need a volume (step 3)." % tag))
    elif c.get("source") == "assumed" and p.get("source") != "assumed":
        out.append(("warning", "%s: assumed pile caps follow the assumed piles - with the engineer's piles or none, enter "
                               "the cap volume or set caps to none; no caps are counted (step 3)." % tag))
    elif c.get("source") == "assumed" and not all(pos(c, k) for k in ("depth_m", "core_thickness_m")):
        out.append(("error", "%s: assumed pile caps need a cap depth and a core cap thickness (step 3)." % tag))
    elif c.get("source") == "raft" and not pos(c, "raft_thickness_m"):
        out.append(("error", "%s: enter the raft thickness (step 3)." % tag))
    return out


LOGO_TYPES = (".png", ".jpg", ".jpeg", ".gif", ".bmp")


def effective_logo(state, office):
    """The logo the workbook will carry: the dialog's choice, else the office settings logo ('' = none)."""
    choice = (state.get("output") or {}).get("logo")
    if choice is None:
        return ((office or {}).get("branding") or {}).get("logo") or ""
    return choice


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


def facade_header(option, office):
    """Export header lines describing the option's facade mix, so the workbook's scope check knows whether to expect
    curtain walling (2.5.2) and punched windows (2.6): shares of the net facade."""
    cat = dict((f["id"], f) for f in facade_catalogue(office or {}))
    cw = punched = 0.0
    for f in option.get("facade") or []:
        kind = f.get("kind") or cat.get(f["build_up"], {}).get("kind")
        s = float(f.get("share") or 0)
        if kind == FACADE_UNITISED:
            cw += s
        elif float(f.get("wwr") or 0) > 0:
            punched += s
    return {"facade_curtain_wall_share": round(cw, 4), "facade_punched_window_share": round(punched, 4)}


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
    # substructure (step 3): the option's figures win over the office defaults and the script's own
    sub = cfg.setdefault("substructure", {})
    for k, v in (option.get("substructure") or {}).items():
        if isinstance(v, dict) and isinstance(sub.get(k), dict):
            sub[k].update(v)
        else:
            sub[k] = copy.deepcopy(v)
    return cfg


def recon_path(csv):
    """The reconciliation JSON written next to a take-off CSV."""
    return os.path.splitext(csv)[0] + "_reconciliation.json"


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
        rj = recon_path(csv)
        options.append({"name": o["name"], "takeoff_csv": csv, "facade_route": "As exported",
                        "reconciliation_json": rj if os.path.exists(rj) else None,
                        "operational": dict((k, v) for k, v in (o.get("operational") or {}).items() if v not in (None, ""))})
    out = state["output"]
    branding = dict(office.get("branding") or {})
    branding["font"] = out.get("font") or "Arial"
    if out.get("logo") is not None:
        branding["logo"] = out["logo"] or None
    wb = out.get("workbook") or (safe_stem(state["project"]["name"]) + "_WLCA.xlsx")
    return {
        "options": options, "library_xlsx": office["library_xlsx"], "benchmarks": office["benchmarks"],
        "targets_xlsx": office.get("targets_xlsx"), "site": office.get("site") or {}, "params": params,
        "branding": branding,
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
