#! python3
"""
WLCA plan reader - Rhino route  v0.1  (draft for review)
Office WLCA template - typical floor plan read from Rhino layers (cores, columns, stairs)

Drafted by an AI agent (Claude) - review before trusting.

Replaces the PDF plan extractor as the default drawing route (decision D5). The plan is CAD linework in the
Rhino model - imported DWG/DGN, pasted from another .3dm, or drawn - at true scale, anywhere in the model.
It returns the same dict as WLCA_plan_extract, so the take-off's structure_rows / stair_rows use it unchanged.

  core walls  thin closed outlines or hatches, 0.10-0.50 m thick: plan area A, thickness t from the outline
              (exact for a rectangle: P = 2(L + t), A = L t); length = A / t
  columns     circles 0.20-1.50 m across; squares and rectangles (closed polylines, each side 0.20-1.50 m, long side
              at most 3 x the short one, so wall stubs and treads stay out); blocks by their box. A rectangle
              counts as the square of the same area (the take-off models square columns)
  stairs      treads = rectangles 0.18-0.40 x 0.80-2.20 m; runs of treads make flights, flights make stairs
              (same grouping as the PDF extractor). The plan may be rotated: rectangles are read in the
              plan's own frame (dominant rectangle angle).
  boundary    only shapes inside the floor plate count - the largest closed outline on the wall layer
              (facade line) unless a boundary curve is given. Keeps other drawings on the same layer out.
  units       the file's unit header is not trusted blindly (a DWG said millimetres for metre coordinates):
              the scale that makes columns and walls plausible wins, and a change is reported.

The geometry logic below is plain Python (testable without Rhino). `read_plan()` at the bottom is the Rhino
adapter: it collects curves, hatches and block instances from the chosen layers (and their sublayers).
"""
import fnmatch
import math

from wlca_plan_extract import group_stairs

DEFAULTS = {
    "wall_thickness_range_m": [0.10, 0.50],
    "column_size_range_m": [0.20, 1.50],
    "column_shapes": ["circle", "square", "rectangle"],
    "column_max_aspect": 3.0,                    # rectangle long side / short side; longer = a wall stub or blade
    "column_touch_tol_m": 0.02,                  # a square / rectangle touching another small shape is not a column
    "large_outline_m2": 20.0,                    # facade lines and other big outlines may touch columns
    "tread_going_range_m": [0.18, 0.40],
    "tread_width_range_m": [0.80, 2.20],
    "min_treads_per_flight": 4,
    "stair_cluster_gap_m": 1.0,
    "min_boundary_area_m2": 100.0,               # a floor plate is at least this big
}
# office settings may override; these are generic CAD names, matched case-insensitively on the full layer path
LAYER_PATTERNS = {
    "walls": ["*wall*", "*a-wall*", "*s-wall*", "*core*"],
    "columns": ["*col*", "*wall*"],
    "stairs": ["*stair*", "*strs*"],
}
SCALES = [1.0, 0.001, 1000.0, 0.0254, 0.3048, 0.01, 0.1, 10.0]


# ----------------------------------------------------------------------------- shape helpers
# shape = dict(id, layer, closed, area, perim, circle=(x, y, d) | None, pts=[(x, y), ...] | None, bb=(x0, y0, x1, y1))

def scaled(shape, k):
    if k == 1.0:
        return shape
    s = dict(shape)
    s["area"] = (shape.get("area") or 0.0) * k * k
    s["perim"] = shape["perim"] * k
    s["bb"] = tuple(v * k for v in shape["bb"])
    if shape.get("circle"):
        s["circle"] = tuple(v * k for v in shape["circle"])
    if shape.get("pts"):
        s["pts"] = [(x * k, y * k) for x, y in shape["pts"]]
    return s


def thickness(area, perim):
    """Thickness of a thin closed outline: exact for a rectangle (P = 2(L + t), A = L t), close for L / U shapes."""
    if not perim or area <= 0:
        return 0.0
    h = perim / 2.0
    disc = h * h - 4.0 * area
    return (h - math.sqrt(disc)) / 2.0 if disc >= 0 else 2.0 * area / perim


