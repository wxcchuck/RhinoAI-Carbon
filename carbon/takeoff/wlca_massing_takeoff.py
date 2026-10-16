#! python3
"""
WLCA massing take-off  v0.9  (draft for review)
Office WLCA template - build step 4a (massing route, RIBA 0-2)

Drafted by an AI agent (Claude) - review before trusting. Quantity rules live in wlca_core.py
(plain Python, unit-tested in carbon/tests); this file only measures geometry in Rhino.

What it does
  1. Collects closed solids from the massing layer(s); fails loudly on open or mesh geometry.
  2. Floor arrangement from ONE of two routes:
       a) area schedule (xlsx, any sheet with Level / GEA / GIA headers, optional AOD, Floor to Floor,
          NIA) - governs levels, storey heights, GEA, GIA, slabs and roofs, incl. basements; or
       b) storey heights you supply - the massing is sliced and GIA = plates offset by the facade zone.
     The massing always governs the envelope: facade by orientation and WWR. With a schedule,
     massing plates are reconciled level by level against it and differences > tolerance flagged.
     Slicing: from a base level and the storey heights.
     A volume contributes to a storey only if a full storey fits inside it
     (min_storey_fraction = 1.0), so parapets / roof upstands are not counted as floors.
  3. Bakes floor plates (GEA) and GIA curves (plates offset inward by the facade zone)
     to WLCA::_Massing::GEA and WLCA::GIA, so GIA always comes from curves, never typed.
  4. Measures the union of the massing by z-bands between every top/bottom level:
     lowest slab, roof areas, exposed soffits, and gross facade area by orientation
     (8 bins, N/NE/.../NW), split into storey-enclosing facade and parapet/upstand.
  5. Writes quantity rows in interchange schema v0.1 (CSV with '# key: value' header +
     JSON {"header", "rows"}), plus a geometry summary (storeys, bands, orientations).
     Quantities only - no carbon. Build-up codes come from CONFIG and must exist in the
     build-up library.

  6. Structure (v0.3): core walls and columns per level, from a plan extract (WLCA_plan_extract)
     or numeric inputs (core area, wall density, grid); basement retaining walls from the ground-floor
     footprint x basement depth, or the engineer's figures; piles and caps/raft from the engineer.
  7. Substructure defaults (v0.4, no SI data): bored piles 0.75 m dia, 3 per column (lowest level),
     25 m long, plus a pile group under the core (v0.5); basement walls as a secant piled wall,
     hard/firm secant piles (v0.6: 1.0 m dia, hard piles at 1.2 m centres with a firm pile between,
     overlaps deducted), length = basement depth x (1 + embedment ratio), with an RC liner (v0.5).

  8. Scope-gap allowances (v0.8): stairs (count and flight geometry from the plan extract), edge beams
     on every slab edge, louvres on plant levels, entrance doors, other roof elements, pile caps.
     Every rule takes the best information available - supplied figures > drawing / model > office
     assumption - and rows resting on an assumption start their notes with [ASSUMED], so they can be
     listed and replaced as project information arrives.

  9. Frame systems (v0.9): RC flat slab as measured, PT flat slab, or a steel / timber frame from the PF Stage 1
     rates per m2 of floor (beams and connections in the floor build-up); steel / timber columns are scaled by
     (storeys + 1) / 9 relative to PF's ground + 7 building and tagged [ASSUMED] (core.apply_frame).

Limits
  - Exact for prismatic massing (vertical walls, flat roofs). Sloped / curved roofs and
    raked walls are measured as plan-projected roof area and perimeter x height facade;
    the script warns when it finds non-vertical, non-horizontal faces.
  - Not yet derived: guarding / balustrades, lift pits, transfer structures.

Run: Rhino 8 ScriptEditor (Python 3), with wlca_core.py in the same folder. Edit CONFIG, then run.
When exec'd without __file__ (e.g. over MCP), put WLCA_LIB_DIR = <folder of wlca_core.py> in globals.
"""

import json, os, sys, datetime
import Rhino
import Rhino.Geometry as rg
import System

try:
    doc = __rhino_doc__                      # injected when run remotely
except NameError:
    import scriptcontext
    doc = scriptcontext.doc

_lib = globals().get("WLCA_LIB_DIR") or (os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None)
if _lib and _lib not in sys.path:
    sys.path.insert(0, _lib)
import wlca_core as core                    # noqa: E402
from wlca_core import TakeoffError, ORIENTS, expand_wwr, ground_index   # noqa: E402

