"""Calculation template tests on an INVENTED library, take-off and benchmark table.
Drafted by an AI agent (Claude) - review before trusting.

No office or third-party data: every factor below is made up to give round hand numbers.

  SLAB  (m2): concrete 0.25 m3 (2400 kg/m3, 0.1 kgCO2e/kg) + steel 20 kg (1.0)      -> 80 kgCO2e/m2 A1-A3
  PANEL (m2, offsite): glass 20 kg (1.5, fab waste 3%, life 35) + steel 5 kg (life 60, fab waste 15%)
  Take-off: SLAB 1000 m2 (2.2.1), PANEL 500 m2 (2.5.2), OPQ 200 m2 (2.5.1 -> routed to PANEL),
            UNKNOWN 10 m2 (build-up not in library -> not counted, QA flag)
  Benchmark: Office '3 Finishes' 10 / 1 / 1 (A1-A3 / A4 / A5) kgCO2e/m2 GIA; GIA 2000 m2.

The structural tests always run. The numeric tests need LibreOffice (soffice) to calculate the
workbook; they are skipped without it.
"""
import math
import os
import shutil
import subprocess

import pytest

openpyxl = pytest.importorskip("openpyxl")

import wlca_calc_template as ct  # noqa: E402

GIA = 2000.0
VEH = dict(pay=13.0, vol=65.0, c1=0.99156, erf=1.0, c2=0.774, f50=0.94152)
ASM, A2F, SEA = 0.2, 0.04, 0.016


