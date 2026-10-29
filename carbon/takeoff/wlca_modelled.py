"""
WLCA modelled elements  v0.1  (draft for review)
Office WLCA template - detailed models: take off what is modelled, keep the massing estimate for the rest

Drafted by an AI agent (Claude) - review before trusting. Plain Python (no Rhino), unit-tested in carbon/tests;
wlca_modelled_rhino.py measures the geometry and hands the figures to these rules.

How a detailed model is read
  One RULE per line of the table on step 2: a Rhino layer, the RICS element it reports to, how it is measured,
  the build-up from the library, a factor, and which massing-derived rows it replaces. A layer can have several
  lines (e.g. the lowest slab as a volume of concrete and as a plan area of sub-base). A rule's defaults come from,
  in order:
    1. the layer name, when it follows RICS_<code>_<anything>[_<build-up code>]  (e.g. RICS_2.2.1_Slabs_SLAB-RC-M3);
    2. the office pattern list (office settings "modelled_layer_patterns": layer-name globs -> rule);
    3. otherwise the layer is listed as not mapped and ignored until someone sets it.
  An object with user text WLCA_BUILDUP=<code> is taken off on its own, whatever its layer says: measured as its
  build-up's unit implies (m3 volume, m2 plan or face, nr count) and reported to that build-up's RICS code.

Measures (per object, from closed solids and meshes; open surfaces only give areas)
  volume     volume as modelled (m3); volume_v / volume_h = only the vertical / horizontal pieces (columns / beams on
             one layer: a piece is vertical when its height is at least its plan extent)
  plan       area of the top faces (m2) = volume / height for prismatic pieces
  face       area of one side of a wall-like piece (m2) = (surface area - 2 x top area) / 2
  share      the face areas of every 'share' rule split the massing's net facade between them (m2): the model sets
             what the facade is made of, the massing sets how much facade there is
  count      number of objects (nr)
Replacement: the massing-derived rows of the group a rule replaces are dropped for the options that use the model
(e.g. floors: the derived upper-floor and roof slabs; facade: the derived walls and glazing). Allowances the model does
not normally show (soffits, louvres, entrance doors, other roof elements) stay as derived.
"""
import fnmatch
import re

METHOD = "Modelled"
TAG_KEY = "WLCA_BUILDUP"

MEASURES = [  # key, label, unit
    ("volume", "Volume as modelled", "m3"),
    ("volume_v", "Volume - vertical pieces only (columns)", "m3"),
    ("volume_h", "Volume - horizontal pieces only (beams)", "m3"),
    ("plan", "Plan area (top faces)", "m2"),
    ("face", "Face area (one side)", "m2"),
    ("share", "Share of the massing façade", "m2"),
    ("count", "Count", "nr"),
    ("ignore", "Ignore", ""),
]
UNIT = dict((k, u) for k, _, u in MEASURES)
LABEL = dict((k, lb) for k, lb, _ in MEASURES)
STAT = {"volume": "vol", "volume_v": "vol_v", "volume_h": "vol_h", "plan": "plan", "face": "face", "share": "face",
        "count": "n"}

# group -> (label, derived row kinds it removes); kinds come from kind_of()
REPLACE = {
    "piles_caps": ("Piles and caps (1.1)", ["pile", "cap_raft"]),
    "lowest_slab": ("Lowest slab (1.2.1)", ["lowest_slab"]),
    "basement_slabs": ("Basement suspended slabs (1.2.2)", ["basement_slab"]),
    "basement_walls": ("Basement walls (1.2.3)", ["basement_wall"]),
    "columns": ("Columns (2.1.1)", ["column"]),
    "core_walls": ("Core walls (2.1.1)", ["core_wall"]),
    "beams": ("Edge beams (2.1.2)", ["edge_beam"]),
    "floors": ("Upper floors and roof slabs (2.2.1)", ["upper_floor"]),
    "stairs": ("Stairs (2.4)", ["stair"]),
    "roof_finish": ("Roof coverings (2.5.3)", ["roof_finish"]),
    "facade": ("Façade walls and glazing (2.5.1, 2.5.2, 2.6 windows)", ["facade_opaque", "facade_glazed", "windows"]),
    "none": ("Nothing - adds to the derived rows", []),
}
REPLACE_ORDER = ["facade", "floors", "columns", "beams", "core_walls", "stairs", "roof_finish", "lowest_slab",
                 "basement_slabs", "basement_walls", "piles_caps", "none"]
DEFAULT_REPLACES = {"1.1": "piles_caps", "1.2.1": "lowest_slab", "1.2.2": "basement_slabs", "1.2.3": "basement_walls",
                    "2.1.1": "columns", "2.1.2": "beams", "2.2.1": "floors", "2.4": "stairs", "2.5.1": "facade",
                    "2.5.2": "facade", "2.6": "facade", "2.5.3": "roof_finish"}