# ----------------------------------------------------------------------------- CONFIG
CONFIG = {
    # --- interchange header (schema v0.1) ---
    "project_id": "P-XXXX",
    "use_class": "Office",
    "target_tier": "Practice target",
    "riba_stage": 2,
    "existing_gia_demolished_m2": 0,
    "fitout_scope": "Shell & core + Cat A",
    "schema_version": "0.1",
    "library_version": "SM-0.4",             # scope matrix snapshot
    "model_version": "v0.1",
    "author": "XX",                          # assessor initials
    "method_label": "Derived",               # SM-0.2 method for massing-derived rows

    # --- geometry ---
    "massing_layers": None,                  # None = every layer except WLCA::*; or ["01_PROPOSED::Option A"]
    "base_level": None,                      # None = lowest point of the massing
    "ground_storey_height": 5.0,             # m
    "typical_storey_height": 4.0,            # m
    "storey_height_overrides": {},           # {storey_index: height_m}
    "min_storey_fraction": 1.0,              # share of a storey that must fit in a volume
    "area_schedule": None,                   # {"path": r"C:\...\schedule.xlsx", "sheet": "Office"} -> route (a)
    "schedule_tolerance": 0.03,              # flag levels where massing GEA differs from schedule by more
    "facade_zone_m": 0.30,                   # GEA -> GIA inward offset (external wall zone)
    "north_angle_deg": 0.0,                  # true north, degrees clockwise from +Y
    "wwr": {"N": 0.60, "E": 0.60, "S": 0.60, "W": 0.60},   # window-to-wall ratio on storey facade;
                                                            # 4 or 8 keys - NE etc. default to mean of neighbours

    # --- structure (v0.3): drawing route via plan_json, or numeric route; first match wins ---
    "structure": {
        "plan_json": None,                   # output of WLCA_plan_extract (typical floor)
        "core_wall_length_m_per_floor": None,
        "core_area_m2": None,                # else core_area_pct_gia x typical GIA, else schedule typical GIA - NIA
        "core_area_pct_gia": None,
        "core_wall_density_m_per_m2": 0.46,  # m of core wall per m2 core - calibrated on pilot tower (144 m / 314 m2)
        "column_count_per_floor": None,      # typical floor
        "grid_x_m": 9.0, "grid_y_m": 8.0,
        "column_edge_factor": 1.42,          # columns vs pure grid count - calibrated on pilot tower (20 on 1,012 m2, 9x8 grid)
        "column_size_m": 0.75,
        "frame": "RC flat slab",             # or PT flat slab / Steel + composite deck / Steel + CLT + concrete topping /
                                             # Steel + CLT / Glulam + CLT (PF rates, columns scaled with height)
    },
    "substructure": {
        "retaining_walls": {"source": "footprint",   # "footprint" = ground-floor perimeter x basement depth; "engineer"
                            "type": "secant",        # "secant" piled wall (default) or "rc_wall" (RET-RC-350 per m2)
                            "pile_diameter_m": 1.0,
                            "pile_spacing_m": 1.2,   # HARD-to-HARD centres; one firm pile centred between each pair
                            "pile_length_m": None,   # None = basement depth x (1 + embedment_ratio)
                            "embedment_ratio": 0.5,  # toe below formation as a share of retained height - ASSUMED, confirm
                            "liner_thickness_m": 0.20,   # RC liner inside the piled wall; 0 / None = no liner
                            "perimeter_m": None, "depth_m": None, "area_m2": None, "volume_m3": None},
        "piles": {"source": "assumed",               # "assumed" (bored, per column) | "engineer" | None
                  "diameter_m": 0.75, "per_column": 3, "length_m": 25.0,
                  "core_group": True, "core_spacing_x_dia": 3.0,   # piles under the core at 3 x dia centres over core area
                  "count": None},                    # engineer: count x diameter x length
        "caps_raft": {"source": "assumed",           # "assumed" (rule below) | "engineer" (volume_m3) | None
                      "depth_m": 1.2, "edge_m": 0.15,  # column caps: piles_per_column at core_spacing_x_dia, edge beyond pile
                      "core_thickness_m": 2.0, "core_margin_m": 0.5,   # core cap over core area + margin all round
                      "volume_m3": None},
        "basement_depth_m": None,            # massing route only (schedule gives depth from basement FTFs)
    },
    # --- scope-gap allowances (v0.8). source: "assumed" (office default) | "supplied" (your figure wins) ---
    "stairs": {"source": "drawing",          # count + flights from plan_json; "supplied" uses volume_m3
               "count": None,                # override the drawing count
               "assumed_count": 2,           # used only with no drawing and no count
               "flights_per_storey": 2, "treads_per_flight": 11, "flight_width_m": 1.2, "going_m": 0.25,   # no-drawing defaults
               "waist_m": 0.20, "landing_thickness_m": 0.20, "flight_gap_m": 0.10,                          # always assumed
               "volume_m3": None},
    "edge_beams": {"source": "assumed", "include": True, "length_m": None},
    "envelope_allowances": {
        "louvres": {"source": "assumed", "fraction_of_plant_facade": 0.5, "area_m2": None},
        "entrance_doors": {"source": "assumed", "count": 2, "area_m2_each": 15.0, "area_m2": None},
        "roof_other": {"source": "assumed", "include": True, "area_m2": None},
    },
    "plant_levels": None,                    # massing route: storey names with plant (schedule route reads Use = Plant)

    # --- build-up codes (must exist in the build-up library) ---
    "build_ups": {
        "lowest_slab":   "GF-SLAB-RC-300",
        "upper_floor":   "SLAB-RC-FLAT-250",
        "roof_slab":     "SLAB-RC-FLAT-250",
        "basement_slab": "SLAB-RC-FLAT-250",  # 1.2.2 suspended slabs below ground line
        "soffit_finish": "SOFFIT-INS-01",     # 2.5.1 insulated soffit under overhangs (NOT a second slab)
        "roof_finish":   "RF-INV-01",
        "facade_opaque": "EW-SFS-BRK-01",
        "facade_glazed": "CW-UNIT-01",
        "core_wall":     "WALL-RC-250",
        "column":        "COL-RC-750",
        "retaining_wall": "RET-RC-350",       # rc_wall, per m2
        "secant_wall":   "WALL-SECANT-RC",    # secant wall hard (RC) piles, per m3
        "secant_firm":   "WALL-SECANT-FIRM",  # secant wall firm (unreinforced) piles, per m3 net of overlaps
        "liner_wall":    "LINER-RC-200",      # RC liner to piled wall, per m2
        "pile":          "PILE-RC-600",       # per m3
        "cap_raft":      "CAP-RC-01",         # per m3
        "stair":         "STAIR-RC-01",       # 2.4 in-situ RC stairs, per m3
        "edge_beam":     "BEAM-RC-EDGE-DS",   # 2.1.2 downstand edge beam below the slab, per m
        "louvre":        "LOUVRE-AL-01",      # 2.6 plant louvres, per m2
        "door_ext":      "DOOR-EXT-GL-01",    # 2.6 entrance doors, per m2
        "roof_other":    "ROOF-OTHER-01",     # 2.3 other roof elements, per m2 of roof
    },

    # --- output ---
    "bake": True,
    "write_files": True,
    "output_dir": None,                      # None = folder of the .3dm
    "file_stem": None,                       # None = <model name>_massing_takeoff
}

