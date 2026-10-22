"""Rhino plan reader (geometry core, no Rhino). Drafted by an AI agent (Claude) - review before trusting.

An INVENTED typical floor: 40 x 30 m plate (outer + inner facade line), a core of 0.30 m walls, 6 round columns,
two stairs of 2 flights x 10 treads (1.20 m wide, 0.25 m going), and a wall drawn outside the plate.
"""
import math

import pytest

import wlca_plan_rhino as pr

N = [0]


def _rect(x0, y0, x1, y1, layer="W", rot=0.0, k=1.0):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    return _poly(pts, layer, rot, k)


def _poly(pts, layer="W", rot=0.0, k=1.0):
    c, s = math.cos(rot), math.sin(rot)
    p = [((x * c - y * s) * k, (x * s + y * c) * k) for x, y in pts]
    area = abs(sum(p[i][0] * p[i + 1][1] - p[i + 1][0] * p[i][1] for i in range(len(p) - 1))) / 2
    per = sum(math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) for i in range(len(p) - 1))
    xs, ys = zip(*p)
    N[0] += 1
    return dict(id="o%d" % N[0], layer=layer, closed=True, area=area, perim=per, pts=p, bb=(min(xs), min(ys), max(xs), max(ys)))


def _circle(x, y, d, layer="W", rot=0.0, k=1.0):
    c, s = math.cos(rot), math.sin(rot)
    X, Y = (x * c - y * s) * k, (x * s + y * c) * k
    N[0] += 1
    return dict(id="o%d" % N[0], layer=layer, closed=True, area=math.pi * (d * k / 2) ** 2, perim=math.pi * d * k,
                circle=(X, Y, d * k), bb=(X - d * k / 2, Y - d * k / 2, X + d * k / 2, Y + d * k / 2))


def plan(rot=0.0, k=1.0, stairs_layer="S"):
    W = [_rect(0, 0, 40, 30, rot=rot, k=k), _rect(0.3, 0.3, 39.7, 29.7, rot=rot, k=k)]           # facade lines
    # core: four straight walls 0.30 thick (8 + 8 + 6 + 6 m) and one L (4 + 3 m centreline)
    W += [_rect(15, 10, 23, 10.3, rot=rot, k=k), _rect(15, 16, 23, 16.3, rot=rot, k=k),
          _rect(15, 10.3, 15.3, 16.3, rot=rot, k=k), _rect(22.7, 10.3, 23, 16.3, rot=rot, k=k),
          _poly([(17, 12), (21, 12), (21, 12.3), (17.3, 12.3), (17.3, 15), (17, 15), (17, 12)], rot=rot, k=k)]
    W += [_circle(x, y, 0.75, rot=rot, k=k) for x in (5, 12, 30) for y in (6, 24)]
    W += [_rect(60, 10, 70, 10.3, rot=rot, k=k)]                                                   # another drawing
    S = []
    for sx in (3.0, 33.0):                                    # two stairs, two flights each, 10 treads 1.2 x 0.25
        for fx in (sx, sx + 1.3):
            S += [_rect(fx, 10 + i * 0.25, fx + 1.2, 10.25 + i * 0.25, layer=stairs_layer, rot=rot, k=k) for i in range(10)]
    return W, S


def _check(p):
    c = p["core"]
    # straight walls 8 + 8 + 6 + 6 = 28 m; L outline P = 14, A = 2.01 -> t = 0.3 (rect formula) and L = 6.7
    assert c["pieces"] == 5
    assert c["mean_thickness_m"] == pytest.approx(0.30, abs=0.005)
    assert c["wall_length_m_per_floor"] == pytest.approx(28.0 + 6.7, abs=0.2)
    assert p["columns"]["count_per_floor"] == 6 and p["columns"]["size_m"] == pytest.approx(0.75)
    st = p["stairs"]
    assert st["count"] == 2 and st["flights_per_stair"] == [2, 2] and st["treads_per_flight"] == [10] * 4
    assert st["flight_width_m"] == pytest.approx(1.2, abs=0.01) and st["going_m"] == pytest.approx(0.25, abs=0.01)


def test_reads_core_columns_stairs_and_ignores_outside_plate():
    W, S = plan()
    p, ids, notes = pr.measure(W, W, S)
    _check(p)
    assert p["units_factor"] == 1.0 and any("1 objects outside" in n for n in notes)
    assert len(ids["walls"]) == 5 and len(ids["columns"]) == 6 and len(ids["stairs"]) == 40


def test_rotated_plan():
    W, S = plan(rot=math.radians(27))
    p, _, _ = pr.measure(W, W, S)
    _check(p)
    assert p["stairs"]["plan_angle_deg"] == pytest.approx(27, abs=0.6)