def _library(path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def sheet(name, hdr, rows):
        ws = wb.create_sheet(name)
        for c, h in enumerate(hdr, start=1):
            ws.cell(4, c, h)
        for i, r in enumerate(rows):
            for c, v in enumerate(r, start=1):
                ws.cell(5 + i, c, v)
        return ws

    mh = ["material_id", "Name", "Declared unit", "kg per declared unit", "Density (kg/m³)", "A1–A3", "Biogenic",
          "Source type", "Source", "Data year", "T17", "T18", "T20", "T23", "T28", "Status", "Notes", "Used",
          "C3 override (kgCO2e/kg)", "C4 override (kgCO2e/kg)", "D (kgCO2e/kg)", "EoL / D source"]
    sheet("Materials", mh, [
        ["CONC", "Concrete", "kg", 1, 2400, 0.1, 0, "", "", "", "LOCAL", "WR5", "L60", "CONC", "INERT", "READY", "", "", None, None, None, ""],
        ["STEEL", "Steel", "kg", 1, 7850, 1.0, 0, "", "", "", "NATIONAL", "WR5", "L60", "METAL", "MET", "READY", "", "", None, None, -0.5, "x"],
        ["GLASS", "Glass", "kg", 1, 2500, 1.5, 0, "", "", "", "EURO", "WR1", "L30", "GLASS", "INERT", "READY", "", "", None, None, None, ""],
    ])
    lh = ["build_up_code", "Seq", "material_id", "Quantity", "Qty unit", "Basis", "G", "H", "I", "J", "K", "L",
          "Reports to", "Assumed", "Life override", "Site WR override", "Fab WR"]
    sheet("Layers", lh, [
        ["SLAB", 1, "CONC", 0.25, "m3", "", None, None, None, None, None, None, None, "N", None, None, None],
        ["SLAB", 2, "STEEL", "=Rebar_Rates!$C$5", "kg", "", None, None, None, None, None, None, None, "N", None, None, None],
        ["PANEL", 1, "GLASS", 20, "kg", "", None, None, None, None, None, None, None, "N", None, 0.01, 0.03],
        ["PANEL", 2, "STEEL", 5, "kg", "", None, None, None, None, None, None, None, "N", 60, 0.01, 0.15],
        ["OPQ", 1, "CONC", 0.1, "m3", "", None, None, None, None, None, None, None, "N", None, None, None],
    ])
    bh = ["build_up_code", "RICS code", "Description", "Declared unit", "Basis", "Version", "Status", "Provenance",
          "I", "J", "K", "L", "M", "N", "O", "P", "Offsite manufactured (CWCT A3)"]
    sheet("Buildups", bh, [
        ["SLAB", "2.2.1", "Slab", "m2", "", "0.1", "DRAFT", "", None, None, None, None, None, None, None, None, "N"],
        ["PANEL", "2.5.2", "Panel", "m2", "", "0.1", "DRAFT", "", None, None, None, None, None, None, None, None, "Y"],
        ["OPQ", "2.5.1", "Opaque", "m2", "", "0.1", "DRAFT", "", None, None, None, None, None, None, None, None, "N"],
    ])
    sheet("Rebar_Rates", ["rate_id", "Element", "Rate"], [["RB", "Slab steel", 20]])
    sheet("Offsite_Params", ["param_id", "Parameter", "Value"], [["CWCT-A3-ASSEMBLY", "a", ASM], ["CWCT-A2-FAB", "b", A2F]])
    sheet("REF_T17_Transport", ["id", "s", "e", "road", "sea"], [["LOCAL", "", "", 20, None], ["NATIONAL", "", "", 120, None],
                                                                ["EURO", "", "", 1500, 100]])
    sheet("REF_T18_Waste", ["id", "m", "rate"], [["WR5", "", 0.05], ["WR1", "", 0.01]])
    sheet("REF_T20_ServiceLife", ["id", "p", "e", "life"], [["L60", "", "", 60], ["L30", "", "", 35]])
    sheet("REF_T23_EoL", ["id", "m", "d", "reuse", "rec", "inc", "disp"], [["CONC", "", "", 0, 97.5, 0, 2.5],
                                                                          ["METAL", "", "", 0, 98, 0, 2],
                                                                          ["GLASS", "", "", 0, 61, 0, 39]])
    sheet("REF_T28_C4", ["id", "m", "kg/t"], [["INERT", "", 1.234], ["MET", "", 1.264]])
    sheet("REF_Vehicles", ["id", "label", "t", "m3", "c1", "erf", "c2", "c50"],
          [["HGV", "test HGV", VEH["pay"], VEH["vol"], VEH["c1"], VEH["erf"], VEH["c2"], VEH["f50"]]])
    wb.save(path)


def _export(path):
    lines = ["# project_id: TEST", "# use_class: Office", "# riba_stage: 2", "# gia_m2: %s" % GIA,
             "# existing_gia_demolished_m2: 0", "# schema_version: 0.1",
             "project_id,element_id,nrm_code,build_up_code,quantity,unit,method,stage,model_version,author,source_layer,include,notes",
             "TEST,E1,2.2.1,SLAB,1000,m2,Derived,2,v,XX,L,Y,slab",
             "TEST,E2,2.5.2,PANEL,500,m2,Derived,2,v,XX,L,Y,glazing",
             "TEST,E3,2.5.1,OPQ,200,m2,Derived,2,v,XX,L,Y,opaque facade",
             "TEST,E4,2.5.3,UNKNOWN,10,m2,Derived,2,v,XX,L,Y,roof"]
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def _bench(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bench"
    ws.append(["", "NOTE"])
    ws.append(["", "Building Type", "Building Element Category", "A1-A3", "A4", "A5", "B4", "C1", "C2", "C3", "C4", "D"])
    ws.append(["", "Office", "3 Finishes", 10, 1, 1, 5, 1, 0.5, 0.5, 0.1, None])
    ws.append(["", "Residential", "3 Finishes", 99, 9, 9, 9, 9, 9, 9, 9, None])
    ws.append(["", "Office", "Site emissions", 40, 0, 0, 0, 0, 0, 0, 0, None])     # ignored: no element key
    wb.save(path)


@pytest.fixture
def built(tmp_path):
    lib, exp, bm = str(tmp_path / "lib.xlsx"), str(tmp_path / "export.csv"), str(tmp_path / "bench.xlsx")
    _library(lib)
    _export(exp)
    _bench(bm)
    cfg = dict(takeoff_csv=exp, library_xlsx=lib, benchmarks=dict(path=bm, sheet="Bench", source="invented"),
               site=dict(A51=35, A52=40, C1=12),
               params=dict(road_vehicle="HGV", eol_vehicle="HGV", sea_factor=SEA, eol_distances_km=[50, 60, 70],
                           facade_opaque_build_up="OPQ", cw_build_up="PANEL", cw_reference_a1a5=100),
               out=str(tmp_path / "calc.xlsx"))
    wb = ct.build(cfg)
    wb.save(cfg["out"])
    return cfg


def test_structure(built):
    wb = openpyxl.load_workbook(built["out"])
    for s in ["README", "Project", "Results", "QA", "Takeoff", "Lines", "Materials", "Layers", "Buildups", "Benchmarks",
              "Rebar_Rates", "Offsite_Params", "REF_Vehicles"]:
        assert s in wb.sheetnames
    for nm in ["GIA", "RSP", "CONT", "USE", "FACADE", "CW_BU", "OPQ_BU", "V1_PAY", "V2_F50", "CWCT_ASM", "SEA_F"]:
        assert nm in wb.defined_names
    t = wb["Takeoff"]
    assert [t.cell(r, 3).value for r in range(5, 9)] == ["SLAB", "PANEL", "OPQ", "UNKNOWN"]
    assert wb["Lines"].max_row == 4 + (4 + ct.SPARE_ROWS) * ct.SLOTS
    k = wb["Benchmarks"]
    assert [k.cell(r, 3).value for r in (5, 6)] == ["3", "3"] and k.cell(7, 1).value is None
    assert wb["Layers"]["D9"].value == "=Rebar_Rates!$C$5"     # sorted OPQ, PANEL x2, SLAB x2; formulas copied verbatim


def _calc(path, outdir):
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        pytest.skip("LibreOffice not installed - numeric checks need it to calculate the workbook")
    subprocess.run([exe, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", outdir, path],
                   check=True, capture_output=True, timeout=180)
    return openpyxl.load_workbook(os.path.join(outdir, os.path.basename(path)), data_only=True)


def test_numbers_against_hand_calculation(built, tmp_path):
    wb = _calc(built["out"], str(tmp_path / "calc"))
    T, R, Q = wb["Takeoff"], wb["Results"], wb["QA"]

    # ---- hand values
    conc = 1000 * 0.25 * 2400                                     # OPQ is routed to PANEL, so only slab concrete
    steel = 1000 * 20 + 700 * 5                                   # slab + panel (500 + 200 routed)
    glass = 700 * 20.0
    a4 = {  # per kg: loads x km x (c1 + erf c2) [+ sea]
        "CONC": math.ceil(conc / 1000 / 13) * 20 * (VEH["c1"] + VEH["c2"]) / conc,
        "STEEL": math.ceil(steel / 1000 / 13) * 120 * (VEH["c1"] + VEH["c2"]) / steel,
        "GLASS": (math.ceil(glass / 1000 / 13) * 1500 * (VEH["c1"] + VEH["c2"]) + glass / 1000 * 100 * SEA) / glass,
    }

    def c2(m, shares):  # loads per route x distance x 2 x 50% laden factor
        return sum(math.ceil(s * m / 1000 / 13) * d for s, d in zip(shares, (50, 60, 70))) * 2 * VEH["f50"] / m

    eol = {"CONC": c2(conc, (0.975, 0, 0.025)) + 0.975 * 1.234e-3 + 0.025 * 1.234e-3,
           "STEEL": c2(steel, (0.98, 0, 0.02)) + 0.98 * 1.264e-3 + 0.02 * 1.264e-3,
           "GLASS": c2(glass, (0.61, 0, 0.39)) + 0.61 * 1.234e-3 + 0.39 * 1.234e-3}

    # slab per m2
    s_a13 = 0.25 * 2400 * 0.1 + 20 * 1.0
    assert s_a13 == pytest.approx(80.0)
    s_a4 = 600 * a4["CONC"] + 20 * a4["STEEL"]
    s_a53 = 0.05 * (60 + 600 * a4["CONC"] + 600 * eol["CONC"]) + 0.05 * (20 + 20 * a4["STEEL"] + 20 * eol["STEEL"])
    assert T["R5"].value == pytest.approx(1000 * s_a13, rel=1e-9)
    assert T["S5"].value == pytest.approx(1000 * s_a4, rel=1e-9)
    assert T["T5"].value == pytest.approx(1000 * s_a53, rel=1e-9)

    # panel per m2 (offsite): product + assembly + A2 + fabrication waste
    g_a13, st_a13 = 20 * 1.5, 5 * 1.0
    off = 25 * (ASM + A2F) + 0.03 / 0.97 * (g_a13 + 20 * A2F) + 0.15 / 0.85 * (st_a13 + 5 * A2F)
    p_a4 = 20 * a4["GLASS"] + 5 * a4["STEEL"]
    p_g_off = 20 * (ASM + A2F) + 0.03 / 0.97 * (g_a13 + 20 * A2F)
    p_s_off = 5 * (ASM + A2F) + 0.15 / 0.85 * (st_a13 + 5 * A2F)
    p_a53 = 0.01 * (g_a13 + p_g_off + 20 * a4["GLASS"] + 20 * eol["GLASS"]) + \
        0.01 * (st_a13 + p_s_off + 5 * a4["STEEL"] + 5 * eol["STEEL"])
    assert T["R6"].value == pytest.approx(500 * (g_a13 + st_a13 + off), rel=1e-9)
    assert T["R7"].value == pytest.approx(200 * (g_a13 + st_a13 + off), rel=1e-9)      # routed opaque row
    assert T["K7"].value == "PANEL" and T["L7"].value == "2.5.2"
    # B4: glass life 35 -> ROUNDUP(60/35)-1 = 1 replacement (ROUNDDOWN would give 0); steel life 60 -> 0
    g_b4 = g_a13 + p_g_off + 20 * a4["GLASS"] + 0.01 * (g_a13 + p_g_off + 20 * a4["GLASS"] + 20 * eol["GLASS"])
    assert T["W6"].value == pytest.approx(500 * g_b4, rel=1e-9)
    # unknown build-up is not counted and is flagged
    assert T["U8"].value == 0 and T["Y8"].value.startswith("NOT IN LIBRARY")

    # results rows
    def row(code, method=None):
        for r in range(13, R.max_row + 1):
            if R.cell(r, 1).value == code and (method is None or R.cell(r, 3).value == method):
                return r
        raise AssertionError(code)
    assert R.cell(row("2.2.1"), 4).value == pytest.approx(80.0, rel=1e-9)                 # t A1-A3
    assert R.cell(row("2.5.2"), 8).value == pytest.approx(700 * p_a53 / 1000, rel=1e-9)   # t A5.3
    assert R.cell(row("2.5.1"), 9).value in (0, None)
    fin = row("3", "Benchmark")
    assert R.cell(fin, 4).value == pytest.approx(10 * GIA / 1000)                         # benchmark A1-A3
    assert R.cell(fin, 8).value == pytest.approx(1 * GIA / 1000)                          # benchmark A5 -> A5.3
    assert R.cell(fin, 11).value == pytest.approx(0)                                      # C1 share excluded
    assert R.cell(row("A5.2"), 7).value == pytest.approx(40 * GIA / 1000)
    assert R.cell(row("C1"), 11).value == pytest.approx(12 * GIA / 1000)
    # totals and contingency
    sub = next(r for r in range(13, R.max_row + 1) if R.cell(r, 2).value == "Subtotal")
    assert R.cell(sub + 1, 9).value == pytest.approx(0.15 * R.cell(sub, 9).value, rel=1e-9)
    assert R["C5"].value == pytest.approx(R.cell(sub + 2, 9).value * 1000 / GIA, rel=1e-9)
    assert R.cell(sub, 16).value == pytest.approx(-0.5 * steel / 1000, rel=1e-9)         # D memo, steel only
    # QA: unknown build-up flagged; CW reference check computed
    q = {Q.cell(r, 2).value: (Q.cell(r, 3).value, Q.cell(r, 4).value) for r in range(7, 20) if Q.cell(r, 2).value}
    assert q["Take-off rows whose build-up is not in the library (not counted)"] == (1, "FLAG")
    assert q["Opaque facade rows routed to the curtain wall build-up"][0] == 1
    cw = q["Curtain wall A1-A5 per m2 facade vs reference (kgCO2e/m2)"][0]
    assert cw == pytest.approx(g_a13 + st_a13 + off + p_a4 + p_a53, rel=1e-9)


def test_facade_as_exported_keeps_split(built, tmp_path):
    src = openpyxl.load_workbook(built["out"])
    p = src["Project"]
    for r in range(5, 40):
        if p.cell(r, 2).value == "Facade route":
            p.cell(r, 3).value = "As exported"
    path = str(tmp_path / "as_exported.xlsx")
    src.save(path)
    wb = _calc(path, str(tmp_path / "calc2"))
    T = wb["Takeoff"]
    assert T["K7"].value == "OPQ" and T["L7"].value == "2.5.1"
    assert T["R7"].value == pytest.approx(200 * 0.1 * 2400 * 0.1, rel=1e-9)