TOL = doc.ModelAbsoluteTolerance if doc else 0.001
WORLD = rg.Plane.WorldXY
# ----------------------------------------------------------------------------- helpers
def unit_scale_to_m():
    return Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters)


def layer_path(idx):
    return doc.Layers[idx].FullPath


def collect_massing(cfg, warnings):
    breps, sources, errors = [], set(), []
    wanted = cfg["massing_layers"]
    for obj in doc.Objects:
        if obj.IsDeleted or not obj.Visible:
            continue
        lp = layer_path(obj.Attributes.LayerIndex)
        if wanted is not None and lp not in wanted:
            continue
        if wanted is None and lp.startswith("WLCA"):
            continue
        g = obj.Geometry
        if isinstance(g, rg.Extrusion):
            g = g.ToBrep()
        if isinstance(g, rg.Brep):
            if not g.IsSolid:
                errors.append("Open brep %s on %s" % (obj.Id, lp))
                continue
            breps.append(g); sources.add(lp)
        elif isinstance(g, rg.Mesh):
            errors.append("Mesh %s on %s - convert to closed polysurface" % (obj.Id, lp))
        elif isinstance(g, (rg.Curve, rg.TextEntity, rg.Point)) or g is None:
            continue
        else:
            warnings.append("Ignored %s on %s" % (type(g).__name__, lp))
    if errors:
        raise TakeoffError("Geometry check failed:\n  " + "\n  ".join(errors))
    if not breps:
        raise TakeoffError("No closed massing solids found on %s" % (wanted or "visible layers"))
    for b in breps:
        for f in b.Faces:
            ok, pl = f.TryGetPlane(TOL * 10)
            if ok:
                nz = abs(pl.ZAxis.Z)
                if 0.02 < nz < 0.98:
                    warnings.append("Sloped planar face found - roof/facade measured as plan projection x height (approximate)")
                    return breps, sorted(sources)
            else:
                warnings.append("Curved face found - roof/facade measured as plan projection x height (approximate)")
                return breps, sorted(sources)
    return breps, sorted(sources)