def test_wrong_units_are_detected():
    W, S = plan(k=0.001)                       # a DWG saying millimetres for metre coordinates
    p, _, notes = pr.measure(W, W, S)
    assert p["units_factor"] == 1000.0 and notes[0].startswith("Units")
    _check(p)


def test_treads_on_the_wall_layer_are_not_walls():
    W, S = plan(stairs_layer="W")
    p, _, _ = pr.measure(W + S, W + S, W + S)
    _check(p)


def test_layer_suggestions_by_name_then_shape():
    W, S = plan()
    shapes = {"EF_25 - Wall and Barrier elements - External": W, "1140_Stair- General": S,
              "Internal Wall": [_rect(5, 5, 9, 5.1, layer="I")], "Gridlines": []}
    pick, sc = pr.suggest_layers(shapes)
    assert pick == {"walls": "EF_25 - Wall and Barrier elements - External", "columns": "EF_25 - Wall and Barrier elements - External",
                    "stairs": "1140_Stair- General"}
    pick, _ = pr.suggest_layers({"L1": W, "L2": S})            # no name matches: the shapes decide
    assert pick["walls"] == "L1" and pick["columns"] == "L1" and pick["stairs"] == "L2"


def test_square_and_rectangular_columns_by_default():
    W, S = plan()
    sq = _rect(25, 20, 25.6, 20.6)                                   # 600 square
    rc = _rect(8, 14, 8.4, 15.0)                                     # 400 x 1000 rectangle -> square of the same area
    messy = _poly([(30, 14), (30.3, 14), (30.6, 14), (30.6, 14.6), (30, 14.6), (30, 14.6), (30, 14)])  # extra + repeated points
    stub = _rect(10, 4, 10.3, 5.5)                                   # 300 x 1500 = 5 x as long: a wall stub, not a column
    p, ids, _ = pr.measure(W + [sq, rc, messy, stub], W + [sq, rc, messy, stub], S)
    c = p["columns"]
    assert c["count_per_floor"] == 6 + 3 and set(c["shapes"]) == {"circle", "square", "rectangle"}
    assert sq["id"] in ids["columns"] and rc["id"] in ids["columns"] and messy["id"] in ids["columns"]
    assert stub["id"] not in ids["columns"] and stub["id"] in ids["walls"]
    assert rc["id"] not in ids["walls"]                              # 400 thick would also pass as a wall - columns win
    sizes = sorted([0.75] * 6 + [0.6, math.sqrt(0.4 * 1.0), 0.6])
    assert c["size_m"] == pytest.approx(sum(sizes) / len(sizes), abs=0.001)


def test_circles_only_when_the_office_says_so():
    W, S = plan()
    W.append(_rect(25, 20, 25.6, 20.6))
    assert pr.measure(W, W, S, {"column_shapes": ["circle"]})[0]["columns"]["count_per_floor"] == 6


def test_rect_columns_survive_a_units_fix_without_becoming_walls():
    W, S = plan(k=0.001)
    rc = _rect(8, 14, 8.4, 15.0, k=0.001)
    p, ids, _ = pr.measure(W + [rc], W + [rc], S)
    assert p["units_factor"] == 1000.0 and rc["id"] in ids["columns"] and rc["id"] not in ids["walls"]


def test_treads_on_the_column_layer_are_not_columns():
    W, S = plan()
    p, ids, _ = pr.measure(W + S, W + S, W + S)
    assert p["columns"]["count_per_floor"] == 6 and p["stairs"]["count"] == 2


def test_boxes_that_touch_other_shapes_are_not_columns():
    """From the sample plan: a row of 1.5 m squares (shafts / tiles) and 300 mm nibs on a core wall are not columns."""
    W, S = plan()
    row = [_rect(5 + 1.5 * i, 14, 6.5 + 1.5 * i, 15.5) for i in range(4)]      # side by side, sharing edges
    nib = _rect(15.3, 13, 15.8, 13.3)                                          # 500 x 300 nib on the core wall at x = 15.3
    free = _rect(25, 20, 25.6, 20.6)
    on_facade = _rect(0.3, 12, 0.9, 12.6)                                      # perimeter column on the inner facade line
    extra = row + [nib, free, on_facade]
    p, ids, notes = pr.measure(W + extra, W + extra, S)
    assert p["columns"]["count_per_floor"] == 6 + 2
    assert free["id"] in ids["columns"] and on_facade["id"] in ids["columns"]
    assert not any(r["id"] in ids["columns"] for r in row) and nib["id"] not in ids["columns"]
    assert nib["id"] in ids["walls"]                                           # a nib stays part of the core walls
    assert any("touch other shapes" in n for n in notes)
