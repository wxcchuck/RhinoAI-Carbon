#! python3
# r: pymupdf, shapely, matplotlib
"""
WLCA plan extractor  v0.2  (draft for review)
Office WLCA template - drawing route for cores and columns

Drafted by an AI agent (Claude) - review before trusting.

Reads a VECTOR floor-plan PDF and measures, per floor:
  - core walls: cut walls inside a core window -> total wall length (m), mean thickness (m),
    wall area in plan (m2). Walls are the thin faces formed by the heaviest black pen.
  - columns: circles (or squares) inside a floor-plate window -> count and size (m).
  - stairs (v0.2): treads are thin closed rectangles in the cut-line pen; runs of equal treads make a
    flight, flights close together make a stair -> stair count, flights per stair, treads per flight,
    flight width and going.
Writes <stem>.json for the take-off (CONFIG["structure"]["plan_json"]) and <stem>_overlay.png
for review - always check the overlay before using the numbers.

Windows are given in SHEET millimetres from the top-left corner (read them off any PDF viewer
with a measure tool, or from the sheet grid). Scale is the drawing scale, e.g. 200 for 1:200.

Will not work on scanned/raster PDFs, or where cut walls share a pen with other linework - use the
numeric route in the take-off instead.

Run: Rhino 8 ScriptEditor (Python 3 installs the packages above), or any Python 3:
    python wlca_plan_extract.py [config.json]   (or edit CONFIG)
"""
import json, os, sys

CONFIG = {
    "pdf": r"C:\path\to\plan.pdf",
    "page": 0,
    "scale": 200,                                   # 1:200
    "core_windows_mm": [[469, 310, 600, 410]],      # [x0, y0, x1, y1] sheet mm, one per core zone
    "plate_window_mm": [339, 198, 600, 410],        # window for columns (whole floor plate)
    "wall_pen_width_pt": None,                      # None = heaviest black pen in the core windows
    "wall_thickness_range_m": [0.10, 0.50],         # faces thinner/thicker than this are not walls
    "column_size_range_m": [0.25, 1.50],
    "column_shapes": ["circle"],                    # add "square" for rectangular columns
    "column_pen_width_pt": None,                    # None = same pen as the cut walls
    "stairs": True,                                 # detect stairs (treads) in the plate window
    "tread_going_range_m": [0.18, 0.40],            # short side of a tread rectangle
    "tread_width_range_m": [0.80, 2.20],            # long side = flight width
    "min_treads_per_flight": 4,
    "stair_cluster_gap_m": 1.0,                     # flights closer than this belong to one stair
    "applies_to_levels": "typical",                 # label only; the take-off decides where it applies
    "out_dir": None,                                # None = next to the PDF
    "stem": None,
}