def corners(pts, tol=0.02):
    """Closed polyline points without the closing point, repeated points or points along a straight edge."""
    p = list(pts)
    if len(p) >= 2 and abs(p[0][0] - p[-1][0]) < 1e-9 and abs(p[0][1] - p[-1][1]) < 1e-9:
        p = p[:-1]
    q = []
    for v in p:
        if not q or math.hypot(v[0] - q[-1][0], v[1] - q[-1][1]) > 1e-6:
            q.append(v)
    if len(q) > 1 and math.hypot(q[0][0] - q[-1][0], q[0][1] - q[-1][1]) <= 1e-6:
        q.pop()
    changed = True
    while changed and len(q) > 3:
        changed = False
        for i in range(len(q)):
            a, b, c = q[i - 1], q[i], q[(i + 1) % len(q)]
            ab, bc = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
            la, lb = math.hypot(*ab), math.hypot(*bc)
            if la and lb and abs(ab[0] * bc[1] - ab[1] * bc[0]) <= tol * la * lb and ab[0] * bc[0] + ab[1] * bc[1] > 0:
                q.pop(i)                       # b sits on the straight line a-c
                changed = True
                break
    return q


def rect_frame(pts, tol=0.02):
    """(cx, cy, angle_rad, w, h) if pts (closed polyline) is a rectangle, else None. angle in [0, pi/2).
    Extra points along an edge and repeated points are ignored."""
    p = corners(pts, tol)
    if len(p) != 4:
        return None
    e = [(p[(i + 1) % 4][0] - p[i][0], p[(i + 1) % 4][1] - p[i][1]) for i in range(4)]
    ln = [math.hypot(*v) for v in e]
    if min(ln) <= 0:
        return None
    for i in range(4):
        a, b = e[i], e[(i + 1) % 4]
        if abs(a[0] * b[0] + a[1] * b[1]) > tol * ln[i] * ln[(i + 1) % 4]:
            return None
    ang = math.atan2(e[0][1], e[0][0]) % (math.pi / 2)
    w, h = ln[0], ln[1]
    cx = sum(q[0] for q in p) / 4.0
    cy = sum(q[1] for q in p) / 4.0
    return cx, cy, ang, w, h


def dominant_angle(shapes):
    """Plan orientation (radians, 0..pi/2) from the rectangles, weighted by perimeter; 0 if none."""
    bins = {}
    for s in shapes:
        if s.get("pts") and s["closed"]:
            rf = rect_frame(s["pts"])
            if rf:
                k = round(math.degrees(rf[2]) * 2) / 2.0 % 90
                bins[k] = bins.get(k, 0.0) + s["perim"]
    if not bins:
        return 0.0
    return math.radians(max(bins, key=bins.get))


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            inside = not inside
    return inside


