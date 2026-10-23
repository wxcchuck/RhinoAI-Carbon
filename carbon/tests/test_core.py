"""Unit tests for wlca_core. Drafted by an AI agent (Claude) - review before trusting.

Expected values are worked out by hand in the comments, from the invented test building in conftest.py,
so a failing test points at a rule change rather than a moved number.
"""
import math

import pytest

import wlca_core as core
from conftest import write_schedule

PI4 = math.pi / 4


# ----------------------------------------------------------------------------- schedule parsing
def test_parse_schedule_orders_levels_bottom_up_and_reads_all_columns(schedule):
    names = [lv["name"] for lv in schedule]
    assert names == ["B2", "B1", "0"] + [str(i) for i in range(1, 13)]
    assert schedule[0] == dict(name="B2", use="Plant", gea=1200.0, gia=1100.0, aod=-9.0, ftf=4.5, nia=None)
    l5 = schedule[7]
    assert (l5["name"], l5["nia"], l5["ftf"]) == ("5", 800.0, 3.75)
    assert sum(lv["gea"] for lv in schedule) == 1200 * 2 + 1000 + 1100 * 10 + 800 + 300
    assert sum(lv["gia"] for lv in schedule) == 1100 * 2 + 960 + 1060 * 10 + 770 + 280


def test_parse_schedule_without_aod_orders_by_level_name(tmp_path):
    path = write_schedule(str(tmp_path / "noaod.xlsx"), with_aod=False)
    w = []
    lv = core.parse_area_schedule({"path": path, "sheet": "Office"}, w)
    assert [x["name"] for x in lv][:4] == ["B2", "B1", "0", "1"]
    assert any("no AOD" in m for m in w)
    gi = core.ground_index(lv)
    core.stack_aod(lv, gi, 0.0)
    assert [x["aod"] for x in lv[:4]] == [-9.0, -4.5, 0.0, 4.5]