TAKEOFF_GROUPS = ("1", "2")      # RICS groups the take-off measures; 3-8 are on benchmarks

RICS_LAYER = re.compile(r"^RICS_(\d+(?:\.\d+)*)(?:_(.*))?$", re.I)


# ----------------------------------------------------------------------------------------------- library
def read_library(path):
    """{build-up code: {"unit", "rics", "desc"}} from the build-up library's Buildups sheet (header on row 4)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb["Buildups"]
    out = {}
    for r in ws.iter_rows(min_row=5, values_only=True):
        if r and r[0]:
            out[str(r[0]).strip()] = {"rics": str(r[1] or "").strip(), "desc": str(r[2] or "").strip(),
                                      "unit": str(r[3] or "").strip()}
    wb.close()
    return out


def measure_for(code, lib):
    """Measure an object tagged with a build-up code is taken off by: from the build-up's unit and RICS code."""
    b = lib.get(code) or {}
    u, rics = b.get("unit"), b.get("rics") or ""
    if u == "m3":
        return "volume"
    if u == "m2":
        return "face" if rics.startswith(("2.5.1", "2.5.2", "2.6")) else "plan"
    if u == "nr":
        return "count"
    return None


def default_replaces(rics):
    rics = str(rics or "")
    if rics in DEFAULT_REPLACES:
        return DEFAULT_REPLACES[rics]
    for k in sorted(DEFAULT_REPLACES, key=len, reverse=True):
        if rics.startswith(k + "."):
            return DEFAULT_REPLACES[k]
    return "none"


# ----------------------------------------------------------------------------------------------- rules
def new_rule(layer, rics="", measure="ignore", build_up="", factor=1.0, replaces=None, source="", note=""):
    return {"layer": layer, "rics": str(rics or ""), "measure": measure, "build_up": build_up or "",
            "factor": float(factor if factor not in (None, "") else 1.0),
            "replaces": replaces if replaces is not None else default_replaces(rics), "source": source, "note": note}


def parse_rics_layer(leaf):
    """(RICS code, build-up code or None) from a layer named RICS_<code>_<anything>[_<build-up>]; None if not so named."""
    m = RICS_LAYER.match(leaf.strip())
    if not m:
        return None
    rest = (m.group(2) or "").split("_")
    return m.group(1), (rest[-1].strip() if rest and rest[-1].strip() else None)


def rules_from_layer_name(path, lib):
    leaf = path.split("::")[-1]
    p = parse_rics_layer(leaf)
    if p is None:
        return None
    code, bu = p
    if not code.startswith(TAKEOFF_GROUPS):
        return [new_rule(path, code, "ignore", source="layer name",
                         note="RICS group %s is on benchmarks in the take-off, not modelled" % code.split(".")[0])]
    if bu and bu in lib:
        m = measure_for(bu, lib)
        if m:
            return [new_rule(path, code, m, bu, source="layer name")]
    return [new_rule(path, code, "ignore", source="layer name",
                     note="RICS %s from the layer name; no build-up code at the end of the name - choose one" % code)]


def rules_from_patterns(path, patterns):
    """Rules from the first office pattern matching the layer's full path (every entry with that same pattern)."""
    for p in patterns or []:
        if fnmatch.fnmatch(path.lower(), str(p.get("pattern", "")).lower()):
            hit = [q for q in patterns if q.get("pattern") == p.get("pattern")]
            return [new_rule(path, q.get("rics", ""), q.get("measure", "ignore"), q.get("build_up", ""), q.get("factor", 1.0),
                             q.get("replaces"), source="office pattern '%s'" % p["pattern"], note=q.get("note", "")) for q in hit]
    return None


def suggest_rules(layers, patterns, lib, existing=None):
    """The rule table for the layers found in the model. Lines already in the table (edited or not) are kept for
    layers that still exist; new layers get their defaults; layers gone from the model drop out.
    layers: [layer full path]. Returns (rules, dropped layer paths)."""
    existing = existing or []
    keep = {}
    for r in existing:
        keep.setdefault(r["layer"], []).append(r)
    out = []
    for path in layers:
        if path in keep:
            out += keep[path]
            continue
        rs = rules_from_layer_name(path, lib) or rules_from_patterns(path, patterns) or \
            [new_rule(path, "", "ignore", source="not mapped", note="Not mapped - set it, or leave it ignored")]
        out += rs
    dropped = sorted(set(keep) - set(layers))
    return out, dropped


