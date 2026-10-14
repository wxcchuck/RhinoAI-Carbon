"""
wlca_core - quantity rules for the WLCA massing take-off (no Rhino dependency)

Drafted by an AI agent (Claude) - review before trusting. See carbon/README.md.

Everything here is plain Python 3 so it can be unit-tested outside Rhino. The Rhino wrapper
(wlca_massing_takeoff.py) measures geometry and hands plain numbers to these functions:

  read_xlsx_sheet / parse_area_schedule / ground_index   area schedule route
  schedule_horizontals                                    slabs, roofs, soffits from a schedule (BR-01..03)
  reconcile_schedule                                      massing vs schedule, level by level
  structure_rows                                          core walls + columns (plan extract or numbers)
  secant_section                                          hard/firm secant wall plan geometry
  substructure_rows                                       basement walls, liner, piles, caps/raft
  build_rows                                              interchange schema v0.1 rows

Rows produced by the rules are tuples (rics_code, build_up_key, quantity, unit, method, note);
build_rows maps build_up_key -> library code via CONFIG["build_ups"].
"""

import math
import os

ORIENTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]   # 45-degree bins centred on each direction
GROUND_NAMES = ("0", "00", "G", "GF", "GROUND", "L0", "L00")


class TakeoffError(Exception):
    pass


# ----------------------------------------------------------------------------- orientation / WWR
def orientation(nx, ny, north_deg=0.0):
    """Bin an outward normal (plan) into one of 8 orientations; north_deg = true north clockwise from +Y."""
    az = (math.degrees(math.atan2(nx, ny)) - north_deg) % 360.0
    return ORIENTS[int(((az + 22.5) % 360.0) // 45.0)]


def expand_wwr(w):
    """Accept 4 (N/E/S/W) or 8 keys; diagonals default to the mean of their neighbours."""
    out = dict(w)
    for k, (a, b) in {"NE": ("N", "E"), "SE": ("S", "E"), "SW": ("S", "W"), "NW": ("N", "W")}.items():
        if k not in out:
            out[k] = (w[a] + w[b]) / 2.0
    missing = [k for k in ORIENTS if k not in out]
    if missing:
        raise TakeoffError("wwr missing orientations: %s" % missing)
    return out


# ----------------------------------------------------------------------------- area schedule (route a)
def read_xlsx_sheet(path, sheet_name):
    """Cached cell values of one sheet, without external packages: {row: {col_letter: value}}."""
    import zipfile
    import xml.etree.ElementTree as ET
    M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid, names = None, []
    for sh in wb.find("{%s}sheets" % M):
        names.append(sh.get("name"))
        if sh.get("name").strip().lower() == sheet_name.strip().lower():
            rid = sh.get("{%s}id" % R)
    if rid is None:
        raise TakeoffError("Sheet '%s' not in %s (sheets: %s)" % (sheet_name, os.path.basename(path), ", ".join(names)))
    target = [r.get("Target") for r in rels if r.get("Id") == rid][0].lstrip("/")
    if not target.startswith("xl/"):
        target = "xl/" + target
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("{%s}si" % M):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % M)))
    rows = {}
    for c in ET.fromstring(z.read(target)).iter("{%s}c" % M):
        ref = c.get("r")
        col = "".join(ch for ch in ref if ch.isalpha())
        row = int(ref[len(col):])
        t, v = c.get("t"), c.find("{%s}v" % M)
        if t == "s" and v is not None:
            val = shared[int(v.text)]
        elif t == "inlineStr":
            val = "".join(x.text or "" for x in c.iter("{%s}t" % M))
        elif v is None:
            val = None
        elif t in ("str", "e"):
            val = v.text
        else:
            try:
                val = float(v.text)
            except (TypeError, ValueError):
                val = v.text
        rows.setdefault(row, {})[col] = val
    return rows


def _num(v):
    return isinstance(v, float)


def _txt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else str(v)
    return str(v).strip()