def section(brep, z, z_target):
    """Closed section curves of brep at height z, moved to z_target."""
    plane = rg.Plane(rg.Point3d(0, 0, z), rg.Vector3d.ZAxis)
    rc = rg.Intersect.Intersection.BrepPlane(brep, plane, TOL)
    crvs = rc[1] if isinstance(rc, tuple) else None
    if not crvs:
        return []
    joined = rg.Curve.JoinCurves(crvs, TOL * 2)
    xf = rg.Transform.Translation(0, 0, z_target - z)
    out = []
    for c in joined:
        if c.IsClosed:
            c.Transform(xf); out.append(c)
    return out


def union(curves):
    if len(curves) <= 1:
        return list(curves)
    res = rg.Curve.CreateBooleanUnion(curves, TOL)
    if res and len(res) > 0:
        return list(res)
    # fallback: tiny outward nudge removes coincident-edge failures
    nudged = []
    for c in curves:
        o = best_offset(c, 2 * TOL, outward=True)
        nudged.append(o if o else c)
    res = rg.Curve.CreateBooleanUnion(nudged, TOL)
    if res and len(res) > 0:
        return list(res)
    raise TakeoffError("Curve union failed at z=%.3f" % curves[0].PointAtStart.Z)


def regions(curves):
    if not curves:
        return []
    b = rg.Brep.CreatePlanarBreps(curves, TOL)
    return list(b) if b else []


def area_of(curves):
    return sum(rg.AreaMassProperties.Compute(b).Area for b in regions(curves))


def loop_area(c):
    amp = rg.AreaMassProperties.Compute(c)
    return amp.Area if amp else 0.0


def best_offset(c, d, outward):
    """Offset closed planar curve by d; outward=True picks the larger result."""
    cands = []
    for s in (d, -d):
        try:
            r = c.Offset(rg.Plane(c.PointAtStart, rg.Vector3d.ZAxis), s, TOL,
                         rg.CurveOffsetCornerStyle.Sharp)
        except Exception:
            r = None
        if r and len(r) == 1 and r[0].IsClosed:
            cands.append(r[0])
    if not cands:
        return None
    cands.sort(key=loop_area)
    return cands[-1] if outward else cands[0]


def is_hole(c, loops):
    for o in loops:
        if o is c:
            continue
        rel = rg.Curve.PlanarClosedCurveRelationship(c, o, WORLD, TOL)
        if rel == rg.RegionContainment.AInsideB:
            return True
    return False


def gia_curves(loops, zone, warnings, label):
    out = []
    for c in loops:
        hole = is_hole(c, loops)
        o = best_offset(c, zone, outward=hole)
        if o is None:
            warnings.append("%s: GIA offset failed on one loop - perimeter x zone used" % label)
            return None
        out.append(o)
    return out


def orientation(nx, ny, north_deg):
    return core.orientation(nx, ny, north_deg)


def clear_previous(layer_idx, prefix):
    n = 0
    for o in list(doc.Objects.FindByLayer(doc.Layers[layer_idx]) or []):
        if (o.Attributes.Name or "").startswith(prefix):
            doc.Objects.Delete(o, True); n += 1
    return n


def perimeter_by_orientation(loops, north_deg):
    """Length of region boundary by outward-normal orientation."""
    out = dict((k, 0.0) for k in ORIENTS)
    regs = regions(loops)
    if not regs:
        return out
    for c in loops:
        ok, pl = c.TryGetPolyline()
        if ok:
            pts = list(pl)
        else:
            ts = c.DivideByLength(0.25, True)
            pts = [c.PointAt(t) for t in ts] + [c.PointAtEnd] if ts else []
        for a, b in zip(pts[:-1], pts[1:]):
            L = a.DistanceTo(b)
            if L < TOL:
                continue
            tx, ty = (b.X - a.X) / L, (b.Y - a.Y) / L
            m = rg.Point3d((a.X + b.X) / 2, (a.Y + b.Y) / 2, a.Z)
            nx, ny = ty, -tx
            probe = rg.Point3d(m.X + nx * 0.05, m.Y + ny * 0.05, m.Z)
            inside = any(r.ClosestPoint(probe).DistanceTo(probe) < 1e-4 for r in regs)
            if inside:
                nx, ny = -nx, -ny
            out[orientation(nx, ny, north_deg)] += L
    return out


def ensure_layer(path, color=None):
    idx = doc.Layers.FindByFullPath(path, -1)
    if idx >= 0:
        return idx
    parent_id = System.Guid.Empty
    parts = path.split("::")
    for i in range(len(parts)):
        sub = "::".join(parts[: i + 1])
        idx = doc.Layers.FindByFullPath(sub, -1)
        if idx < 0:
            lay = Rhino.DocObjects.Layer()
            lay.Name = parts[i]
            lay.ParentLayerId = parent_id
            if color is not None and i == len(parts) - 1:
                lay.Color = color
            idx = doc.Layers.Add(lay)
        parent_id = doc.Layers[idx].Id
    return idx