def check_rules(rules, lib):
    """[(level, message)] - errors block the run (step 2)."""
    out = []
    for r in rules:
        if r.get("measure", "ignore") == "ignore":
            continue
        where = "Model layer '%s'" % r["layer"].split("::")[-1]
        bu = r.get("build_up") or ""
        if r["measure"] not in UNIT:
            out.append(("error", "%s: unknown measure %s (step 2)." % (where, r["measure"])))
            continue
        if not bu:
            out.append(("error", "%s: choose a build-up, or ignore the layer (step 2)." % where))
            continue
        if lib and bu not in lib:
            out.append(("error", "%s: build-up %s is not in the office library (step 2)." % (where, bu)))
            continue
        if lib and lib[bu]["unit"] != UNIT[r["measure"]]:
            out.append(("error", "%s: %s is per %s but '%s' gives %s (step 2)." % (where, bu, lib[bu]["unit"],
                                                                                LABEL[r["measure"]].lower(), UNIT[r["measure"]])))
        try:
            if float(r.get("factor") or 0) <= 0:
                out.append(("error", "%s: the factor must be above 0 (step 2)." % where))
        except (TypeError, ValueError):
            out.append(("error", "%s: the factor must be a number (step 2)." % where))
        if not str(r.get("rics") or "").strip():
            out.append(("error", "%s: give the RICS element it reports to (step 2)." % where))
    return out


# ----------------------------------------------------------------------------------------------- rows
def _row(meta, n, rics, bu, q, unit, layer, note):
    return {"project_id": meta.get("project_id", ""), "element_id": "MD-%04d" % n, "nrm_code": rics, "build_up_code": bu,
            "quantity": round(q, 2), "unit": unit, "method": METHOD, "stage": meta.get("stage", ""),
            "model_version": meta.get("model_version", ""), "author": meta.get("author", ""), "source_layer": layer,
            "include": "Y", "notes": note}


def modelled_rows(rules, measured, lib, meta=None):
    """Rows from the measured model. measured = wlca_modelled_rhino.measure() output:
    {"layers": {path: stats}, "tagged": {code: stats + "layers"}}; stats = {"n", "open", "vol", "vol_v", "vol_h",
    "plan", "face"}. Returns (rows, shares, replaces, notes):
      rows      interchange rows (method Modelled)
      shares    [(layer, build-up, rics, face m2)] for 'share' rules - turned into rows by share_rows()
      replaces  {row element_id: group}
      notes     warnings for the run messages"""
    meta = meta or {}
    rows, shares, rep, notes, n = [], [], {}, [], 0
    layers = (measured or {}).get("layers") or {}
    for r in rules:
        m = r.get("measure", "ignore")
        if m == "ignore":
            continue
        st = layers.get(r["layer"])
        if st is None:
            notes.append("Model layer '%s' was not found in the model - not taken off" % r["layer"])
            continue
        f = float(r.get("factor") or 1.0)
        q = float(st.get(STAT[m]) or 0) * f
        if m.startswith("volume") and st.get("open"):
            notes.append("Model layer '%s': %d open object(s) have no volume and are not counted" % (r["layer"], st["open"]))
        if q <= 0:
            notes.append("Model layer '%s': nothing measured as %s" % (r["layer"], LABEL[m].lower()))
            continue
        if m == "share":
            shares.append((r["layer"], r["build_up"], r["rics"], q))
            continue
        n += 1
        note = "Modelled: %s, %d object(s), %s%s" % (r["layer"], st.get("n", 0), LABEL[m].lower(),
                                                     " x %g" % f if abs(f - 1) > 1e-9 else "")
        row = _row(meta, n, r["rics"], r["build_up"], q, UNIT[m], r["layer"], note + (" - " + r["note"] if r.get("note") else ""))
        rows.append(row)
        rep[row["element_id"]] = r.get("replaces") or "none"
    for code, st in sorted(((measured or {}).get("tagged") or {}).items()):
        m = measure_for(code, lib)
        if m is None:
            notes.append("Objects tagged %s=%s: build-up not in the library (or not per m3 / m2 / nr) - not taken off" % (TAG_KEY, code))
            continue
        q = float(st.get(STAT[m]) or 0)
        if q <= 0:
            continue
        n += 1
        rics = lib[code]["rics"]
        row = _row(meta, n, rics, code, q, UNIT[m], " | ".join(st.get("layers") or []),
                   "Modelled: %d object(s) tagged %s=%s, %s" % (st.get("n", 0), TAG_KEY, code, LABEL[m].lower()))
        rows.append(row)
        rep[row["element_id"]] = default_replaces(rics)
    return rows, shares, rep, list(dict.fromkeys(notes))