def group_stairs(rects, going_rng=(0.18, 0.40), width_rng=(0.80, 2.20), min_treads=4, gap=1.0):
    """Treads -> flights -> stairs. rects: [(x0, y0, x1, y1)] in metres (any consistent origin).

    A flight is a run of >= min_treads tread rectangles of the same size and alignment whose centres
    step by about one going. Flights whose boxes come within `gap` of each other form one stair.
    Returns a list of stairs: dict(flights=[dict(treads, width, going, box)], box).
    """
    tr = []
    for x0, y0, x1, y1 in set((round(a, 3), round(b, 3), round(c, 3), round(d, 3)) for a, b, c, d in rects):
        w, h = x1 - x0, y1 - y0
        short, long_ = min(w, h), max(w, h)
        if going_rng[0] <= short <= going_rng[1] and width_rng[0] <= long_ <= width_rng[1] and long_ / short >= 3:
            vertical = h > w                       # long side vertical -> flight runs along x
            tr.append(dict(box=(x0, y0, x1, y1), v=vertical, short=short, long=long_,
                           s=(x0 + x1) / 2 if vertical else (y0 + y1) / 2,      # position along the flight
                           a=y0 if vertical else x0))                          # alignment of the tread ends
    tr.sort(key=lambda t: (t["v"], round(t["a"], 1), round(t["long"], 1), t["s"]))
    flights, cur = [], []
    for t in tr:
        if cur:
            p = cur[-1]
            same = (t["v"] == p["v"] and abs(t["a"] - p["a"]) < 0.10 and abs(t["long"] - p["long"]) < 0.05 * p["long"]
                    and 0.6 * p["short"] <= t["s"] - p["s"] <= 1.4 * p["short"])
            if not same:
                flights.append(cur)
                cur = []
        cur.append(t)
    if cur:
        flights.append(cur)
    fl = []
    for f in flights:
        if len(f) < min_treads:
            continue
        xs = [c for t in f for c in (t["box"][0], t["box"][2])]
        ys = [c for t in f for c in (t["box"][1], t["box"][3])]
        steps = [b["s"] - a["s"] for a, b in zip(f[:-1], f[1:])]
        fl.append(dict(treads=len(f), width=round(sum(t["long"] for t in f) / len(f), 3),
                       going=round(sum(steps) / len(steps), 3), box=(min(xs), min(ys), max(xs), max(ys))))

    def near(a, b):
        dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
        dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
        return (dx * dx + dy * dy) ** 0.5 <= gap

    stairs = []
    for f in fl:
        hit = [st for st in stairs if any(near(f["box"], g["box"]) for g in st["flights"])]
        if hit:
            base = hit[0]
            for other in hit[1:]:
                base["flights"] += other["flights"]
                stairs.remove(other)
            base["flights"].append(f)
        else:
            stairs.append(dict(flights=[f]))
    for st in stairs:
        bx = [g["box"] for g in st["flights"]]
        st["box"] = (min(b[0] for b in bx), min(b[1] for b in bx), max(b[2] for b in bx), max(b[3] for b in bx))
    return stairs