def bake(curves, layer_idx, name, xf=None):
    ids = []
    for c in curves:
        if xf is not None:
            c = c.DuplicateCurve(); c.Transform(xf)
        a = Rhino.DocObjects.ObjectAttributes()
        a.LayerIndex = layer_idx
        a.Name = name
        ids.append(doc.Objects.AddCurve(c, a))
    return ids



# ----------------------------------------------------------------------------- main
def run(cfg):
    global TOL
    warnings = []
    s = unit_scale_to_m()                      # model units -> metres; all maths runs in metres
    TOL = doc.ModelAbsoluteTolerance * s
    to_model = rg.Transform.Scale(rg.Point3d.Origin, 1.0 / s)

    breps, src_layers = collect_massing(cfg, warnings)
    if abs(s - 1.0) > 1e-9:
        sc = rg.Transform.Scale(rg.Point3d.Origin, s)
        breps = [b.DuplicateBrep() for b in breps]
        for b in breps:
            b.Transform(sc)
        warnings.append("Model units %s - measured in metres (scale %g); base_level is in metres" % (doc.ModelUnitSystem, s))
    boxes = [b.GetBoundingBox(True) for b in breps]
    zmin = min(bb.Min.Z for bb in boxes)
    zmax = max(bb.Max.Z for bb in boxes)

    # ---- floor arrangement: route (a) area schedule, or route (b) storey heights
    sched = None
    if cfg.get("area_schedule"):
        sched = core.parse_area_schedule(cfg["area_schedule"], warnings)
        gi = ground_index(sched)
        if gi is None:
            raise TakeoffError("Schedule has no ground level (named 0 / G / GF / Ground)")
        if sched[gi]["aod"] is not None:
            base = sched[gi]["aod"]
            if abs(base - zmin) > 0.05:
                warnings.append("Schedule ground AOD %.2f vs massing base %.2f - is the model in AOD? Using the schedule" % (base, zmin))
        else:
            base = cfg["base_level"] if cfg["base_level"] is not None else zmin
            core.stack_aod(sched, gi, base)
        storey_defs = [(lv["name"], lv["aod"], lv["ftf"]) for lv in sched[gi:]]
    else:
        base = cfg["base_level"] if cfg["base_level"] is not None else zmin
        storey_defs, z0, i = [], base, 0
        while z0 < zmax - TOL:
            h = cfg["storey_height_overrides"].get(i, cfg["ground_storey_height"] if i == 0 else cfg["typical_storey_height"])
            storey_defs.append(("L%02d" % i, z0, h)); z0 += h; i += 1
    if base > zmin + TOL:
        warnings.append("Massing extends %.2f m below base level - below-ground volume not sliced as storeys" % (base - zmin))
    typ_h = sorted(h for _, _, h in storey_defs)[len(storey_defs) // 2]

    # ---- slice the massing at each above-ground storey
    storeys = []
    frac = cfg["min_storey_fraction"]
    for idx, (name, z0, h) in enumerate(storey_defs):
        secs = []
        for b, bb in zip(breps, boxes):
            if bb.Min.Z <= z0 + TOL and bb.Max.Z >= z0 + frac * h - TOL:
                zs = z0 + min(h / 2.0, (bb.Max.Z - z0) / 2.0)
                secs += section(b, zs, z0)
        loops = union(secs) if secs else []
        if loops:
            gea = area_of(loops)
            per = sum(c.GetLength() for c in loops)
            per_o = perimeter_by_orientation(loops, cfg["north_angle_deg"])
            gcs = gia_curves(loops, cfg["facade_zone_m"], warnings, name)
            gia = sum(loop_area(c) * (-1 if is_hole(c0, loops) else 1) for c, c0 in zip(gcs, loops)) if gcs else gea - per * cfg["facade_zone_m"]
        else:
            gea = gia = per = 0.0; per_o = dict((k, 0.0) for k in ORIENTS); gcs = None
            if sched is None:
                continue
        storeys.append(dict(index=idx, name=name, z=round(z0, 3), height=h, gea=gea, gia=gia, perimeter=per,
                            facade_by_orient=dict((k, v * h) for k, v in per_o.items()), loops=loops, gia_loops=gcs))
    if not any(st["gea"] > 0 for st in storeys):
        raise TakeoffError("No full storey fits in the massing - check storey heights")

    # ---- z-bands for envelope measurement (always from the massing)
    zl = sorted(set([round(bb.Min.Z, 4) for bb in boxes] + [round(bb.Max.Z, 4) for bb in boxes]))
    bands = []
    for b0, b1 in zip(zl[:-1], zl[1:]):
        if b1 - b0 < TOL:
            continue
        mid = (b0 + b1) / 2.0
        secs = []
        for b, bb in zip(breps, boxes):
            if bb.Min.Z <= mid <= bb.Max.Z:
                secs += section(b, mid, b0)
        loops = union(secs) if secs else []
        per_o = perimeter_by_orientation(loops, cfg["north_angle_deg"]) if loops else dict((k, 0.0) for k in ORIENTS)
        bands.append(dict(z0=b0, z1=b1, area=area_of(loops), loops=loops,
                          facade_by_orient=dict((k, v * (b1 - b0)) for k, v in per_o.items())))
    m_roof, m_soffit, m_roof_levels = 0.0, 0.0, []
    for k, bd in enumerate(bands):
        above = bands[k + 1] if k + 1 < len(bands) else None
        if above is None:
            r, sft = bd["area"], 0.0
        else:
            if bd["loops"] and above["loops"]:
                up = []
                for c in above["loops"]:          # bring the band above onto this band's plane
                    c2 = c.DuplicateCurve(); c2.Transform(rg.Transform.Translation(0, 0, bd["z0"] - above["z0"])); up.append(c2)
                both = area_of(union(bd["loops"] + up))
            else:
                both = bd["area"] + above["area"]
            r, sft = both - above["area"], both - bd["area"]
        if r > 0.01:
            m_roof += r; m_roof_levels.append(dict(z=round(bd["z1"], 3), area=round(r, 1)))
        if sft > 0.01:
            m_soffit += sft

    fac_total = dict((k, sum(bd["facade_by_orient"][k] for bd in bands)) for k in ORIENTS)
    fac_storey = dict((k, sum(st["facade_by_orient"][k] for st in storeys)) for k in ORIENTS)
    # Envelope (z-bands) is the measured truth; storey facade only sets where glazing can go.
    fac_parapet = dict((k, fac_total[k] - fac_storey[k]) for k in ORIENTS)
    recon = sum(v for v in fac_parapet.values() if v < 0)
    if recon < -0.01 * sum(fac_total.values()):
        warnings.append("Storey facade exceeds envelope by %.0f m2 (>1%%) - check storey heights against massing tops" % -recon)

    tops = []
    for bb in boxes:
        last = max([st["z"] + st["height"] for st in storeys if st["gea"] > 0 and st["z"] + st["height"] <= bb.Max.Z + TOL] or [base])
        r = bb.Max.Z - last
        if r > 0.05:
            tops.append(dict(top=round(bb.Max.Z, 3), last_storey_top=round(last, 3), residual_m=round(r, 3)))
    tops = sorted([dict(t) for t in set(tuple(sorted(d.items())) for d in tops)], key=lambda d: d["top"])
    for t in tops:
        if t["residual_m"] > 0.5 * typ_h:
            warnings.append("Volume top +%.2f is %.2f m above its last full storey - parapet/plant screen, or a storey the heights miss?" % (t["top"], t["residual_m"]))

    # ---- horizontal quantities (rules in wlca_core)
    recon_rows = []
    if sched:
        hz, roof_levels = core.schedule_horizontals(sched)
        gia_total = sum(lv["gia"] for lv in sched)
        gea_total = sum(lv["gea"] for lv in sched)
        recon_rows = core.reconcile_schedule(sched, dict((st["name"], st["gea"]) for st in storeys),
                                             cfg["schedule_tolerance"], warnings)
        gia_source = "Area schedule: %s [%s]" % (os.path.basename(cfg["area_schedule"]["path"]), cfg["area_schedule"].get("sheet", ""))
    else:
        hz = dict(lowest=bands[0]["area"], basement=0.0, upper=sum(st["gea"] for st in storeys if st["index"] > 0),
                  roof=m_roof, podium=0.0, soffit=m_soffit)
        roof_levels = m_roof_levels
        gia_total = sum(st["gia"] for st in storeys)
        gea_total = sum(st["gea"] for st in storeys)
        gia_source = "Massing take-off: WLCA::GIA curves = storey plates offset %.2f m (model %s)" % (cfg["facade_zone_m"], doc.Name or "unsaved")

    # ---- structure and substructure (rules in wlca_core)
    S, SUB, B = cfg["structure"], cfg["substructure"], cfg["build_ups"]
    if sched:
        lv_all = [(lv["name"], lv["ftf"], lv["gea"], lv["gia"], lv["nia"]) for lv in sched]
        n_base = ground_index(sched)
    else:
        lv_all = [(st["name"], st["height"], st["gea"], st["gia"], None) for st in storeys if st["gea"] > 0]
        n_base = 0
    plan = None
    if S.get("plan_json"):
        with open(S["plan_json"], encoding="utf-8") as f:
            plan = json.load(f)
    st_rows, sinfo = core.structure_rows(lv_all, plan, S, cfg["method_label"], warnings, B["core_wall"], B["column"])
    g0 = storeys[0]
    sub_rows, depth = core.substructure_rows(lv_all, n_base, bool(sched), (g0["name"], g0["perimeter"], g0["gea"]),
                                             sched[0]["gea"] if sched else g0["gea"], sinfo["columns_by_level"],
                                             sinfo["core_area_m2"], sinfo["core_area_source"], SUB, cfg["method_label"],
                                             warnings, B["liner_wall"])
    st_rows = st_rows + sub_rows

    wwr = expand_wwr(cfg["wwr"])
    glazed = sum(fac_storey[k] * wwr[k] for k in ORIENTS)
    opaque = sum(fac_total[k] - fac_storey[k] * wwr[k] for k in ORIENTS)   # glazed + opaque = envelope

    # ---- scope-gap allowances (rules in wlca_core)
    gap_rows = core.stair_rows(lv_all, sinfo["typical_level"], plan, cfg["stairs"], cfg["method_label"], warnings)
    above = [st for st in storeys if st["gea"] > 0]
    gap_rows += core.edge_beam_rows([(st["name"], st["perimeter"]) for st in above], cfg["edge_beams"], cfg["method_label"])
    if sched:
        plant = [lv["name"] for lv in sched if "plant" in (lv.get("use") or "").lower()]
        plant_src = "schedule Use = Plant: " + (", ".join(n for n in plant if n in [st["name"] for st in above]) or "none above ground")
    else:
        plant = cfg.get("plant_levels") or []
        plant_src = "CONFIG plant_levels: " + (", ".join(plant) or "none")
    plant_fac = sum(sum(st["facade_by_orient"].values()) for st in above if st["name"] in plant)
    env_rows, glazed, opaque = core.envelope_allowance_rows(plant_fac, plant_src, glazed, opaque, hz["roof"],
                                                            cfg["envelope_allowances"], cfg["method_label"])
    st_rows = st_rows + gap_rows + env_rows

    # ---- bake
    if cfg["bake"]:
        li_gea = ensure_layer("WLCA::_Massing::GEA floor plates", System.Drawing.Color.Gray)
        li_gia = ensure_layer("WLCA::GIA", System.Drawing.Color.FromArgb(0, 150, 80))
        clear_previous(li_gea, "GEA "); clear_previous(li_gia, "GIA ")   # re-runs replace, not duplicate
        for st in storeys:
            if st["loops"]:
                bake(st["loops"], li_gea, "GEA %s" % st["name"], to_model)
            if st["gia_loops"]:
                bake(st["gia_loops"], li_gia, "GIA %s" % st["name"], to_model)
        doc.Views.Redraw()

    # ---- interchange rows
    src = " | ".join(src_layers) + (" + " + gia_source if sched else "")
    hsrc = "schedule" if sched else "massing"
    rows = core.build_rows(cfg, hz, roof_levels, hsrc, glazed, opaque, sum(fac_parapet.values()), wwr, st_rows, src)
    S0 = cfg["structure"]
    rows, frame_info = core.apply_frame(rows, S0.get("frame") or "RC flat slab", S0["grid_x_m"], S0["grid_y_m"],
                                        len(above), cfg["build_ups"], cfg["method_label"])

    header = dict(project_id=cfg["project_id"], use_class=cfg["use_class"], target_tier=cfg["target_tier"],
                  riba_stage=cfg["riba_stage"], gia_m2=round(gia_total, 1),
                  existing_gia_demolished_m2=cfg["existing_gia_demolished_m2"], fitout_scope=cfg["fitout_scope"],
                  schema_version=cfg["schema_version"], library_version=cfg["library_version"],
                  model_version=cfg["model_version"], gia_source=gia_source)

    geometry = dict(
        floor_source=hsrc, base_level=round(base, 3), top_level=round(zmax, 3), height_m=round(zmax - base, 2),
        storey_count=len(storeys), gea_m2=round(gea_total, 1), gia_m2=round(gia_total, 1),
        gia_gea_ratio=round(gia_total / gea_total, 4),
        massing_gea_above_ground_m2=round(sum(st["gea"] for st in storeys), 1),
        massing_gia_above_ground_m2=round(sum(st["gia"] for st in storeys), 1),
        horizontals=dict((k, round(v, 1)) for k, v in hz.items()),
        roof_levels=roof_levels, massing_roof_levels=m_roof_levels, volume_tops=tops,
        facade_total_by_orient=dict((k, round(v, 1)) for k, v in fac_total.items()),
        facade_storey_by_orient=dict((k, round(v, 1)) for k, v in fac_storey.items()),
        facade_total_m2=round(sum(fac_total.values()), 1),
        facade_to_gia=round(sum(fac_total.values()) / gia_total, 4),
        schedule_reconciliation=recon_rows,
        structure=dict(sinfo, basement_depth_m=depth, frame=frame_info),
        storeys=[dict(index=st["index"], name=st["name"], z=st["z"], height=st["height"], gea=round(st["gea"], 1),
                      gia=round(st["gia"], 1), perimeter=round(st["perimeter"], 1),
                      facade_by_orient=dict((k, round(v, 1)) for k, v in st["facade_by_orient"].items()))
                 for st in storeys],
        bands=[dict(z0=bd["z0"], z1=bd["z1"], area=round(bd["area"], 1),
                    facade_by_orient=dict((k, round(v, 1)) for k, v in bd["facade_by_orient"].items()))
               for bd in bands],
        config=dict((k, v) for k, v in cfg.items() if k not in ("output_dir",)),
        warnings=warnings,
        run_at=datetime.datetime.now().isoformat(timespec="seconds"),
    )

    # ---- write
    paths = []
    if cfg["write_files"]:
        out_dir = cfg["output_dir"] or (os.path.dirname(doc.Path) if doc.Path else None)
        if not out_dir:
            raise TakeoffError("Save the model or set output_dir")
        stem = cfg["file_stem"] or (os.path.splitext(doc.Name)[0] + "_massing_takeoff")
        jp = os.path.join(out_dir, stem + ".json")
        with open(jp, "w", encoding="utf-8") as f:
            json.dump(dict(header=header, rows=rows, geometry=geometry), f, indent=2)
        cp = os.path.join(out_dir, stem + ".csv")
        cols = ["project_id", "element_id", "nrm_code", "build_up_code", "quantity", "unit", "method",
                "stage", "model_version", "author", "source_layer", "include", "notes"]
        with open(cp, "w", encoding="utf-8-sig", newline="") as f:
            for k, v in header.items():
                f.write("# %s: %s\n" % (k, v))
            f.write(",".join(cols) + "\n")
            for r in rows:
                f.write(",".join('"%s"' % str(r[c]).replace('"', "'") for c in cols) + "\n")
        sp = os.path.join(out_dir, stem + "_storeys.csv")
        rec = dict((r["level"], r) for r in recon_rows)
        with open(sp, "w", encoding="utf-8-sig", newline="") as f:
            f.write("level,z_m,height_m,massing_GEA_m2,massing_GIA_m2,perimeter_m," + ",".join("facade_%s_m2" % k for k in ORIENTS)
                    + ",schedule_GEA_m2,schedule_GIA_m2,schedule_NIA_m2,delta_GEA_pct,status\n")
            for lv in (recon_rows if sched else []):
                if lv["massing_gea"] is None:
                    f.write("%s,%.3f,%.2f,,,,%s,%.1f,%.1f,%s,,%s\n" % (lv["level"], lv["aod"], lv["ftf"], "," * (len(ORIENTS) - 1),
                            lv["schedule_gea"], lv["schedule_gia"], "" if lv["schedule_nia"] is None else lv["schedule_nia"], lv["status"]))
            for st in geometry["storeys"]:
                fo = st["facade_by_orient"]; r = rec.get(st["name"])
                f.write("%s,%.3f,%.2f,%.1f,%.1f,%.1f," % (st["name"], st["z"], st["height"], st["gea"], st["gia"], st["perimeter"])
                        + ",".join("%.1f" % fo[k] for k in ORIENTS)
                        + (",%.1f,%.1f,%s,%s,%s\n" % (r["schedule_gea"], r["schedule_gia"], "" if r["schedule_nia"] is None else r["schedule_nia"],
                                                     "" if r["delta_pct"] is None else r["delta_pct"], r["status"]) if r else ",,,,,\n"))
        paths = [cp, jp, sp]

    return header, rows, geometry, paths


if not globals().get("WLCA_NO_AUTORUN"):
    try:
        H, R, G, P = run(CONFIG)
        print("Floors from %s | storeys %d | GEA %.0f m2 | GIA %.0f m2 | facade %.0f m2" % (
            G["floor_source"], G["storey_count"], G["gea_m2"], G["gia_m2"], G["facade_total_m2"]))
        for r in R:
            print("  %-6s %-18s %10.1f %s" % (r["nrm_code"], r["build_up_code"], r["quantity"], r["unit"]))
        for w in G["warnings"]:
            print("WARNING:", w)
        for p in P:
            print("Wrote", p)
    except TakeoffError as e:
        print("TAKE-OFF REFUSED:", e)