def kind_of(row, build_ups):
    """What a massing-derived row is (build_ups = the take-off's CONFIG["build_ups"])."""
    code, bu = str(row["nrm_code"]), row["build_up_code"]
    B = build_ups or {}
    if code == "1.1":
        return "pile" if bu == B.get("pile") else "cap_raft"
    if code == "1.2.1":
        return "lowest_slab"
    if code == "1.2.2":
        return "basement_slab"
    if code == "1.2.3":
        return "basement_wall"
    if code == "2.1.1":
        return "core_wall" if bu == B.get("core_wall") else "column"
    if code == "2.1.2":
        return "edge_beam"
    if code == "2.2.1":
        return "upper_floor"
    if code == "2.3":
        return "roof_other"
    if code == "2.4":
        return "stair"
    if code == "2.5.3":
        return "roof_finish"
    if code == "2.5.1":
        return "soffit_finish" if bu == B.get("soffit_finish") else "facade_opaque"
    if code == "2.5.2":
        return "facade_glazed"
    if code == "2.6":
        return "louvre" if bu == B.get("louvre") else "door_ext" if bu == B.get("door_ext") else "windows"
    return "other"


def share_rows(rows, shares, build_ups, meta=None, start=1000):
    """Split the massing's net facade (the derived opaque + glazed rows) between the 'share' rules in proportion to
    their modelled face areas. Returns (rows without the derived facade, share rows, net facade m2, derived facade rows)."""
    meta = meta or {}
    fac = [r for r in rows if kind_of(r, build_ups) in ("facade_opaque", "facade_glazed")]
    net = sum(float(r["quantity"]) for r in fac)
    total = sum(s[3] for s in shares)
    out = [r for r in rows if r not in fac]
    new = []
    if net <= 0 or total <= 0:
        return rows, new, net, []
    tmpl = fac[0] if fac else {}
    meta = dict(meta, project_id=meta.get("project_id", tmpl.get("project_id", "")), stage=meta.get("stage", tmpl.get("stage", "")),
                model_version=meta.get("model_version", tmpl.get("model_version", "")), author=meta.get("author", tmpl.get("author", "")))
    for i, (layer, bu, rics, area) in enumerate(shares):
        s = area / total
        new.append(_row(meta, start + i, rics, bu, s * net, "m2", layer,
                        "Modelled façade share: %s face %.0f m2 = %.1f%% of the modelled façade (%.0f m2) x net massing façade "
                        "%.0f m2 (after louvres and entrance doors)" % (layer, area, 100 * s, total, net)))
    return out, new, net, fac


def apply_modelled(rows, mrows, replaces, build_ups, share_new=None, share_old=None):
    """Drop the derived rows of every group a modelled row replaces, then add the modelled rows (and the facade
    share rows, which replace the facade group; share_old = the derived facade rows share_rows() took out, for the
    report). Returns (rows, report) - report: [{"group", "label", "derived", "modelled"}] with quantities summed by
    unit, e.g. {"m2": 1234.5}."""
    groups = set(replaces.get(r["element_id"], "none") for r in mrows)
    if share_new:
        groups.add("facade")
    groups.discard("none")
    kinds = set(k for g in groups for k in REPLACE[g][1])
    keep, gone = [], list(share_old or [])
    for r in rows:
        (gone if kind_of(r, build_ups) in kinds else keep).append(r)

    def by_unit(rs):
        d = {}
        for r in rs:
            d[r["unit"]] = round(d.get(r["unit"], 0) + float(r["quantity"]), 1)
        return d
    report = []
    for g in [g for g in REPLACE_ORDER if g in groups]:
        ks = REPLACE[g][1]
        report.append({"group": g, "label": REPLACE[g][0],
                       "derived": by_unit([r for r in gone if kind_of(r, build_ups) in ks]),
                       "modelled": by_unit([r for r in mrows if replaces.get(r["element_id"]) == g] +
                                           (list(share_new) if g == "facade" and share_new else []))})
    added = [r for r in mrows if replaces.get(r["element_id"], "none") == "none"]
    if added:
        report.append({"group": "none", "label": REPLACE["none"][0], "derived": {}, "modelled": by_unit(added)})
    return keep + list(share_new or []) + list(mrows), report


def facade_header_from_rows(rows, build_ups):
    """Export header for the workbook's scope check, from the facade rows actually written (modelled facade)."""
    k = [(kind_of(r, build_ups), float(r["quantity"])) for r in rows if r["unit"] == "m2"]
    net = sum(q for kd, q in k if kd in ("facade_opaque", "facade_glazed", "windows"))
    if net <= 0:
        return {}
    cw = sum(q for kd, q in k if kd == "facade_glazed")
    win = sum(q for kd, q in k if kd == "windows")
    return {"facade_curtain_wall_share": round(cw / net, 4), "facade_punched_window_share": round(win / net, 4)}


def report_lines(report):
    """Lines for the Run step: what the model replaced."""
    def q(d):
        return ", ".join("{:,.0f} {}".format(v, u.replace("m2", "m²").replace("m3", "m³")) for u, v in sorted(d.items())) or "-"
    return ["%s: derived %s -> modelled %s" % (x["label"], q(x["derived"]), q(x["modelled"])) for x in report]