def centre(s):
    if s.get("circle"):
        return s["circle"][0], s["circle"][1]
    b = s["bb"]
    return (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0


def plate_boundary(shapes, min_area):
    """Largest closed outline (with points) on the wall layer, if floor-plate sized."""
    best = None
    for s in shapes:
        if s["closed"] and not s.get("circle") and s.get("pts") and (s.get("area") or 0) >= min_area:
            if best is None or s["area"] > best["area"]:
                best = s
    return best


def _seg_dist(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def outline(s):
    """Closed outline points of a shape (polyline points, or the box of a block / circle)."""
    if s.get("pts"):
        p = list(s["pts"])
        return p if p[0] == p[-1] else p + [p[0]]
    x0, y0, x1, y1 = s["bb"]
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def touches(a, b, tol):
    """True when outlines a and b (closed point lists) touch, overlap or come within tol of each other."""
    for P, Q in ((a, b), (b, a)):
        for v in P[:-1]:
            if point_in_poly(v[0], v[1], Q):
                return True
            for i in range(len(Q) - 1):
                if _seg_dist(v, Q[i], Q[i + 1]) <= tol:
                    return True
    return False


# ----------------------------------------------------------------------------- classification
def box_column(w, h, cfg):
    """("square" | "rectangle", equivalent square side) for a w x h box that reads as a column, else None.
    A rectangle counts as the square of the same area, so the concrete volume is kept."""
    lo, hi = cfg["column_size_range_m"]
    a, b = sorted((w, h))
    if a < lo or b > hi:
        return None
    shapes = cfg["column_shapes"]
    if b - a <= 0.05 * b:
        return ("square", (a + b) / 2.0) if ("square" in shapes or "rectangle" in shapes) else None
    if "rectangle" in shapes and b <= cfg.get("column_max_aspect", 3.0) * a:
        return ("rectangle", math.sqrt(a * b))
    return None


def column_size(s, cfg):
    lo, hi = cfg["column_size_range_m"]
    if s.get("circle"):
        d = s["circle"][2]
        return ("circle", d) if "circle" in cfg["column_shapes"] and lo <= d <= hi else None
    if s["closed"] and s.get("pts") and not s.get("block"):
        rf = rect_frame(s["pts"])
        return box_column(rf[3], rf[4], cfg) if rf else None
    if s.get("block"):
        b = s["bb"]
        return box_column(b[2] - b[0], b[3] - b[1], cfg)
    return None


def wall_piece(s, cfg):
    if not s["closed"] or s.get("circle") or s.get("block"):
        return None
    t = thickness(s.get("area") or 0.0, s["perim"])
    lo, hi = cfg["wall_thickness_range_m"]
    return t if lo <= t <= hi else None


def tread_boxes(shapes, ang, cfg):
    """Rectangles in tread range, rotated into the plan frame -> axis-aligned boxes for group_stairs."""
    c, s_ = math.cos(-ang), math.sin(-ang)
    out = []
    for s in shapes:
        if not (s["closed"] and s.get("pts")):
            continue
        rf = rect_frame(s["pts"])
        if not rf:
            continue
        xs, ys = zip(*[(x * c - y * s_, x * s_ + y * c) for x, y in s["pts"]])
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def is_tread(s, cfg):
    rf = s["closed"] and s.get("pts") and rect_frame(s["pts"])
    return bool(rf) and cfg["tread_going_range_m"][0] <= min(rf[3], rf[4]) <= cfg["tread_going_range_m"][1] \
        and cfg["tread_width_range_m"][0] <= max(rf[3], rf[4]) <= cfg["tread_width_range_m"][1]


def score_scale(walls, cols, k, cfg):
    n = 0
    for s in cols:
        if s.get("circle") and cfg["column_size_range_m"][0] <= s["circle"][2] * k <= cfg["column_size_range_m"][1]:
            n += 1
        elif s["closed"] and s.get("pts") and not s.get("block"):
            rf = rect_frame(s["pts"])
            if rf and box_column(rf[3] * k, rf[4] * k, cfg):
                n += 1
    lo, hi = cfg["wall_thickness_range_m"]
    for s in walls:
        if s["closed"] and not s.get("circle"):
            t = thickness((s.get("area") or 0) * k * k, s["perim"] * k)
            if lo <= t <= hi:
                n += 1
    return n


def check_scale(walls, cols, cfg):
    """Factor on top of the file units that makes columns and walls plausible; 1.0 unless another is clearly better."""
    sc = dict((k, score_scale(walls, cols, k, cfg)) for k in SCALES)
    best = max(sc, key=sc.get)
    if sc[best] > 0 and (sc[1.0] == 0 or sc[best] >= 3 * sc[1.0]):
        return best, sc
    return 1.0, sc


def measure(walls, cols, stairs, cfg=None, boundary=None, source="Rhino layers"):
    """Shapes (metres, file units applied) per role -> (plan dict like WLCA_plan_extract, ids, notes).

    walls / cols / stairs: shape lists from the chosen layers (cols may be the same list as walls).
    boundary: shape to clip to, or None = largest closed outline on the wall layer."""
    C = dict(DEFAULTS)
    C.update(cfg or {})
    notes = []
    k, sc = check_scale(walls, cols, C)
    if k != 1.0:
        notes.append("Units: the plan only makes sense x %g (file units look wrong - e.g. a DWG saying millimetres for "
                     "metre coordinates); applied. Check the highlighted objects." % k)
        walls, cols, stairs = ([scaled(s, k) for s in xs] for xs in (walls, cols, stairs))
        if boundary:
            boundary = scaled(boundary, k)
    bnd = boundary or plate_boundary(walls, C["min_boundary_area_m2"])
    poly = bnd.get("pts") if bnd else None
    if poly:
        keep = lambda xs: [s for s in xs if s is not bnd and s.get("id") != bnd.get("id") and point_in_poly(*centre(s), poly=poly)]  # noqa: E731
        every = dict((id(x), x) for x in walls + cols + stairs)
        walls, cols, stairs = keep(walls), keep(cols), keep(stairs)
        dropped = len(every) - 1 - len(set(id(x) for x in walls + cols + stairs))
        notes.append("Floor plate: %s, %.0f m2; %d objects outside it ignored." % (
            "boundary curve" if boundary else "largest closed outline on the wall layer", bnd.get("area") or 0, dropped))
    else:
        notes.append("No floor-plate outline found on the wall layer - everything on the chosen layers is counted.")

    ids = {"walls": [], "columns": [], "stairs": []}
    # stairs first, then columns, then walls: a tread is never a column or a wall, a column never a wall
    ang = dominant_angle(stairs)
    boxes = tread_boxes(stairs, ang, C)
    st = group_stairs(boxes, tuple(C["tread_going_range_m"]), tuple(C["tread_width_range_m"]),
                      C["min_treads_per_flight"], C["stair_cluster_gap_m"])
    treads = [f for s in st for f in s["flights"]]
    # one object may sit in several role lists (shared layers, or copies after a units fix): match by Rhino id
    key = lambda x: x.get("id") or id(x)      # noqa: E731
    tread_ids = set()
    if st:
        for s in stairs:
            if is_tread(s, C):
                ids["stairs"].append(s.get("id"))
                tread_ids.add(key(s))
    cands = []
    for s in cols:
        if key(s) in tread_ids:
            continue
        cs = column_size(s, C)
        if cs:
            cands.append((s, cs))
    # a square / rectangle is a column only when it stands free: one touching a wall piece, a nib, or a row of
    # other boxes (shafts, tiles) is not. Large outlines (facade lines) may touch columns.
    others = dict((key(x), x) for x in walls + cols if key(x) not in tread_ids and x.get("closed")
                  and (x.get("area") or 0) < C["large_outline_m2"])
    touching = 0
    keep_c = []
    for s, cs in cands:
        if cs[0] != "circle":
            o = outline(s)
            bx = s["bb"]
            t = C["column_touch_tol_m"]
            hit = False
            for kk, x in others.items():
                if kk == key(s):
                    continue
                xb = x["bb"]
                if xb[0] > bx[2] + t or xb[2] < bx[0] - t or xb[1] > bx[3] + t or xb[3] < bx[1] - t:
                    continue
                if touches(o, outline(x), t):
                    hit = True
                    break
            if hit:
                touching += 1
                continue
        keep_c.append((s, cs))
    col_ids, sizes, centres_, shapes_ = set(), [], [], set()
    for s, cs in keep_c:
        if cs:
            col_ids.add(key(s))
            sizes.append(cs[1])
            shapes_.add(cs[0])
            centres_.append([round(v, 2) for v in centre(s)])
            ids["columns"].append(s.get("id"))
    A = L = 0.0
    n_w = 0
    for s in walls:
        if key(s) in col_ids or key(s) in tread_ids:     # a column or a tread is never also a wall
            continue
        t = wall_piece(s, C)
        if t:
            A += s["area"]
            L += s["area"] / t
            n_w += 1
            ids["walls"].append(s.get("id"))
    plan = {
        "source": source, "route": "rhino", "units_factor": k,
        "applies_to_levels": "all (typical floor)",
        "core": {"wall_length_m_per_floor": round(L, 1), "wall_plan_area_m2_per_floor": round(A, 1),
                 "mean_thickness_m": round(A / L, 3) if L else None, "pieces": n_w},
        "columns": {"count_per_floor": len(sizes), "size_m": round(sum(sizes) / len(sizes), 3) if sizes else None,
                    "shapes": sorted(shapes_), "centres_m": centres_},
        "stairs": {"count": len(st), "flights_per_stair": [len(s["flights"]) for s in st],
                   "treads_per_flight": [f["treads"] for f in treads],
                   "flight_width_m": round(sum(f["width"] for f in treads) / len(treads), 3) if treads else None,
                   "going_m": round(sum(f["going"] for f in treads) / len(treads), 3) if treads else None,
                   "plan_angle_deg": round(math.degrees(ang), 1)},
    }
    if not n_w:
        notes.append("No core walls found (closed outlines or hatches 100-500 mm thick).")
    if touching:
        notes.append("%d square / rectangular shapes of column size were left out because they touch other shapes "
                     "(wall nibs, shafts, tiles) - only free-standing ones count as columns." % touching)
    if not sizes:
        notes.append("No columns found (circles, squares or rectangles 0.2-1.5 m across as closed polylines or blocks; "
                     "rectangles up to %g x as long as wide)." % C.get("column_max_aspect", 3.0))
    if not st:
        notes.append("No stairs found (tread rectangles 0.18-0.40 x 0.80-2.20 m, 4+ per flight) - stairs use office defaults.")
    plan["note"] = " ".join(notes) + " Check the highlighted objects in Rhino."
    return plan, ids, notes


def layer_scores(shapes_by_layer, cfg=None):
    """Per layer: (walls, columns, treads-in-flights) counts, used to pre-fill the pickers."""
    C = dict(DEFAULTS)
    C.update(cfg or {})
    out = {}
    for lay, xs in shapes_by_layer.items():
        k, _ = check_scale(xs, xs, C)
        xs = [scaled(s, k) for s in xs]
        nc = sum(1 for s in xs if column_size(s, C))
        st = group_stairs(tread_boxes(xs, dominant_angle(xs), C), tuple(C["tread_going_range_m"]),
                          tuple(C["tread_width_range_m"]), C["min_treads_per_flight"], C["stair_cluster_gap_m"])
        nw = sum(1 for s in xs if wall_piece(s, C) and not column_size(s, C) and not (st and is_tread(s, C)))
        out[lay] = (nw, nc, sum(f["treads"] for s in st for f in s["flights"]))
    return out


def suggest_layers(shapes_by_layer, patterns=None, cfg=None):
    """{'walls': layer, 'columns': layer, 'stairs': layer} - name patterns first (office settings), then shape counts."""
    P = dict(LAYER_PATTERNS)
    P.update(patterns or {})
    sc = layer_scores(shapes_by_layer, cfg)
    pick = {}
    for role, i in (("walls", 0), ("columns", 1), ("stairs", 2)):
        named = [l for l in sc if any(fnmatch.fnmatch(l.lower(), p.lower()) for p in P.get(role, []))]
        pool = [l for l in named if sc[l][i] > 0] or [l for l in sc if sc[l][i] > 0]
        pick[role] = max(pool, key=lambda l: sc[l][i]) if pool else ""
    return pick, sc


# ----------------------------------------------------------------------------- Rhino adapter
def _shapes_from_geometry(g, xf, oid, layer, k, out):
    import Rhino.Geometry as rg
    g = g.Duplicate()
    if xf is not None:
        g.Transform(xf)
    curves = []
    if isinstance(g, rg.Hatch):
        curves = [c for c in g.Get3dCurves(True)]
    elif isinstance(g, rg.Curve):
        curves = [g]
    for c in curves:
        s = {"id": oid, "layer": layer, "closed": c.IsClosed, "perim": c.GetLength() * k}
        b = c.GetBoundingBox(True)
        s["bb"] = (b.Min.X * k, b.Min.Y * k, b.Max.X * k, b.Max.Y * k)
        if c.IsClosed:
            ok, ci = c.TryGetCircle()
            if ok:
                s["circle"] = (ci.Center.X * k, ci.Center.Y * k, 2 * ci.Radius * k)
            amp = rg.AreaMassProperties.Compute(c)
            s["area"] = (amp.Area if amp else 0.0) * k * k
        ok, pl = c.TryGetPolyline()
        if ok:
            s["pts"] = [(p.X * k, p.Y * k) for p in pl]
        elif c.IsClosed and not s.get("circle"):
            pc = c.ToPolyline(0.001 / k if k else 0.001, 0.0, 0.0, 0.0)
            if pc:
                ok2, pl2 = pc.TryGetPolyline()
                if ok2:
                    s["pts"] = [(p.X * k, p.Y * k) for p in pl2]
        out.append(s)


def collect(doc, layer_paths):
    """Shapes on the given layers (and sublayers) in metres (file units applied): {layer: [shape]}.
    Block instances are read through (nested too); a block that is one small square-ish object counts by its box."""
    import Rhino
    import Rhino.Geometry as rg
    k = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters)
    wanted = [p for p in layer_paths if p]
    out = dict((p, []) for p in wanted)

    def owner(path):
        for p in wanted:
            if path == p or path.startswith(p + "::"):
                return p
        return None

    def walk(objs, xf, top_id, depth):
        for o in objs:
            lay = doc.Layers[o.Attributes.LayerIndex].FullPath
            g = o.Geometry
            if isinstance(g, rg.InstanceReferenceGeometry) and depth < 6:
                d = doc.InstanceDefinitions.FindId(g.ParentIdefId)
                if d is not None:
                    walk(d.GetObjects(), g.Xform if xf is None else xf * g.Xform, top_id or o.Id, depth + 1)
                continue
            p = owner(lay)
            if p:
                _shapes_from_geometry(g, xf, str(top_id or o.Id), p, k, out[p])

    walk([o for o in doc.Objects if not o.IsDeleted], None, None, 0)
    return out


def read_plan(doc, walls_layer, columns_layer=None, stairs_layer=None, boundary_id=None, cfg=None):
    """Read the typical floor plan from the model. Returns (plan dict, ids by role, notes)."""
    import Rhino
    layers = [l for l in {walls_layer, columns_layer or walls_layer, stairs_layer} if l]
    shp = collect(doc, layers)
    bnd = None
    if boundary_id:
        import System
        o = doc.Objects.FindId(System.Guid(boundary_id))
        if o is not None:
            tmp = []
            _shapes_from_geometry(o.Geometry, None, boundary_id, "boundary",
                                  Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters), tmp)
            bnd = tmp[0] if tmp else None
    src = "Rhino layers: walls '%s', columns '%s', stairs '%s'" % (walls_layer, columns_layer or walls_layer, stairs_layer or "-")
    return measure(shp.get(walls_layer, []), shp.get(columns_layer or walls_layer, []), shp.get(stairs_layer, []) if stairs_layer else [],
                   cfg, boundary=bnd, source=src)


def all_layer_shapes(doc, max_layers=200):
    """Shapes on every layer that holds curves or hatches (for suggest_layers)."""
    import Rhino.Geometry as rg
    paths = sorted(set(doc.Layers[o.Attributes.LayerIndex].FullPath for o in doc.Objects
                       if not o.IsDeleted and isinstance(o.Geometry, (rg.Curve, rg.Hatch, rg.InstanceReferenceGeometry))))
    return collect(doc, [p for p in paths if not p.startswith("WLCA")][:max_layers])


def highlight(doc, ids):
    """Select the counted objects so the designer can check them."""
    import System
    doc.Objects.UnselectAll()
    n = 0
    for role in ("walls", "columns", "stairs"):
        for i in set(x for x in ids.get(role, []) if x):
            if doc.Objects.Select(System.Guid(i), True):
                n += 1
    doc.Views.Redraw()
    return n