def _col_index(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n


def parse_area_schedule(spec, warnings):
    """Levels bottom -> top: dicts with name, use, aod, ftf, gea, gia, nia.

    spec = {"path": ..., "sheet": ...}. The header row is the first row containing Level, GEA and GIA;
    AOD, Floor to Floor and NIA are optional columns (NIA prefers a 'Total' sub-column).
    """
    rows = read_xlsx_sheet(spec["path"], spec.get("sheet", "Sheet1"))
    hdr, cols = None, {}
    for r in sorted(rows):
        lab = dict((c, _txt(v).lower()) for c, v in rows[r].items())
        vals = set(lab.values())
        if "level" in vals and "gea" in vals and "gia" in vals:
            hdr = r
            for c, v in lab.items():
                if v == "level":
                    cols["level"] = c
                elif v == "use":
                    cols["use"] = c
                elif v.startswith("aod"):
                    cols["aod"] = c
                elif "floor to floor" in v or v in ("ftf", "f2f"):
                    cols["ftf"] = c
                elif v == "gea":
                    cols["gea"] = c
                elif v == "gia":
                    cols["gia"] = c
                elif v.startswith("nia") and "nia" not in cols:
                    cols["nia"] = c
            break
    if hdr is None:
        raise TakeoffError("No header row with Level / GEA / GIA found on sheet '%s'" % spec.get("sheet"))
    if "nia" in cols:
        for r in (hdr + 1, hdr + 2):
            for c, v in rows.get(r, {}).items():
                if _txt(v).lower() == "total" and 0 <= _col_index(c) - _col_index(cols["nia"]) <= 4:
                    cols["nia"] = c
    levels, started = [], False
    for r in sorted(x for x in rows if x > hdr):
        row = rows[r]
        name = _txt(row.get(cols["level"]))
        gea = row.get(cols["gea"])
        if not name:
            if started:
                break
            continue
        if not _num(gea):
            continue
        started = True

        def opt(key):
            v = row.get(cols[key]) if key in cols else None
            return v if _num(v) else None
        levels.append(dict(name=name, use=_txt(row.get(cols.get("use"))), gea=gea, gia=opt("gia"),
                           aod=opt("aod"), ftf=opt("ftf"), nia=opt("nia")))
    if not levels:
        raise TakeoffError("Area schedule has no level rows under the header")
    for lv in levels:
        if lv["gia"] is None:
            raise TakeoffError("Level %s has no GIA in the schedule" % lv["name"])
        if lv["ftf"] is None:
            raise TakeoffError("Level %s has no floor-to-floor height in the schedule" % lv["name"])
    if all(lv["aod"] is not None for lv in levels):
        levels.sort(key=lambda d: d["aod"])
    else:
        levels.sort(key=lambda d: _level_key(d["name"]))
        warnings.append("Schedule has no AOD column - levels ordered by name, heights stacked from base")
    for a, b in zip(levels[:-1], levels[1:]):
        if a["aod"] is not None and b["aod"] is not None and abs(a["aod"] + a["ftf"] - b["aod"]) > 0.02:
            warnings.append("Schedule: level %s AOD %.2f + FTF %.2f != level %s AOD %.2f"
                            % (a["name"], a["aod"], a["ftf"], b["name"], b["aod"]))
    return levels


def _level_key(n):
    u = n.upper().replace("LEVEL", "").strip()
    if u.startswith("B"):
        try:
            return -float(u[1:])
        except ValueError:
            return -0.5
    if u in GROUND_NAMES:
        return 0.0
    try:
        return float(u.lstrip("L"))
    except ValueError:
        return 0.0


def ground_index(levels):
    for i, lv in enumerate(levels):
        if lv["name"].upper().replace("LEVEL", "").strip() in GROUND_NAMES:
            return i
    return None


def stack_aod(levels, gi, base):
    """Fill missing AODs by stacking FTFs up and down from the ground level at `base`."""
    z = base
    for lv in levels[gi:]:
        lv["aod"] = z
        z += lv["ftf"]
    z = base
    for lv in reversed(levels[:gi]):
        z -= lv["ftf"]
        lv["aod"] = z


# ----------------------------------------------------------------------------- horizontals from schedule
def schedule_horizontals(sched):
    """Slab / roof / soffit areas from a schedule (bottom -> top), per BR-01..BR-03.

    lowest   1.2.1  lowest level GEA
    basement 1.2.2  suspended slabs below the ground line
    upper    2.2.1  suspended slabs at / above the ground line
    roof     2.2.1 + 2.5.3  storey below not covered by the one above, plus the top level
    podium   2.2.1  basement roof outside the building at ground (finishes = external works)
    soffit   2.5.1  overhang above ground (level larger than the one below)
    """
    gi = ground_index(sched)
    if gi is None:
        raise TakeoffError("Schedule has no ground level (named 0 / G / GF / Ground)")
    hz = dict(lowest=sched[0]["gea"], basement=0.0, upper=0.0, roof=0.0, podium=0.0, soffit=0.0)
    roof_levels = []
    for i in range(1, len(sched)):
        lv, below = sched[i], sched[i - 1]
        if i < gi:
            hz["basement"] += lv["gea"]
        else:
            hz["upper"] += lv["gea"]
        exposed = max(0.0, below["gea"] - lv["gea"])
        if exposed > 0.01:
            if i == gi:
                hz["podium"] += exposed
            else:
                hz["roof"] += exposed
                roof_levels.append(dict(level=lv["name"], z=round(lv["aod"], 3), area=round(exposed, 1)))
        if i > gi and lv["gea"] - below["gea"] > 0.01:
            hz["soffit"] += lv["gea"] - below["gea"]
    top = sched[-1]
    hz["roof"] += top["gea"]
    roof_levels.append(dict(level="roof", z=round(top["aod"] + top["ftf"], 3), area=round(top["gea"], 1)))
    return hz, roof_levels


def reconcile_schedule(sched, massing_gea_by_name, tol, warnings):
    """Per-level massing GEA vs schedule GEA; returns rows and appends a summary warning."""
    gi = ground_index(sched)
    rows, n_flag = [], 0
    for lv in sched:
        mg = massing_gea_by_name.get(lv["name"])
        d = (mg - lv["gea"]) / lv["gea"] if (mg is not None and lv["gea"]) else None
        if mg is None:
            flag = "below ground - not in massing"
        elif d is not None and abs(d) > tol:
            flag = "CHECK"
            n_flag += 1
        else:
            flag = "OK"
        rows.append(dict(level=lv["name"], use=lv["use"], aod=round(lv["aod"], 3), ftf=lv["ftf"],
                         schedule_gea=round(lv["gea"], 1), schedule_gia=round(lv["gia"], 1),
                         schedule_nia=lv["nia"], massing_gea=None if mg is None else round(mg, 1),
                         delta_pct=None if d is None else round(100 * d, 1), status=flag))
    if n_flag:
        ag_s = sum(lv["gea"] for lv in sched[gi:])
        ag_m = sum(massing_gea_by_name.get(lv["name"]) or 0 for lv in sched[gi:])
        warnings.append("%d level(s) differ from the schedule by more than %.0f%% (above ground total %+.1f%%) - check model vs schedule option"
                        % (n_flag, 100 * tol, 100 * (ag_m - ag_s) / ag_s))
    return rows


# ----------------------------------------------------------------------------- structure (2.1.1)
def structure_rows(lv_all, plan, S, method, warnings, core_wall_build_up="WALL-RC-250", column_build_up="COL-RC-750"):
    """Core walls (m2) and columns (m) per level.

    lv_all: [(name, ftf, gea, gia, nia)] for every level the structure passes through (incl. basements).
    plan:   dict from wlca_plan_extract, or None.
    S:      CONFIG["structure"].
    Returns (rows, info) where info carries core_area, column counts by level, etc.
    """
    rows = []
    geas = [round(x[2]) for x in lv_all]
    typ_gea = max(set(geas), key=geas.count)                 # the typical floor a plan represents
    typ = [x for x in lv_all if round(x[2]) == typ_gea][0]
    core_area, ca_src = None, None
    if S.get("core_area_m2"):
        core_area, ca_src = S["core_area_m2"], "input"
    elif S.get("core_area_pct_gia"):
        core_area, ca_src = S["core_area_pct_gia"] * typ[3], "%.0f%% of typical GIA" % (100 * S["core_area_pct_gia"])
    elif typ[4]:
        core_area, ca_src = typ[3] - typ[4], "schedule typical GIA - NIA (level %s)" % typ[0]

    wall_len, wl_src = None, None
    if S.get("core_wall_length_m_per_floor"):
        wall_len, wl_src = S["core_wall_length_m_per_floor"], "input"
    elif plan:
        wall_len = plan["core"]["wall_length_m_per_floor"]
        wl_src = "plan extract %s (mean %.2f m thick)" % (plan["source"], plan["core"]["mean_thickness_m"] or 0)
    elif core_area:
        wall_len = core_area * S["core_wall_density_m_per_m2"]
        wl_src = "core area %.0f m2 x %.2f m/m2" % (core_area, S["core_wall_density_m_per_m2"])
    if wall_len:
        q = sum(wall_len * x[1] for x in lv_all)
        rows.append(("2.1.1", "core_wall", q, "m2", method,
                     "Core walls, all RC: %.1f m/floor (%s) x FTF, %d levels incl. basements" % (wall_len, wl_src, len(lv_all))))
        if plan and plan["core"]["mean_thickness_m"] and abs(plan["core"]["mean_thickness_m"] - 0.25) > 0.05:
            warnings.append("Plan core walls average %.2f m thick vs build-up %s" % (plan["core"]["mean_thickness_m"], core_wall_build_up))
    else:
        warnings.append("No core input (plan_json, wall length, core area or schedule NIA) - 2.1.1 core walls not derived")

    n_typ = None
    if S.get("column_count_per_floor"):
        n_typ = S["column_count_per_floor"]
    elif plan and plan["columns"]["count_per_floor"]:
        n_typ = plan["columns"]["count_per_floor"]
        if abs(plan["columns"]["size_m"] - S["column_size_m"]) > 0.1 * S["column_size_m"]:
            warnings.append("Plan columns %.2f m vs column_size_m %.2f m / build-up %s" % (plan["columns"]["size_m"], S["column_size_m"], column_build_up))
    free_typ = typ[2] - (core_area or 0)
    if n_typ:
        rho, rho_src = n_typ / free_typ, "%d on typical level %s" % (n_typ, typ[0])
    else:
        rho = S["column_edge_factor"] / (S["grid_x_m"] * S["grid_y_m"])
        rho_src = "grid %.1f x %.1f m x edge factor %.2f" % (S["grid_x_m"], S["grid_y_m"], S["column_edge_factor"])
    col_m, col_n = 0.0, []
    for name, h, gea, gia, nia in lv_all:
        n = int(round(rho * max(0.0, gea - (core_area or 0))))
        col_n.append((name, n))
        col_m += n * h
    rows.append(("2.1.1", "column", col_m, "m", method,
                 "Columns %s; scaled per level by GEA less core (%s): %s"
                 % (rho_src, "core %.0f m2, %s" % (core_area, ca_src) if core_area else "no core deduction",
                    ", ".join("%s:%d" % c for c in col_n[:3]) + " ...")))
    info = dict(typical_level=typ[0], core_area_m2=core_area, core_area_source=ca_src,
                core_wall_m_per_floor=wall_len, core_wall_source=wl_src,
                columns_per_m2=round(rho, 5), columns_by_level=col_n)
    return rows, info


# ----------------------------------------------------------------------------- substructure (1.1, 1.2.3)
def secant_section(d, sp, warnings=None):
    """Plan geometry of a hard/firm secant wall.

    Hard piles at `sp` centres (hard-to-hard); one firm pile centred between each pair, i.e. sp/2 from
    each hard pile. Overlaps are deducted once, from the firm pile.
    Returns dict(a_hard, a_firm, lens, eq_thickness) per bay of length sp.
    """
    w = warnings if warnings is not None else []
    r = d / 2.0
    a_c = math.pi * r * r
    h = sp / 2.0
    if sp < d:
        w.append("Hard piles at %.2f m centres overlap each other (dia %.2f m) - check spacing" % (sp, d))
    if h >= d:
        w.append("Firm piles do not reach the hard piles (half-spacing %.2f m >= dia %.2f m) - wall has gaps" % (h, d))
        lens = 0.0
    else:
        lens = 2 * r * r * math.acos(h / (2 * r)) - (h / 2) * math.sqrt(4 * r * r - h * h)
    a_firm = a_c - 2 * lens
    return dict(a_hard=a_c, a_firm=a_firm, lens=lens, eq_thickness=(a_c + a_firm) / sp)


def substructure_rows(lv_all, n_base, has_schedule, ground, lowest_gea, col_n, core_area, ca_src, SUB, method,
                      warnings, liner_build_up="LINER-RC-200"):
    """Basement walls (1.2.3), piles and caps/raft (1.1).

    ground: (name, perimeter_m, gea_m2) of the ground storey (from the massing).
    lowest_gea: GEA of the lowest level (for the basement-larger-than-footprint warning).
    col_n: [(level, n_columns)] bottom -> top, from structure_rows.
    """
    rows = []
    ret = SUB["retaining_walls"]
    depth = sum(x[1] for x in lv_all[:n_base]) if has_schedule else (SUB.get("basement_depth_m") or 0)
    if ret.get("source") == "engineer":
        if ret.get("volume_m3"):
            rows.append(("1.2.3", "secant_wall", ret["volume_m3"], "m3", "Supplied", "Engineer's figures: piled wall %.0f m3" % ret["volume_m3"]))
        else:
            a = ret.get("area_m2") or ((ret.get("perimeter_m") or 0) * (ret.get("depth_m") or depth))
            if a > 0:
                rows.append(("1.2.3", "retaining_wall", a, "m2", "Supplied", "Engineer's figures: %s" % (
                    "%.0f m2" % ret["area_m2"] if ret.get("area_m2") else
                    "%.1f m x %.2f m" % (ret.get("perimeter_m") or 0, ret.get("depth_m") or depth))))
    elif depth > 0:
        g_name, g_per, g_gea = ground
        per = ret.get("perimeter_m") or g_per
        src_p = "input" if ret.get("perimeter_m") else "ground-floor footprint, massing %s" % g_name
        if ret.get("type", "secant") == "secant":
            d, sp = ret["pile_diameter_m"], ret["pile_spacing_m"]
            L = ret.get("pile_length_m") or depth * (1 + ret.get("embedment_ratio", 0.5))
            L_src = "input" if ret.get("pile_length_m") else "depth %.2f m x (1 + %.2f embedment)" % (depth, ret.get("embedment_ratio", 0.5))
            if L <= depth:
                warnings.append("Secant pile length %.1f m gives no embedment below the %.2f m basement - check" % (L, depth))
            g = secant_section(d, sp, warnings)
            n = int(math.ceil(per / sp))                      # closed perimeter: n hard + n firm
            rows.append(("1.2.3", "secant_wall", n * g["a_hard"] * L, "m3", method,
                         "Secant wall HARD RC piles (assumed, no SI): %d = perimeter %.1f m (%s) / %.2f m hard-to-hard c/c, %.2f m dia x %.2f m (%s) (BR-04)"
                         % (n, per, src_p, sp, d, L, L_src)))
            rows.append(("1.2.3", "secant_firm", n * g["a_firm"] * L, "m3", method,
                         "Secant wall FIRM piles: %d x %.3f m2 net (circle %.3f - 2 overlaps of %.3f) x %.2f m; equivalent wall %.2f m thick"
                         % (n, g["a_firm"], g["a_hard"], g["lens"], L, g["eq_thickness"])))
            t = ret.get("liner_thickness_m")
            if t:
                rows.append(("1.2.3", "liner_wall", per * depth, "m2", method,
                             "RC liner %.0f mm inside piled wall = perimeter %.1f m x basement depth %.2f m" % (t * 1000, per, depth)))
                if abs(t - 0.20) > 0.01:
                    warnings.append("Liner %.0f mm vs build-up %s (200 mm)" % (t * 1000, liner_build_up))
        else:
            rows.append(("1.2.3", "retaining_wall", per * depth, "m2", method,
                         "RC basement walls = perimeter %.1f m (%s) x basement depth %.2f m (BR-04)" % (per, src_p, depth)))
        if has_schedule and lowest_gea > 1.05 * g_gea and not ret.get("perimeter_m"):
            warnings.append("Basement GEA %.0f m2 exceeds ground footprint %.0f m2 - footprint perimeter may understate basement walls (x%.2f if same shape)"
                            % (lowest_gea, g_gea, (lowest_gea / g_gea) ** 0.5))

    p = SUB["piles"]
    if p.get("source") == "engineer" and p.get("count") and p.get("diameter_m") and p.get("length_m"):
        v = p["count"] * math.pi / 4 * p["diameter_m"] ** 2 * p["length_m"]
        rows.append(("1.1", "pile", v, "m3", "Supplied", "Engineer's figures: %d piles x %.2f m dia x %.1f m" % (p["count"], p["diameter_m"], p["length_m"])))
    elif p.get("source") == "assumed":
        n_cols = col_n[0][1] if col_n else 0                  # columns arriving at the lowest level
        if n_cols:
            n = int(round(n_cols * p["per_column"]))
            v = n * math.pi / 4 * p["diameter_m"] ** 2 * p["length_m"]
            rows.append(("1.1", "pile", v, "m3", method,
                         "Bored piles under columns (assumed, no SI): %d columns at %s x %s per column = %d piles x %.2f m dia x %.1f m"
                         % (n_cols, col_n[0][0], p["per_column"], n, p["diameter_m"], p["length_m"])))
        if p.get("core_group") and core_area:
            s_c = p["core_spacing_x_dia"] * p["diameter_m"]
            n_c = int(math.ceil(core_area / s_c ** 2))
            v_c = n_c * math.pi / 4 * p["diameter_m"] ** 2 * p["length_m"]
            rows.append(("1.1", "pile", v_c, "m3", method,
                         "Bored pile group under core (assumed, no SI): core %.0f m2 (%s) / (%.2f m c/c)^2 = %d piles x %.2f m dia x %.1f m"
                         % (core_area, ca_src, s_c, n_c, p["diameter_m"], p["length_m"])))
        elif p.get("core_group"):
            warnings.append("Core pile group not derived - no core area (input, % GIA or schedule NIA)")
    c = SUB["caps_raft"]
    if c.get("source") == "engineer" and c.get("volume_m3"):
        rows.append(("1.1", "cap_raft", c["volume_m3"], "m3", "Supplied", "Engineer's figures: pile caps / raft %.0f m3" % c["volume_m3"]))
    if not any(r[0] == "1.1" for r in rows):
        warnings.append("1.1 foundations: no piles derived - keep the benchmark row")
    elif not any(r[1] == "cap_raft" for r in rows):
        warnings.append("1.1 pile caps / raft not included - add the engineer's volume (caps_raft) or confirm an assumption")
    return rows, depth


# ----------------------------------------------------------------------------- interchange rows
def build_rows(cfg, hz, roof_levels, hsrc, glazed, opaque, parapet_net, wwr, st_rows, source_layer):
    """Assemble interchange schema v0.1 rows (quantities only; zero rows dropped)."""
    B = cfg["build_ups"]
    m = cfg["method_label"]
    rl = ", ".join("+%.2f: %.0f" % (r["z"], r["area"]) for r in roof_levels)
    spec = [
        ("1.2.1", "lowest_slab",   hz["lowest"],   "m2", m, "Lowest slab (%s)" % hsrc),
        ("1.2.2", "basement_slab", hz["basement"], "m2", m, "Suspended slabs below ground line (BR-03, %s)" % hsrc),
        ("2.2.1", "upper_floor",   hz["upper"],    "m2", m, "Suspended floor slabs at/above ground line (BR-03, %s)" % hsrc),
        ("2.2.1", "roof_slab",     hz["roof"],     "m2", m, "Roof slabs (BR-01, %s): %s" % (hsrc, rl)),
        ("2.2.1", "roof_slab",     hz["podium"],   "m2", m, "Basement roof outside building footprint at ground (%s) - surface finishes are external works 8.1.1, not 2.5.3" % hsrc),
        ("2.5.3", "roof_finish",   hz["roof"],     "m2", m, "Roof coverings over roof slabs, excl. podium (BR-02)"),
        ("2.5.1", "soffit_finish", hz["soffit"],   "m2", m, "Insulated soffit under overhangs (%s)" % hsrc),
        ("2.5.2", "facade_glazed", glazed,         "m2", m, "Storey facade (massing) x WWR %s" % ", ".join("%s %.0f%%" % (k, wwr[k] * 100) for k in ORIENTS)),
        ("2.5.1", "facade_opaque", opaque,         "m2", m, "Envelope facade (massing) less glazing; incl. parapets/upstands (net %.0f m2)" % parapet_net),
    ] + list(st_rows)
    rows, n = [], 0
    for code, key, q, unit, method, note in spec:
        if q <= 0.01:
            continue
        n += 1
        rows.append(dict(project_id=cfg["project_id"], element_id="MS-%04d" % n, nrm_code=code,
                         build_up_code=B[key], quantity=round(q, 1), unit=unit, method=method,
                         stage=cfg["riba_stage"], model_version=cfg["model_version"], author=cfg["author"],
                         source_layer=source_layer, include="Y", notes=note))
    return rows