def extract(cfg):
    import pymupdf
    from shapely.geometry import LineString, box
    from shapely.ops import unary_union, polygonize

    MM = 72.0 / 25.4                                  # pt per sheet mm
    M_PER_PT = 25.4 / 72.0 * cfg["scale"] / 1000.0    # model metres per pt
    doc = pymupdf.open(cfg["pdf"])
    page = doc[cfg["page"]]
    drawings = page.get_drawings()

    def win(w):
        return [w[0] * MM, w[1] * MM, w[2] * MM, w[3] * MM]

    def inside(r, w):
        return r.x0 >= w[0] and r.y0 >= w[1] and r.x1 <= w[2] and r.y1 <= w[3]

    def is_black(g):
        c = g.get("color")
        return c is not None and max(c) < 0.05

    core_ws = [win(w) for w in cfg["core_windows_mm"]]
    pen = cfg["wall_pen_width_pt"]
    if pen is None:
        def stroke_len(g):                            # drawn length in pt, by item type
            n = 0.0
            for it in g["items"]:
                if it[0] == "l":
                    n += abs(it[2] - it[1])
                elif it[0] == "re":
                    n += 2 * (it[1].width + it[1].height)
                elif it[0] == "qu":
                    q = it[1]; n += abs(q.ur - q.ul) + abs(q.lr - q.ur) + abs(q.ll - q.lr) + abs(q.ul - q.ll)
                elif it[0] == "c":
                    n += abs(it[4] - it[1])
            return n
        widths = {}
        for g in drawings:
            if is_black(g) and any(inside(g["rect"], w) for w in core_ws):
                wd = round(g.get("width") or 0, 2)
                widths[wd] = widths.get(wd, 0) + stroke_len(g)
        cand = [w for w, n in widths.items() if n * M_PER_PT >= 5.0]   # >= 5 m of linework at drawing scale
        if not cand:
            raise RuntimeError("No black linework in the core window(s) - check windows / vector PDF")
        pen = max(cand)

    lo, hi = cfg["wall_thickness_range_m"]
    cores = []
    all_walls = []
    for w in core_ws:
        segs = []
        for g in drawings:
            if not (is_black(g) and round(g.get("width") or 0, 2) == pen and inside(g["rect"], w)):
                continue
            for it in g["items"]:
                if it[0] == "l":
                    segs.append(LineString([(it[1].x, it[1].y), (it[2].x, it[2].y)]))
                elif it[0] == "re":
                    R = it[1]; segs.append(box(R.x0, R.y0, R.x1, R.y1).exterior)
                elif it[0] == "qu":
                    q = it[1]
                    segs.append(LineString([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)]))
        faces = list(polygonize(unary_union(segs))) if segs else []
        walls = []
        for f in faces:
            t = 2 * f.area / f.length * M_PER_PT          # strip thickness
            if lo <= t <= hi:
                walls.append(f)
        area = sum(f.area for f in walls) * M_PER_PT ** 2
        length = sum(f.length / 2 for f in walls) * M_PER_PT
        outline = unary_union([f.buffer(0.5 / M_PER_PT) for f in faces]).buffer(-0.5 / M_PER_PT) if faces else None
        cores.append(dict(window_mm=[round(v / MM, 1) for v in w], wall_faces=len(walls),
                          wall_length_m=round(length, 1), wall_plan_area_m2=round(area, 1),
                          mean_thickness_m=round(area / length, 3) if length else None,
                          outline_area_m2=round(outline.area * M_PER_PT ** 2, 1) if outline else None))
        all_walls += walls

    # columns: closed circular paths (or small squares) of the column size range inside the plate window
    pw = win(cfg["plate_window_mm"])
    smin, smax = cfg["column_size_range_m"]
    cpen = cfg["column_pen_width_pt"] or pen
    cols = []
    for g in drawings:
        r = g["rect"]
        if not inside(r, pw) or any(inside(r, w) for w in core_ws):
            continue
        if not (is_black(g) and round(g.get("width") or 0, 2) == cpen):
            continue
        dx, dy = r.width * M_PER_PT, r.height * M_PER_PT
        if not (smin <= dx <= smax and abs(dx - dy) < 0.05):
            continue
        kinds = set(it[0] for it in g["items"])
        if kinds <= {"c"} and len(g["items"]) >= 4:
            shape = "circle"
        elif kinds <= {"re", "qu"} or (kinds <= {"l"} and len(g["items"]) == 4):
            shape = "square"
        else:
            continue
        if shape not in cfg["column_shapes"]:
            continue
        c = (r.x0 + r.width / 2, r.y0 + r.height / 2)
        if all(abs(c[0] - k["c"][0]) + abs(c[1] - k["c"][1]) > 2 for k in cols):
            cols.append(dict(c=c, size=round(dx, 3), shape=shape))
    if cols:                                      # keep the dominant size (+/-15%): drops symbols and fittings
        ss = sorted(k["size"] for k in cols); mode = ss[len(ss) // 2]
        cols = [k for k in cols if abs(k["size"] - mode) <= 0.15 * mode]
    sizes = sorted(k["size"] for k in cols)

    # stairs: closed thin rectangles (quads or rects) in black, any pen, inside the plate window
    stairs = []
    if cfg.get("stairs", True):
        rects = []
        for g in drawings:
            if not (is_black(g) and inside(g["rect"], pw)):
                continue
            for it in g["items"]:
                if it[0] in ("re", "qu"):
                    R = it[1] if it[0] == "re" else it[1].rect
                    rects.append(((R.x0 - pw[0]) * M_PER_PT, (R.y0 - pw[1]) * M_PER_PT,
                                  (R.x1 - pw[0]) * M_PER_PT, (R.y1 - pw[1]) * M_PER_PT))
        stairs = group_stairs(rects, cfg["tread_going_range_m"], cfg["tread_width_range_m"],
                              cfg["min_treads_per_flight"], cfg["stair_cluster_gap_m"])
    tot_len = sum(c["wall_length_m"] for c in cores)
    tot_area = sum(c["wall_plan_area_m2"] for c in cores)
    result = dict(
        source=os.path.basename(cfg["pdf"]), page=cfg["page"], scale="1:%d" % cfg["scale"],
        applies_to_levels=cfg["applies_to_levels"], wall_pen_width_pt=pen,
        core=dict(wall_length_m_per_floor=round(tot_len, 1), wall_plan_area_m2_per_floor=round(tot_area, 1),
                  mean_thickness_m=round(tot_area / tot_len, 3) if tot_len else None, zones=cores),
        columns=dict(count_per_floor=len(cols), size_m=sizes[len(sizes) // 2] if sizes else None,
                     shapes=sorted(set(k["shape"] for k in cols)),
                     centres_m=[(round((k["c"][0] - pw[0]) * M_PER_PT, 2), round((k["c"][1] - pw[1]) * M_PER_PT, 2)) for k in cols]),
        stairs=dict(count=len(stairs),
                    flights_per_stair=[len(st["flights"]) for st in stairs],
                    treads_per_flight=[f["treads"] for st in stairs for f in st["flights"]],
                    flight_width_m=round(sum(f["width"] for st in stairs for f in st["flights"]) /
                                         max(1, sum(len(st["flights"]) for st in stairs)), 3) if stairs else None,
                    going_m=round(sum(f["going"] for st in stairs for f in st["flights"]) /
                                  max(1, sum(len(st["flights"]) for st in stairs)), 3) if stairs else None,
                    boxes_m=[[round(v, 2) for v in st["box"]] for st in stairs]),
        note="Check the overlay. All cut walls in the core windows are counted (incl. WC/riser walls). Stairs: green boxes.")

    # overlay for review
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out_dir = cfg["out_dir"] or os.path.dirname(os.path.abspath(cfg["pdf"]))
    stem = cfg["stem"] or os.path.splitext(os.path.basename(cfg["pdf"]))[0] + "_plan_extract"
    pix = page.get_pixmap(dpi=100, clip=pymupdf.Rect(*pw))
    png_bg = os.path.join(out_dir, stem + "_bg.png"); pix.save(png_bg)
    img = plt.imread(png_bg)
    fig, ax = plt.subplots(figsize=(12, 12 * (pw[3] - pw[1]) / (pw[2] - pw[0])))
    ax.imshow(img, extent=[pw[0], pw[2], pw[3], pw[1]], alpha=0.45)
    for f in all_walls:
        xs, ys = f.exterior.xy; ax.fill(xs, ys, color="crimson", alpha=0.85, lw=0)
    for w in core_ws:
        ax.plot([w[0], w[2], w[2], w[0], w[0]], [w[1], w[1], w[3], w[3], w[1]], "b--", lw=1)
    for k in cols:
        ax.add_patch(plt.Circle(k["c"], k["size"] / M_PER_PT / 2 * 1.6, fill=False, ec="dodgerblue", lw=2))
    for st in stairs:
        b = [v / M_PER_PT for v in st["box"]]
        ax.add_patch(plt.Rectangle((pw[0] + b[0], pw[1] + b[1]), b[2] - b[0], b[3] - b[1], fill=False, ec="green", lw=2))
    ax.set_xlim(pw[0], pw[2]); ax.set_ylim(pw[3], pw[1]); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("Core walls %.0f m/floor (mean %.2f m thick) · %d columns ~%.2f m · %d stairs - red = walls, blue = columns, green = stairs"
                 % (tot_len, result["core"]["mean_thickness_m"] or 0, len(cols), result["columns"]["size_m"] or 0, len(stairs)), fontsize=10)
    png = os.path.join(out_dir, stem + "_overlay.png")
    fig.savefig(png, dpi=110, bbox_inches="tight"); plt.close(fig)
    os.remove(png_bg)
    jp = os.path.join(out_dir, stem + ".json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result, [jp, png]


if __name__ == "__main__":
    if len(sys.argv) > 1:                      # optional: python script.py config.json
        CONFIG.update(json.load(open(sys.argv[1])))
    res, paths = extract(CONFIG)
    print(json.dumps(dict(core=dict((k, v) for k, v in res["core"].items() if k != "zones"),
                          columns=dict((k, v) for k, v in res["columns"].items() if k != "centres_m"),
                          stairs=dict((k, v) for k, v in res["stairs"].items() if k != "boxes_m")), indent=1))
    for p in paths:
        print("Wrote", p)