def test_parse_schedule_flags_broken_aod_chain(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = write_schedule(str(tmp_path / "s.xlsx"))
    wb = openpyxl.load_workbook(path)
    ws = wb["Office"]
    for row in ws.iter_rows():
        if row[1].value == "5":
            row[3].value = row[3].value + 0.5          # AOD of level 5 off by 0.5 m
    wb.save(path)
    w = []
    core.parse_area_schedule({"path": path, "sheet": "Office"}, w)
    assert sum("AOD" in m for m in w) == 2           # 4->5 and 5->6 both break


def test_parse_schedule_errors_are_loud(tmp_path):
    path = write_schedule(str(tmp_path / "s.xlsx"))
    with pytest.raises(core.TakeoffError, match="not in"):
        core.parse_area_schedule({"path": path, "sheet": "Resi"}, [])


# ----------------------------------------------------------------------------- horizontals (BR-01..03)
def test_schedule_horizontals_allocates_slabs_roofs_soffits(schedule):
    hz, roofs = core.schedule_horizontals(schedule)
    assert hz["lowest"] == 1200                      # B2 -> 1.2.1
    assert hz["basement"] == 1200                    # B1 suspended below ground -> 1.2.2
    assert hz["upper"] == 1000 + 1100 * 10 + 800 + 300   # L0 and above -> 2.2.1
    assert hz["podium"] == 200                       # B1 1200 - L0 1000, at ground
    assert hz["roof"] == 300 + 500 + 300             # L10->L11 setback, L11->L12, top of L12
    assert hz["soffit"] == 100                       # L1 1100 over L0 1000
    assert [r["level"] for r in roofs] == ["11", "12", "roof"]
    assert roofs[-1]["z"] == 50.75                   # L12 AOD 45.75 + 5.0


def test_reconcile_schedule_flags_levels_beyond_tolerance(schedule):
    massing = dict((lv["name"], lv["gea"]) for lv in schedule if not lv["name"].startswith("B"))
    massing["11"] = 800 * 1.05                       # +5% > 3%
    w = []
    rows = core.reconcile_schedule(schedule, massing, 0.03, w)
    status = dict((r["level"], r["status"]) for r in rows)
    assert status["B1"].startswith("below ground")
    assert status["11"] == "CHECK" and status["5"] == "OK"
    assert len(w) == 1 and "1 level(s)" in w[0]


# ----------------------------------------------------------------------------- structure
def _lv_all(schedule):
    return [(lv["name"], lv["ftf"], lv["gea"], lv["gia"], lv["nia"]) for lv in schedule]


def test_structure_numeric_route(schedule, defaults):
    S = dict(defaults["structure"])
    w = []
    rows, info = core.structure_rows(_lv_all(schedule), None, S, "Derived", w)
    # typical = the most common GEA (1100, level 1): core = GIA 1060 - NIA 800 = 260 m2
    assert info["typical_level"] == "1" and info["core_area_m2"] == 260
    wall = 260 * S["core_wall_density_m_per_m2"]
    total_ftf = 4.5 * 3 + 3.75 * 11 + 5.0
    walls = [r for r in rows if r[1] == "core_wall"][0]
    assert walls[2] == pytest.approx(wall * total_ftf)
    # columns: rho = edge factor / (grid x * grid y); n per level = round(rho * (GEA - core))
    rho = S["column_edge_factor"] / (S["grid_x_m"] * S["grid_y_m"])
    by_level = dict(info["columns_by_level"])
    assert by_level["5"] == round(rho * (1100 - 260))
    assert by_level["12"] == round(rho * (300 - 260))
    expect_m = sum(round(rho * max(0, lv["gea"] - 260)) * lv["ftf"] for lv in schedule)
    assert [r for r in rows if r[1] == "column"][0][2] == pytest.approx(expect_m)


def test_structure_plan_route_and_overrides(schedule, defaults):
    plan = dict(source="plan.pdf", core=dict(wall_length_m_per_floor=150.0, mean_thickness_m=0.35),
                columns=dict(count_per_floor=12, size_m=0.6, shapes=["circle"]))
    S = dict(defaults["structure"])
    w = []
    rows, info = core.structure_rows(_lv_all(schedule), plan, S, "Derived", w)
    assert info["core_wall_m_per_floor"] == 150.0
    assert info["columns_per_m2"] == round(12 / (1100 - 260), 5)
    assert any("350 mm thick vs 250 mm" in m for m in w)   # thicker than the 250 mm build-up: warned and scaled
    q = [r for r in rows if r[1] == "core_wall"][0][2]
    assert q == pytest.approx(150.0 * sum(x[1] for x in _lv_all(schedule)) * 0.35 / 0.25)
    assert any("Plan columns 0.60" in m for m in w)  # smaller than column_size_m 0.75
    S.update(core_wall_length_m_per_floor=99.0, column_count_per_floor=10)
    rows, info = core.structure_rows(_lv_all(schedule), plan, S, "Derived", [])
    assert info["core_wall_m_per_floor"] == 99.0 and info["columns_per_m2"] == round(10 / 840, 5)


# ----------------------------------------------------------------------------- secant wall geometry
def test_secant_section_matches_hand_calc():
    g = core.secant_section(1.0, 1.2)
    # lens of two r=0.5 circles 0.6 m apart: 2r^2 acos(d/2r) - (d/2) sqrt(4r^2 - d^2)
    lens = 2 * 0.25 * math.acos(0.6) - 0.3 * math.sqrt(1 - 0.36)
    assert g["lens"] == pytest.approx(lens) and g["lens"] == pytest.approx(0.2236, abs=1e-4)
    assert g["a_hard"] == pytest.approx(0.7854, abs=1e-4)
    assert g["a_firm"] == pytest.approx(0.3381, abs=1e-4)
    assert g["eq_thickness"] == pytest.approx(0.936, abs=1e-3)


def test_secant_section_against_numeric_integration():
    """Independent check: rasterise one 1.2 m bay (hard pile at x=0, firm at 0.6, hard at 1.2) and
    count cells inside any pile. Bay area must equal hard + firm net (overlaps counted once)."""
    d, sp, n = 1.0, 1.2, 1200
    r2 = (d / 2) ** 2
    step = sp / n
    inside = 0
    for i in range(n):
        x = (i + 0.5) * step                         # bay spans hard-pile centre to next hard-pile centre
        for j in range(n):
            y = -0.5 + (j + 0.5) * (1.0 / n)
            if (x * x + y * y <= r2) or ((x - 0.6) ** 2 + y * y <= r2) or ((x - 1.2) ** 2 + y * y <= r2):
                inside += 1
    area = inside * step * (1.0 / n)
    g = core.secant_section(d, sp)
    assert area == pytest.approx(g["a_hard"] + g["a_firm"], rel=2e-3)


def test_secant_section_warns_on_bad_spacing():
    w = []
    core.secant_section(1.0, 0.9, w)
    assert any("overlap each other" in m for m in w)
    w = []
    g = core.secant_section(1.0, 2.2, w)
    assert g["lens"] == 0 and any("gaps" in m for m in w)


# ----------------------------------------------------------------------------- substructure
def _sub(schedule, defaults, base_per=None, **over):
    S = dict(defaults["structure"])
    rows, info = core.structure_rows(_lv_all(schedule), None, S, "Derived", [])
    SUB = {k: (dict(v) if isinstance(v, dict) else v) for k, v in defaults["substructure"].items()}
    for k, v in over.items():
        SUB[k].update(v)
    w = []
    sub, depth = core.substructure_rows(_lv_all(schedule), core.ground_index(schedule), True, ("0", 130.0, 1000.0),
                                        schedule[0]["gea"], info["columns_by_level"], info["core_area_m2"],
                                        info["core_area_source"], SUB, "Derived", w, base_per=base_per)
    return sub, depth, w, info


def test_substructure_defaults(schedule, defaults):
    sub, depth, w, info = _sub(schedule, defaults)
    assert depth == 9.0                              # B2 + B1
    got = dict(((r[0], r[1], i), r) for i, r in enumerate(sub))
    by_key = {}
    for r in sub:
        by_key.setdefault(r[1], []).append(r)
    # secant: 130 m / 1.2 m -> 109 hard + 109 firm, L = 9.0 x 1.5 = 13.5 m
    n, L = math.ceil(130 / 1.2), 13.5
    g = core.secant_section(1.0, 1.2)
    assert by_key["secant_wall"][0][2] == pytest.approx(n * g["a_hard"] * L)
    assert by_key["secant_firm"][0][2] == pytest.approx(n * g["a_firm"] * L)
    assert by_key["liner_wall"][0][2] == pytest.approx(130 * 9.0)
    # piles: columns at B2 x 3, 0.75 m x 25 m; core group 260 / 2.25^2 -> 52 piles
    n_cols = info["columns_by_level"][0][1]
    pile = PI4 * 0.75 ** 2 * 25
    piles = by_key["pile"]
    assert piles[0][2] == pytest.approx(round(n_cols * 3) * pile)
    assert piles[1][2] == pytest.approx(math.ceil(260 / 2.25 ** 2) * pile)
    assert all(r[4] == "Derived" for r in sub)
    # caps (assumed): 3-pile triangle per column + core cap over core area + 0.5 m margin, 2.0 m thick
    caps = by_key["cap_raft"]
    side = 2.25 + math.sqrt(3) * (0.75 + 0.30)
    assert caps[0][2] == pytest.approx(n_cols * math.sqrt(3) / 4 * side ** 2 * 1.2)
    assert caps[1][2] == pytest.approx((math.sqrt(260) + 1.0) ** 2 * 2.0)
    assert all(r[5].startswith(core.ASSUMED) for r in sub)
    assert not any("caps / raft" in m for m in w)
    assert any("exceeds ground footprint" in m for m in w)   # basement 1200 > ground 1000 x 1.05
    assert got  # keeps the dict build exercised


def test_substructure_engineer_overrides(schedule, defaults):
    sub, depth, w, _ = _sub(schedule, defaults,
                            retaining_walls={"source": "engineer", "area_m2": 1500},
                            piles={"source": "engineer", "count": 40, "diameter_m": 0.9, "length_m": 30},
                            caps_raft={"source": "engineer", "volume_m3": 800})
    keys = [(r[0], r[1], r[4]) for r in sub]
    assert ("1.2.3", "retaining_wall", "Supplied") in keys
    assert ("1.1", "pile", "Supplied") in keys and ("1.1", "cap_raft", "Supplied") in keys
    pile = [r for r in sub if r[1] == "pile"][0]
    assert pile[2] == pytest.approx(40 * PI4 * 0.81 * 30)
    assert not any("caps / raft" in m for m in w)


def test_substructure_rc_wall_and_no_embedment_warning(schedule, defaults):
    sub, _, w, _ = _sub(schedule, defaults, retaining_walls={"type": "rc_wall"})
    assert [r for r in sub if r[0] == "1.2.3"][0][1:4] == ("retaining_wall", 130 * 9.0, "m2")
    sub, _, w, _ = _sub(schedule, defaults, retaining_walls={"pile_length_m": 9.0})
    assert any("no embedment" in m for m in w)


def test_basement_wall_perimeter_from_the_takeoff(schedule, defaults):
    sub, _, w, _ = _sub(schedule, defaults, base_per=(150.0, "measured on the massing below ground, level B2"),
                        retaining_walls={"type": "rc_wall"})
    wall = [r for r in sub if r[0] == "1.2.3"][0]
    assert wall[2] == pytest.approx(150.0 * 9.0) and "measured on the massing" in wall[5]
    assert not any("exceeds ground footprint" in m for m in w)          # the take-off has dealt with it
    sub, _, _, _ = _sub(schedule, defaults, base_per=(150.0, "x"), retaining_walls={"type": "rc_wall", "perimeter_m": 120.0})
    assert [r for r in sub if r[0] == "1.2.3"][0][2] == pytest.approx(120.0 * 9.0)   # an input still wins


def test_raft(schedule, defaults):
    sub, _, w, _ = _sub(schedule, defaults, piles={"source": "none"}, caps_raft={"source": "raft", "raft_thickness_m": 1.2})
    raft = [r for r in sub if r[1] == "cap_raft"]
    assert len(raft) == 1 and raft[0][2] == pytest.approx(1200 * (1.2 - 0.30))       # lowest level B2 GEA 1200
    assert not any("no piles derived" in m for m in w)
    assert core.thickness_from_code("GF-SLAB-RC-300", 0.25) == 0.30 and core.thickness_from_code("SLAB-X", 0.25) == 0.25


# ----------------------------------------------------------------------------- rows
def test_build_rows_maps_codes_and_drops_zero_rows(defaults):
    cfg = dict(defaults, project_id="T-1", model_version="m1")
    hz = dict(lowest=100.0, basement=0.0, upper=900.0, roof=100.0, podium=0.0, soffit=0.0)
    st = [("2.1.1", "column", 50.0, "m", "Derived", "c")]
    rows = core.build_rows(cfg, hz, [dict(z=30.0, area=100.0)], "schedule", 400.0, 300.0, 0.0,
                           core.expand_wwr(cfg["wwr"]), st, "layer")
    codes = [(r["nrm_code"], r["build_up_code"]) for r in rows]
    assert ("1.2.2", cfg["build_ups"]["basement_slab"]) not in codes      # zero -> dropped
    assert ("2.1.1", "COL-RC-750") in codes
    assert [r["element_id"] for r in rows] == ["MS-%04d" % i for i in range(1, len(rows) + 1)]
    assert all(r["project_id"] == "T-1" and r["include"] == "Y" for r in rows)


def test_orientation_bins_and_wwr():
    assert core.orientation(0, 1) == "N" and core.orientation(1, 0) == "E"
    assert core.orientation(-1, 1) == "NW"           # exactly 315 deg is the centre of NW, not a boundary
    assert core.orientation(0, 1, north_deg=90) == "W"
    w = core.expand_wwr({"N": 0.4, "E": 0.6, "S": 0.8, "W": 0.2})
    assert w["NE"] == pytest.approx(0.5) and w["SW"] == pytest.approx(0.5)


# ----------------------------------------------------------------------------- scope-gap allowances (v0.8)
def test_cap_plan_area_shapes():
    assert core.cap_plan_area(1, 2.25, 0.75, 0.15) == pytest.approx(1.05 ** 2)
    assert core.cap_plan_area(2, 2.25, 0.75, 0.15) == pytest.approx(3.30 * 1.05)
    assert core.cap_plan_area(4, 2.25, 0.75, 0.15) == pytest.approx(3.30 ** 2)


def test_stair_rows_from_drawing_and_defaults(schedule, defaults):
    lv = _lv_all(schedule)
    ST = dict(defaults["stairs"])
    plan = {"source": "plan.pdf", "stairs": {"count": 2, "flights_per_stair": [2, 2], "treads_per_flight": [11, 11, 11, 11],
                                             "flight_width_m": 1.25, "going_m": 0.25}}
    rows = core.stair_rows(lv, "5", plan, ST, "Derived", [])
    typ = 3.75
    r = typ / (2 * 12)
    L = math.hypot(11 * 0.25, 12 * r)
    v_typ = 2 * 1.25 * (L * 0.20 + 11 * 0.25 * r / 2) + 1 * (2 * 1.25 + 0.10) * 1.25 * 0.20
    climbed = sum(x[1] for x in lv[:-1])
    assert rows[0][:4] == ("2.4", "stair", pytest.approx(2 * v_typ * climbed / typ), "m3")
    assert rows[0][5].startswith(core.ASSUMED) and "drawing" in rows[0][5]
    # no drawing -> assumed count and geometry; supplied volume wins over everything
    rows = core.stair_rows(lv, "5", None, ST, "Derived", [])
    assert "ASSUMED count" in rows[0][5]
    rows = core.stair_rows(lv, "5", plan, dict(ST, source="supplied", volume_m3=123.0), "Derived", [])
    assert rows == [("2.4", "stair", 123.0, "m3", "Supplied", "Supplied stair volume 123.0 m3")]


def test_edge_beams_follow_slab_edges(defaults):
    per = [("0", 100.0), ("1", 100.0), ("2", 120.0), ("3", 80.0)]
    rows = core.edge_beam_rows(per, defaults["edge_beams"], "Derived")
    assert rows[0][1:4] == ("edge_beam", pytest.approx(100 + 120 + 120 + 80), "m")
    assert core.edge_beam_rows(per, dict(defaults["edge_beams"], include=False), "Derived") == []
    sup = core.edge_beam_rows(per, dict(defaults["edge_beams"], source="supplied", length_m=50), "Derived")
    assert sup[0][2] == 50 and sup[0][4] == "Supplied"


def test_envelope_allowances_move_area_out_of_the_facade(defaults):
    EA = {k: dict(v) for k, v in defaults["envelope_allowances"].items()}
    rows, g, o = core.envelope_allowance_rows(1000.0, "test", 5000.0, 2000.0, 400.0, EA, "Derived")
    got = dict((r[1], r[2]) for r in rows)
    assert got == {"louvre": pytest.approx(500.0), "door_ext": pytest.approx(30.0), "roof_other": pytest.approx(400.0)}
    assert g == pytest.approx(4970.0) and o == pytest.approx(1500.0)
    assert all(r[5].startswith(core.ASSUMED) for r in rows)
    EA["louvres"].update(source="supplied", area_m2=120.0)
    rows, g, o = core.envelope_allowance_rows(1000.0, "test", 5000.0, 2000.0, 400.0, EA, "Derived")
    assert [r for r in rows if r[1] == "louvre"][0][2:5] == (120.0, "m2", "Supplied") and o == pytest.approx(1880.0)


# ----------------------------------------------------------------------------- frame systems
def _frame_rows():
    B = dict(upper_floor="SLAB", roof_slab="SLAB", column="COL-RC", edge_beam="EB", core_wall="WALL")
    base = dict(project_id="T", unit="m2", method="Derived", stage=2, model_version="v", author="XX", source_layer="L", include="Y")
    rows = [dict(base, element_id="1", nrm_code="2.2.1", build_up_code="SLAB", quantity=1000.0, notes="Suspended floor slabs"),
            dict(base, element_id="2", nrm_code="2.2.1", build_up_code="SLAB", quantity=200.0, notes="Roof slabs"),
            dict(base, element_id="3", nrm_code="2.2.1", build_up_code="SLAB", quantity=50.0, notes="Basement roof outside building footprint"),
            dict(base, element_id="4", nrm_code="2.1.1", build_up_code="COL-RC", quantity=300.0, unit="m", notes="Columns"),
            dict(base, element_id="5", nrm_code="2.1.2", build_up_code="EB", quantity=400.0, unit="m", notes="Edge beams"),
            dict(base, element_id="6", nrm_code="2.1.1", build_up_code="WALL", quantity=900.0, notes="Core walls")]
    return rows, B


def test_frame_height_factor_and_grid():
    assert core.column_height_factor(30) == pytest.approx(31 / 9)
    assert core.column_height_factor(4) == 1.0                      # never below PF's G+7 quantities
    assert core.frame_grid(6, 7.5) == "S" and core.frame_grid(9, 8) == "L"


def test_apply_frame_steel_swaps_floors_and_columns():
    rows, B = _frame_rows()
    out, info = core.apply_frame(rows, "Steel + composite deck", 9, 8, 30, B, "Derived")
    codes = [(r["build_up_code"], r["quantity"]) for r in out]
    assert ("FLR-STL-COMP-L", 1000.0) in codes and ("FLR-STL-COMP-L", 200.0) in codes
    assert ("SLAB", 50.0) in codes                                  # podium slab stays RC
    assert not any(c in ("COL-RC", "EB") for c, _ in codes)        # RC columns and edge beams removed
    assert ("WALL", 900.0) in codes                                 # cores stay
    col = next(r for r in out if r["build_up_code"] == "COL-STL-COMP-L")
    assert col["quantity"] == pytest.approx(1200 * 31 / 9, abs=0.1) and col["notes"].startswith("[ASSUMED]")
    assert info["floor_area"] == 1200.0


def test_apply_frame_pt_and_rc():
    rows, B = _frame_rows()
    out, _ = core.apply_frame(rows, "PT flat slab", 9, 8, 30, B, "Derived")
    assert sum(1 for r in out if r["build_up_code"] == core.PT_FLOOR) == 2
    assert any(r["build_up_code"] == "COL-RC" for r in out) and any(r["build_up_code"] == "EB" for r in out)
    same, _ = core.apply_frame(rows, "RC flat slab", 9, 8, 30, B, "Derived")
    assert same == rows
    with pytest.raises(ValueError):
        core.apply_frame(rows, "Bamboo", 9, 8, 30, B, "Derived")
