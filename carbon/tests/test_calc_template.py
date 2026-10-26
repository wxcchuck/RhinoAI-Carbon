"""Calculation template tests on an INVENTED library, take-off and benchmark table.
Drafted by an AI agent (Claude) - review before trusting.

No office or third-party data: every factor below is made up to give round hand numbers.

  SLAB  (m2): concrete 0.25 m3 (2400 kg/m3, 0.1 kgCO2e/kg) + steel 20 kg (1.0)      -> 80 kgCO2e/m2 A1-A3
  PANEL (m2, offsite): glass 20 kg (1.5, fab waste 3%, life 35) + steel 5 kg (life 60, fab waste 15%)
  Take-off: SLAB 1000 m2 (2.2.1), PANEL 500 m2 (2.5.2), OPQ 200 m2 (2.5.1 -> routed to PANEL),
            UNKNOWN 10 m2 (build-up not in library -> not counted, QA flag)
  Benchmark: Office '3 Finishes' 10 / 1 / 1 (A1-A3 / A4 / A5) kgCO2e/m2 GIA; GIA 2000 m2.
  Targets (invented): UKNZCBS 2027 limit, LETI bands, RIBA 2025/2030, GLA benchmark/aspirational,
  a GLA element breakdown and a Price & Myers style range - round numbers, no published values.

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


def sfround(x, n=2):
    """Excel ROUND(x, n-1-INT(LOG10(ABS(x)))) - significant figures, halves away from zero (RICS PS 6.1.4)."""
    from decimal import ROUND_HALF_UP, Decimal
    if x == 0:
        return 0.0
    d = n - 1 - math.floor(math.log10(abs(x)))
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))
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
             "TEST,E1,2.2.1,SLAB,1000,m2,Derived,2,v,XX,L,Y,[ASSUMED] slab",
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
    for s in ["README", "Project", "Dashboard", "Compare", "O1_Results", "O1_QA", "O1_Takeoff", "O1_Lines", "O1_Mat",
              "Materials", "Layers", "Buildups", "Benchmarks", "Targets", "Rebar_Rates", "Offsite_Params", "REF_Vehicles"]:
        assert s in wb.sheetnames
    for nm in ["O1_GIA", "O1_FACADE", "OPT_NAMES", "OPT_IDX", "RSP", "CONT", "USE", "CW_BU", "OPQ_BU", "V1_PAY", "V2_F50",
               "CWCT_ASM", "SEA_F", "UK_LIM", "BUD_VAL", "BUD_KEY"]:
        assert nm in wb.defined_names
    t = wb["O1_Takeoff"]
    assert [t.cell(r, 3).value for r in range(5, 9)] == ["SLAB", "PANEL", "OPQ", "UNKNOWN"]
    assert wb["O1_Lines"].max_row == 4 + (4 + ct.SPARE_ROWS) * ct.SLOTS
    assert len(wb["Dashboard"]._charts) == 7 and len(wb["Compare"]._charts) == 2
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
    T, R, Q = wb["O1_Takeoff"], wb["O1_Results"], wb["O1_QA"]

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

    # PS 5.6.4: C3 = reused + recycled share x Table 28 stand-in (no EPD processing data); C4 = landfilled share x Table 28.
    # Together they cover the whole mass once: share_C3 x T28 + share_C4 x T28 = T28
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
    # B4: glass life 35 -> ROUNDUP(60/35)-1 = 1 replacement (ROUNDDOWN would give 0); steel life 60 -> 0.
    # B4 includes the end of life (C2-C4) of the glass it removes (PS 5.2.4, XW 26/10/2026)
    g_b4 = g_a13 + p_g_off + 20 * a4["GLASS"] + 0.01 * (g_a13 + p_g_off + 20 * a4["GLASS"] + 20 * eol["GLASS"]) + 20 * eol["GLASS"]
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
    assert R["C5"].value == pytest.approx(sfround(R.cell(sub + 2, 9).value * 1000 / GIA), rel=1e-9)   # 2 s.f. at RIBA 2
    assert R.cell(sub, 16).value == pytest.approx(-0.5 * steel / 1000, rel=1e-9)         # D memo, steel only
    # QA: unknown build-up flagged; CW reference check computed
    q = {Q.cell(r, 2).value: (Q.cell(r, 3).value, Q.cell(r, 4).value) for r in range(7, 25) if Q.cell(r, 2).value}
    assert q["Take-off rows whose build-up is not in the library (not counted)"] == (1, "FLAG")
    assert q["Opaque facade rows routed to the curtain wall build-up"][0] == 1
    assert T["Z5"].value == "Assumed" and T["Z6"].value == "Derived"
    assert q["Take-off rows resting on office assumptions ([ASSUMED] in notes; Takeoff column Z)"] == (1, "INFO")
    share = T["U5"].value / 1000 / R.cell(sub, 9).value
    assert q["Share of A1-A5 resting on assumed quantities (before contingency)"][0] == pytest.approx(share, rel=1e-9)
    assert R["C10"].value == pytest.approx(share, rel=1e-9)
    cw = q["Curtain wall A1-A5 per m2 facade vs reference (kgCO2e/m2)"][0]
    assert cw == pytest.approx(g_a13 + st_a13 + off + p_a4 + p_a53, rel=1e-9)


def test_facade_as_exported_keeps_split(built, tmp_path):
    src = openpyxl.load_workbook(built["out"])
    sheet, cell = src.defined_names["O1_FACADE"].destinations.__next__()
    src[sheet][cell.replace("$", "")] = "As exported"
    path = str(tmp_path / "as_exported.xlsx")
    src.save(path)
    wb = _calc(path, str(tmp_path / "calc2"))
    T = wb["O1_Takeoff"]
    assert T["K7"].value == "OPQ" and T["L7"].value == "2.5.1"
    assert T["R7"].value == pytest.approx(200 * 0.1 * 2400 * 0.1, rel=1e-9)


# ------------------------------------------------------------------------- targets, options, dashboard
TG_UK, TG_SC, TG_GLA_B, TG_GLA_A = 600.0, 400.0, 900.0, 600.0     # invented
LETI_UP = [("A++", 50), ("A+", 100), ("A", 150), ("B", 200), ("C", 250), ("D", 300), ("E", 350), ("F", 400), ("G", 450)]
GLA_SHARE = [0.2, 0.3, 0.2, 0.1, 0.05, 0.1, 0.05]            # 7 GLA groups, sum 1


def _targets(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Targets"
    ws.append(["scheme", "target", "use_class", "year_or_band", "metric", "value", "unit", "source", "note"])
    ws.append(["UKNZCBS", "UKNZCBS 2026", "Office", 2026, "UP_X8", 700, "", "invented", ""])
    ws.append(["UKNZCBS", "UKNZCBS 2027", "Office", 2027, "UP_X8", TG_UK, "", "invented", ""])
    ws.append(["UKNZCBS", "UKNZCBS S&C 2027", "Office", 2027, "UP_X8", TG_SC, "", "invented", "offices shell & core"])
    ws.append(["UKNZCBS", "UKNZCBS 2027", "Residential", 2027, "UP_X8", 1, "", "invented", "other use - must be ignored"])
    for b, v in LETI_UP:
        ws.append(["LETI upfront", "LETI band " + b, "Office", b, "UP_X8", v, "", "invented", ""])
        ws.append(["LETI life cycle", "LETI band " + b, "Office", b, "AC_X8", 2 * v, "", "invented", ""])
    ws.append(["RIBA 2030", "RIBA 2025", "Office", 2025, "AC_X8", 800, "", "invented", ""])
    ws.append(["RIBA 2030", "RIBA 2030", "Office", 2030, "AC_X8", 500, "", "invented", ""])
    for t, up, bc in (("GLA benchmark", TG_GLA_B, 400), ("GLA aspirational", TG_GLA_A, 300)):
        ws.append(["GLA", t, "Office", t.split()[1], "UP_ALL", up, "", "invented", ""])
        ws.append(["GLA", t, "Office", t.split()[1], "BC_ALL", bc, "", "invented", ""])
        ws.append(["GLA", t, "Office", t.split()[1], "AC_ALL", up + bc, "", "invented", ""])
    g = wb.create_sheet("GLA_Breakdown")
    g.append(["use_class", "metric"] + ct.GROUPS[:7])
    g.append(["Office", "UP_ALL"] + GLA_SHARE)
    g.append(["Residential", "UP_ALL"] + [1, 0, 0, 0, 0, 0, 0])
    p = wb.create_sheet("PM_Structure")
    p.append(["group", "use_class", "n", "p10", "p25", "p50", "p75", "p90", "ac_p25", "ac_p50", "ac_p75"])
    p.append(["Commercial", "Office", 10, 20, 30, 40, 50, 60, 35, 45, 55])
    wb.save(path)


@pytest.fixture
def built2(tmp_path, built):
    exp2 = str(tmp_path / "export2.csv")
    src = open(built["takeoff_csv"], encoding="utf-8").read().replace("TEST,E1,2.2.1,SLAB,1000,", "TEST,E1,2.2.1,SLAB,1500,")
    open(exp2, "w", encoding="utf-8").write(src)
    tg = str(tmp_path / "targets.xlsx")
    _targets(tg)
    cfg = dict(built)
    cfg.pop("takeoff_csv")
    cfg.update(options=[dict(name="Opt A", takeoff_csv=built["takeoff_csv"]), dict(name="Opt B", takeoff_csv=exp2)],
               targets_xlsx=tg, out=str(tmp_path / "calc2.xlsx"))
    wb = ct.build(cfg)
    wb.save(cfg["out"])
    return cfg


def test_options_targets_dashboard(built2, tmp_path):
    src = openpyxl.load_workbook(built2["out"])
    assert "O2_Results" in src.sheetnames and len(src["Dashboard"]._charts) == 7
    wb = _calc(built2["out"], str(tmp_path / "c2"))
    y = lambda k, key: wb["O%d_Results" % k]["Y%d" % ct.SUM_ROW[key]].value      # noqa: E731
    R1, R2 = wb["O1_Results"], wb["O2_Results"]

    # option 2 differs by 500 m2 of slab at 80 kgCO2e/m2 A1-A3 (plus its A4/A5.3) - check A1-A3 exactly
    assert y(2, "M_A13") - y(1, "M_A13") == pytest.approx(500 * 80 * 1.15 / GIA, rel=1e-9)
    for k, R in ((1, R1), (2, R2)):
        assert R["C5"].value == pytest.approx(sfround(y(k, "UP_ALL")), rel=1e-9)
        assert y(k, "UP_X8") == pytest.approx(y(k, "UP_ALL"), rel=1e-9)               # no external works here
        assert y(k, "MOD_UP_X8") + y(k, "BM_UP_X8") == pytest.approx(y(k, "UP_X8"), rel=1e-9)
        assert y(k, "BMS_UP_ALL") == pytest.approx(y(k, "BM_UP_ALL") * TG_GLA_A / TG_GLA_B, rel=1e-9)
        assert sum(y(k, "E_%d" % i) for i in range(8)) + y(k, "E_CONT") == pytest.approx(y(k, "UP_ALL"), rel=1e-9)
        assert y(k, "B_MOD") + y(k, "B_ASM") + y(k, "B_BM") + y(k, "B_SITE") + y(k, "B_CONT") == pytest.approx(y(k, "UP_ALL"), rel=1e-9)
        assert y(k, "UK_LIM") == TG_UK and y(k, "UK_LIM_SC") == TG_SC                   # 2027 default, Office only
        assert y(k, "UP_SC") == pytest.approx(y(k, "UP_X8"), rel=1e-9)                  # default: 100% shell & core
        assert y(k, "MOD_UP_SC") + y(k, "BM_UP_SC") == pytest.approx(y(k, "UP_SC"), rel=1e-9)
        assert y(k, "UP_WB") == "not assessed"                                          # office, no Cat B allowance
        # structure for P&M: modelled 2.2.1 slab (the only structural row) + A5.2 site lump
        slab = next(r for r in range(14, R.max_row + 1) if R.cell(r, 1).value == "2.2.1" and R.cell(r, 21).value == "Modelled")
        a52 = next(r for r in range(14, R.max_row + 1) if R.cell(r, 1).value == "A5.2")
        assert y(k, "STRUCT") == pytest.approx((R.cell(slab, 9).value + R.cell(a52, 9).value) * 1000 / GIA, rel=1e-9)
        band = next((b for b, v in LETI_UP if y(k, "UP_X8") <= v), "worse than G")
        assert y(k, "LETI_UP") == band
        assert y(k, "STRUCT") > 0
        assert y(k, "BIO_STORED") == pytest.approx(-y(k, "BIO_RELEASED"), abs=1e-9)        # stored = released over the life cycle

    # Compare reads each option; Dashboard follows the selected option
    C = wb["Compare"]
    assert [C.cell(4, c).value for c in (2, 3)] == ["Opt A", "Opt B"]
    assert C["C6"].value == pytest.approx(sfround(y(2, "UP_ALL")), rel=1e-9)
    D = wb["Dashboard"]
    assert D["U%d" % ct.SUM_ROW["UP_ALL"]].value == pytest.approx(y(1, "UP_ALL"), rel=1e-9)
    assert D["H13"].value == TG_SC and D["G13"].value == pytest.approx(sfround(y(1, "UP_SC")), rel=1e-9)   # offices: S&C limit
    assert D["F13"].value == pytest.approx(sfround(y(1, "UP_SC") / 1.15), rel=1e-9)                       # before contingency
    assert D["H14"].value == TG_UK and D["J14"].value == "Not assessed"                          # whole building needs Cat B
    assert C["C8"].value == pytest.approx(sfround(y(2, "UP_ALL") / 1.15), rel=1e-9)               # Compare: before contingency
    # budget (UKNZCBS offices -> shell & core): target - modelled = what is left
    assert D["Y53"].value == TG_SC
    assert D["Y55"].value == pytest.approx(sfround(TG_SC - y(1, "MOD_UP_SC")), rel=1e-9)
    assert D["D76"].value == 30 and D["D77"].value == 35                                         # P&M A1-A5 / A1-C4 P25
    # GLA element comparison: share x GLA total; project incl. contingency
    assert D["Z46"].value == pytest.approx(GLA_SHARE[3] * TG_GLA_A, rel=1e-9)
    assert D["AA46"].value == pytest.approx(GLA_SHARE[3] * TG_GLA_B, rel=1e-9)
    assert D["Y46"].value == pytest.approx(y(1, "E_3") * 1.15, rel=1e-9)

    # result states: a limit between the before- and incl.-contingency figures -> "Meets before contingency only"
    mid = y(1, "UP_SC") * (1 + 1 / 1.15) / 2
    t_ = src["Targets"]
    row_sc = next(r for r in range(5, t_.max_row + 1) if t_.cell(r, 2).value == "UKNZCBS S&C 2027")
    t_.cell(row_sc, 6).value = mid
    p_mid = str(tmp_path / "mid.xlsx")
    src.save(p_mid)
    Dm = _calc(p_mid, str(tmp_path / "cm"))["Dashboard"]
    assert Dm["J13"].value == "Meets before contingency only"
    t_.cell(row_sc, 6).value = TG_SC
    src["Dashboard"]["N3"] = "Opt B"

    def setn(nm, val):
        sh, ref = next(iter(src.defined_names[nm].destinations))
        src[sh][ref.replace("$", "")] = val
    setn("SC_FIN", 0.25)                     # 75% of finishes is Cat A
    setn("CATB", 50)                         # Cat B + loose FF&E allowance, before contingency
    setn("STAGE", 3)                         # RIBA 3: building-level results to 3 significant figures
    path = str(tmp_path / "sel.xlsx")
    src.save(path)
    w3 = _calc(path, str(tmp_path / "c3"))
    D2 = w3["Dashboard"]
    assert D2["U%d" % ct.SUM_ROW["UP_ALL"]].value == pytest.approx(y(2, "UP_ALL"), rel=1e-9)
    y3 = lambda key: w3["O1_Results"]["Y%d" % ct.SUM_ROW[key]].value      # noqa: E731
    assert y3("UP_SC") == pytest.approx(y(1, "UP_X8") - 0.75 * y(1, "E_3") * 1.15, rel=1e-9)
    assert y3("BM_UP_SC") == pytest.approx(y(1, "BM_UP_X8") - 0.75 * y(1, "E_3") * 1.15, rel=1e-9)   # finishes are benchmarked
    assert y3("UP_WB") == pytest.approx(y(1, "UP_X8") + 50 * 1.15, rel=1e-9)
    assert w3["O1_Results"]["C5"].value == pytest.approx(sfround(y(1, "UP_ALL"), 3), rel=1e-9)


def test_biogenic_reported_separately_and_nets_to_zero_in_ac(built, tmp_path):
    """PS: biogenic carbon is not in upfront A1-A5 (reported separately) but is included in A-C, where storage in
    A1-A3 and release at end of life net to zero. Invented: glass given -0.5 kgCO2e/kg biogenic."""
    base = _calc(built["out"], str(tmp_path / "b0"))
    lib2 = str(tmp_path / "lib_bio.xlsx")
    wb = openpyxl.load_workbook(built["library_xlsx"])
    M = wb["Materials"]
    row = next(r for r in range(5, 10) if M.cell(r, 1).value == "GLASS")
    M.cell(row, 7).value = -0.5
    wb.save(lib2)
    cfg = dict(built, library_xlsx=lib2, out=str(tmp_path / "bio.xlsx"))
    ct.build(cfg).save(cfg["out"])
    w = _calc(cfg["out"], str(tmp_path / "b1"))
    y = lambda wb_, key: wb_["O1_Results"]["Y%d" % ct.SUM_ROW[key]].value      # noqa: E731
    stored = -0.5 * 700 * 20 * 2 / GIA          # 700 m2 panel x 20 kg glass, replaced once (life 35 in a 60-year RSP)
    assert y(w, "BIO_STORED") == pytest.approx(stored, rel=1e-9)
    assert y(w, "BIO_RELEASED") == pytest.approx(-stored, rel=1e-9)
    assert y(w, "UP_ALL") == pytest.approx(y(base, "UP_ALL"), rel=1e-12)       # not in upfront
    assert y(w, "AC_ALL") == pytest.approx(y(base, "AC_ALL"), rel=1e-12)       # in A-C, nets to zero
    assert "Biogenic carbon stored" in w["Dashboard"]["A10"].value


def _eol_library(src, dst):
    """Invented end-of-life data: GLASS re-routed to 95% incineration / 5% landfill with 2.0 kgCO2e/kg fossil CO2 on
    combustion; CONC treated as bio-based (Table 28 'wood' 900 kg/t); Table 27 + grid factor rows."""
    wb = openpyxl.load_workbook(src)
    M = wb["Materials"]
    M.cell(4, 23, "Combustion CO2, fossil (kgCO2e/kg)")
    for r in range(5, 8):
        if M.cell(r, 1).value == "GLASS":
            M.cell(r, 14).value, M.cell(r, 23).value = "PLAS", 2.0
        if M.cell(r, 1).value == "CONC":
            M.cell(r, 15).value = ct.T28_BIO
    T23 = wb["REF_T23_EoL"]
    T23.append(["PLAS", "", "", 0, 0, 95, 5])
    wb["REF_T28_C4"].append([ct.T28_BIO, "", 900])
    wb["REF_T28_C4"].append([ct.T28_INERT, "", 1.234])
    t27 = wb.create_sheet("REF_T27_D1")
    for row in (["Category ID", "EfW type", "kWh/t"], ["EFW-BIOMASS", "", 880], ["EFW-NONBIOMASS", "", 560], [],
                ["Grid carbon factor (kgCO2e/kWh)", "", 0.2, "invented"]):
        t27.append(row)
    wb.save(dst)


def test_end_of_life_routes_ps_5_6_4(built, tmp_path):
    """C3 / C4 / D per Table 23 route: recovered share x Table 28 stand-in in C3; incinerated share x combustion CO2
    in C3 (energy recovery) or C4 (disposal) with D1 = -share x Table 27 kWh/t x grid only for energy recovery;
    landfill share x Table 28 in C4. The route choice moves carbon between C3 and C4, never in or out of A-C."""
    lib2 = str(tmp_path / "lib_eol.xlsx")
    _eol_library(built["library_xlsx"], lib2)
    assert ct.grid_from_library(openpyxl.load_workbook(lib2)) == (0.2, "invented")
    got = {}
    for mode, extra in (("efw", {}), ("disp", {"efw_route": ct.EFW_OPTS[1]}), ("wood", {"bio_standin": ct.STANDIN_OPTS[0]})):
        cfg = dict(built, library_xlsx=lib2, out=str(tmp_path / ("eol_%s.xlsx" % mode)),
                   params=dict(built["params"], **extra))
        ct.build(cfg).save(cfg["out"])
        w = _calc(cfg["out"], str(tmp_path / ("e_" + mode)))
        M = w["Materials"]
        row = {M.cell(r, 1).value: r for r in range(5, 8)}
        got[mode] = dict(w=w, g=lambda c, m, M=M, row=row: M["%s%d" % (c, row[m])].value)
    efw, disp, wood = (got[k]["g"] for k in ("efw", "disp", "wood"))
    # glass: 95% burnt x 2.0 in C3 + D1 = -0.95 x 560/1000 x 0.2; 5% landfilled x 1.234/1000 in C4
    assert efw("AM", "GLASS") == pytest.approx(0.95 * 2.0, rel=1e-12)
    assert efw("AN", "GLASS") == pytest.approx(0.05 * 1.234e-3, rel=1e-12)
    assert efw("AO", "GLASS") == pytest.approx(-0.95 * 560 / 1000 * 0.2, rel=1e-12)
    assert disp("AM", "GLASS") == pytest.approx(0, abs=1e-15)
    assert disp("AN", "GLASS") == pytest.approx(0.95 * 2.0 + 0.05 * 1.234e-3, rel=1e-12)
    assert disp("AO", "GLASS") == pytest.approx(0, abs=1e-15)
    # bio-based: Table 28 wood (landfill methane) on the landfilled 2.5% only; the recovered 97.5% takes the inert
    # stand-in by default, or the wood factor with the switch
    assert efw("AM", "CONC") == pytest.approx(0.975 * 1.234e-3, rel=1e-12)
    assert wood("AM", "CONC") == pytest.approx(0.975 * 0.9, rel=1e-12)
    assert efw("AN", "CONC") == wood("AN", "CONC") == pytest.approx(0.025 * 0.9, rel=1e-12)
    # library D replaces the energy-recovery estimate (steel keeps its -0.5)
    assert efw("AO", "STEEL") == pytest.approx(-0.5)
    y = lambda k, key: got[k]["w"]["O1_Results"]["Y%d" % ct.SUM_ROW[key]].value      # noqa: E731
    assert y("efw", "AC_ALL") == pytest.approx(y("disp", "AC_ALL"), rel=1e-12)
    assert y("efw", "M_D") < y("disp", "M_D")
    assert "energy recovery assumed (R1" in got["efw"]["w"]["Dashboard"]["A10"].value
    assert "treated as disposal" in got["disp"]["w"]["Dashboard"]["A10"].value


def _b6_library(src, dst):
    """Invented REF_B6B7: factors, and an FES series of 0.10 kgCO2/kWh to 2034 then 0.02 to 2050 (held after 2050)."""
    wb = openpyxl.load_workbook(src)
    ws = wb.create_sheet("REF_B6B7")
    for i, (k_, v_) in enumerate([("ELEC-GEN", 0.2), ("ELEC-TD", 0.02), ("ELEC-WTT-GEN", 0.04), ("ELEC-WTT-TD", 0.004),
                                  ("ELEC-INFRA", 0.02), ("ELEC-INFRA-TD", 0.0004), ("GAS", 0.2), ("GAS-WTT", 0.03),
                                  ("WATER-SUPPLY", 0.2), ("WATER-TREAT", 0.1), ("WASTEWATER-SHARE", 0.9), ("EMB-DECARB", 0.5)]):
        ws.cell(5 + i, 1, k_)
        ws.cell(5 + i, 3, v_)
    for i, y_ in enumerate(range(2024, 2051)):
        ws.cell(5 + i, 7, y_)
        ws.cell(5 + i, 8, 0.10 if y_ <= 2034 else 0.02)
    wb.save(dst)


def test_b6_b7_both_scenarios_and_routes(built, tmp_path):
    """PS 5.3 / 5.4 / App. G: B6 and B7 over the RSP without and with grid decarbonisation, per option, no contingency;
    PS 4.11.5 Table 15 material decarbonisation in the decarbonised whole life figure; indicative EUI and water budget."""
    lib2, tg = str(tmp_path / "lib_b6.xlsx"), str(tmp_path / "tg_b6.xlsx")
    _b6_library(built["library_xlsx"], lib2)
    _targets(tg)
    t = openpyxl.load_workbook(tg)
    for row in (["UKNZCBS", "UKNZCBS 2027", "Office", 2027, "EUI", 80], ["RIBA 2030", "RIBA 2025", "Office", 2025, "EUI", 75],
                ["RIBA 2030", "RIBA 2030", "Office", 2030, "EUI", 55], ["RIBA 2030", "RIBA 2025", "Office", 2025, "WATER_LPD", 13]):
        t["Targets"].append(row + ["", "invented", ""])
    t.save(tg)
    op = dict(elec=100000, gas=20000, pv_self=5000, pv_export=2000, water=1000)
    got = {}
    for tag, route, opk, extra in (("eng", ct.OP_ROUTES[0], op, {}), ("ind", ct.OP_ROUTES[1], {}, {}),
                                   ("est", ct.OP_ROUTES[1], dict(eui=60), dict(occupancy=100, occ_days=250))):
        cfg = dict(built, library_xlsx=lib2, targets_xlsx=tg, out=str(tmp_path / ("b6_%s.xlsx" % tag)),
                   params=dict(built["params"], op_route=route, op_year=2030, construction_start_year=2027, **extra))
        cfg.pop("takeoff_csv")
        cfg["options"] = [dict(name="A", takeoff_csv=built["takeoff_csv"], operational=opk)]
        ct.build(cfg).save(cfg["out"])
        w = _calc(cfg["out"], str(tmp_path / ("c_" + tag)))
        got[tag] = (lambda key, w=w: w["O1_Results"]["Y%d" % ct.SUM_ROW[key]].value, w)
    fes = (5 * 0.10 + 16 * 0.02 + 39 * 0.02) / 60                       # 2030-2089: five years at 0.10, then 0.02
    dec = fes / 0.2
    f_e_nd, f_e_d = 0.2844, fes + 0.064 * dec + 0.0204 * 0.5
    f_g_nd, f_g_d, f_w_nd = 0.23, 0.2 + 0.03 * dec, 0.2 + 0.9 * 0.1
    g, w = got["eng"]
    assert g("B6_ND") == pytest.approx(60 * (100000 * f_e_nd + 20000 * f_g_nd) / GIA, rel=1e-9)
    assert g("B6_D") == pytest.approx(60 * (100000 * f_e_d + 20000 * f_g_d) / GIA, rel=1e-9)
    assert g("B7_ND") == pytest.approx(60 * 1000 * f_w_nd / GIA, rel=1e-9)
    assert g("B7_D") == pytest.approx(60 * 1000 * f_w_nd * dec / GIA, rel=1e-9)
    assert g("EUI") == pytest.approx(125000 / GIA, rel=1e-9) and g("EUI_LIM") == 80
    assert g("D2_PV") == pytest.approx(-60 * 2000 * fes / GIA, rel=1e-9)
    assert g("WLC_ND") == pytest.approx(g("AC_ALL") + g("B6_ND") + g("B7_ND"), rel=1e-12)
    assert g("OP_STATUS") == "Energy: engineer prediction | water: engineer"
    # Table 15: B2-B4 and C1-C2 halved, A1-A5, C3-C4 and biogenic unchanged (contingency on both)
    R = w["O1_Results"]
    tot = next(r for r in range(14, R.max_row + 1) if str(R.cell(r, 2).value or "").startswith("TOTAL"))
    half = 0.5 * (R["J%d" % tot].value + R["K%d" % tot].value + R["L%d" % tot].value) * 1000 / GIA + 0.5 * (g("M_B2") + g("M_B3"))
    assert half > 0 and g("AC_DEC") == pytest.approx(g("AC_ALL") - half, rel=1e-9)
    assert g("WLC_D") == pytest.approx(g("AC_DEC") + g("B6_D") + g("B7_D"), rel=1e-12)
    i, _ = got["ind"]                                                    # UKNZCBS EUI limit x GIA, all electric; gas and PV ignored
    assert i("B6_ND") == pytest.approx(60 * 80 * f_e_nd, rel=1e-9) and i("EUI") == pytest.approx(80)
    assert i("OP_STATUS") == "Energy: indicative (UKNZCBS limit) | water: not assessed" and i("B7_ND") == 0
    e, _ = got["est"]                                                    # option's own EUI estimate; water = 100 x 13 l x 250 days
    assert e("B6_ND") == pytest.approx(60 * 60 * f_e_nd, rel=1e-9) and e("W_M3") == pytest.approx(100 * 13 * 250 / 1000)
    assert e("B7_ND") == pytest.approx(60 * 325 * f_w_nd / GIA, rel=1e-9)
    assert e("OP_STATUS") == "Energy: indicative (EUI estimate) | water: indicative budget (occupancy x RIBA 2025)"


def test_results_reader_for_the_window(built2, tmp_path):
    """wlca_results.read_results on the calculated two-option workbook (LibreOffice stands in for Excel here)."""
    import wlca_results as wr
    assert wr.read_results(built2["out"])["calculated"] is False            # openpyxl output: formulas only
    _calc(built2["out"], str(tmp_path / "calc"))
    res = wr.read_results(str(tmp_path / "calc" / os.path.basename(built2["out"])))
    assert res["calculated"] and [o["values"]["NAME"] for o in res["options"]] == ["Opt A", "Opt B"]
    assert res["cont"] == pytest.approx(0.15) and res["targets"]
    assert res["sc"] == {"fin": 1.0, "ffe": 1.0, "mep": 1.0} and res["catb"] is None        # for the targets chart columns
    for o in res["options"]:          # the A1-A5 column of the targets chart: element groups + contingency = the headline
        v = o["values"]
        assert o["traj"]["emb_nd"][-1] == pytest.approx(v["AC_ALL"], rel=1e-6)                   # trajectory ends at A-C
        assert len(o["traj"]["t"]) == 61 and len(o["traj"]["b4"][0]) == 8
        assert sum(v["E_%d" % i] for i in range(8)) + v["E_CONT"] == pytest.approx(v["UP_ALL"], rel=1e-6)
    for o in res["options"]:
        v = o["values"]
        parts = sum(v[k] or 0 for k in ("B_MOD", "B_ASM", "B_BM", "B_SITE", "B_CONT"))
        assert parts == pytest.approx(v["UP_ALL"], rel=1e-6)                # the doughnut adds up to the headline
        mods = sum(v[k] or 0 for k in ("M_A13", "M_A4", "M_A5"))
        assert mods == pytest.approx(v["UP_ALL"], rel=1e-6)                 # A1-A3 + A4 + A5 = A1-A5
    assert res["options"][1]["values"]["UP_ALL"] > res["options"][0]["values"]["UP_ALL"]   # Opt B has more slab
    assert wr.judge(100, 120, 0.15) == "Meets" and wr.judge(130, 120, 0.15) == "Meets before contingency only"
    assert wr.judge(200, 120, 0.15) == "Above" and wr.judge(None, 120, 0.15) == "Not assessed"


def test_b2_b3_allowances(built, tmp_path):
    """PS 5.2.2 / 5.2.3 (XW 26/10/2026): B2 = max(GIA x 10, 1% x A1-A5 before contingency), one-off over the RSP;
    B3 = 25% x B2 x non-services share of A1-A5 + 10% x services A1-A3; contingency at the end; in A-C and its boundaries."""
    bm = str(tmp_path / "bench_mep.xlsx")                                  # add a services benchmark so the MEP rule is exercised
    b = openpyxl.load_workbook(built["benchmarks"]["path"])
    b["Bench"].append(["", "Office", "5 Services (MEP)", 60, 2, 3, 40, 1, 0.5, 0.5, 0.1, None])
    b.save(bm)
    for tag, extra in (("gia", {}), ("pct", dict(b2_share=0.5))):
        cfg = dict(built, out=str(tmp_path / ("b2_%s.xlsx" % tag)), params=dict(built["params"], **extra),
                   benchmarks=dict(built["benchmarks"], path=bm))
        ct.build(cfg).save(cfg["out"])
        w = _calc(cfg["out"], str(tmp_path / ("c_b2_" + tag)))
        R = w["O1_Results"]
        g = lambda key: R["Y%d" % ct.SUM_ROW[key]].value                  # noqa: E731
        rows = dict((str(R.cell(r, 2).value or ""), r) for r in range(14, R.max_row + 1))
        sub = rows["Subtotal"]
        a15 = R["I%d" % sub].value
        svc = [r for r in range(14, sub) if R.cell(r, 20).value == "Services/MEP"]
        svc_a15 = sum(R["I%d" % r].value or 0 for r in svc)
        svc_a13 = sum(R["D%d" % r].value or 0 for r in svc)
        gia, cont = g("GIA"), w["Project"]["C%d" % next(r for r in range(5, 80) if w["Project"].cell(r, 2).value == "Contingency")].value
        share = extra.get("b2_share", 0.01)
        b2 = max(gia * 10 / 1000, share * a15)
        b3 = 0.25 * b2 * (1 - svc_a15 / a15) + 0.10 * svc_a13
        assert R["C%d" % rows["B2 maintenance - the greater of the two"]].value == pytest.approx(b2, rel=1e-9)
        assert R["C%d" % rows["B3 repair"]].value == pytest.approx(b3, rel=1e-9)
        assert g("M_B2") == pytest.approx(b2 * (1 + cont) * 1000 / gia, rel=1e-9)
        assert g("M_B3") == pytest.approx(b3 * (1 + cont) * 1000 / gia, rel=1e-9)
        assert g("B2_BASIS") == ("GIA x rate" if tag == "gia" else "% of A1-A5")
        tot = rows["TOTAL incl. contingency"]
        assert g("AC_T") == pytest.approx(R["O%d" % tot].value + (b2 + b3) * (1 + cont), rel=1e-9)
        bio = g("BIO_STORED") + g("BIO_RELEASED")
        assert g("AC_ALL") == pytest.approx((R["O%d" % tot].value + (b2 + b3) * (1 + cont)) * 1000 / gia + bio, rel=1e-9)
        assert g("BC_ALL") == pytest.approx(g("AC_ALL") - bio - g("UP_ALL"), rel=1e-9)
        assert g("UP_ALL") == pytest.approx(R["I%d" % tot].value * 1000 / gia, rel=1e-9)       # upfront untouched
        assert svc and svc_a13 > 0


def test_scope_check_expects_what_the_design_has():
    ce = ct.coverage_expected
    assert ce("1.2.2", "Y", {}) == ("Y", "")                                   # older exports: as before
    assert ce("1.2.2", "Y", {"basement_levels": "1"})[0] == "N"                 # one level: lowest slab + ground slab only
    assert ce("1.2.2", "Y", {"basement_levels": "2"})[0] == "Y"
    assert ce("1.2.3", "Y", {"basement_levels": "0", "basement_depth_m": "0"}) == ("N", "no basement")
    assert ce("1.2.3", "Y", {"basement_levels": "1", "basement_depth_m": "5.5"})[0] == "Y"
    assert ce("2.5.2", "Y", {"facade_curtain_wall_share": "0.0"})[0] == "N"     # brick + punched windows: glazing in 2.6
    assert ce("2.5.2", "Y", {"facade_curtain_wall_share": "0.25"})[0] == "Y"
    assert ce("2.6", "Y", {"facade_curtain_wall_share": "1.0"}) == ("Y", "")    # entrance doors are always there


def test_trajectory_ends_at_the_totals(built, tmp_path):
    """O<k>_Traj (XW 26/10/2026): per-year carbon over the RSP; cumulative columns end at A-C and A-C + B6 + B7,
    both scenarios; year 0 = A1-A5; replacements land in their years; B2 + B3 and B6 + B7 every year."""
    lib2, tg = str(tmp_path / "lib_tr.xlsx"), str(tmp_path / "tg_tr.xlsx")
    _b6_library(built["library_xlsx"], lib2)
    _targets(tg)
    bm = str(tmp_path / "bench_tr.xlsx")
    b = openpyxl.load_workbook(built["benchmarks"]["path"])
    b["Bench"].append(["", "Office", "5 Services (MEP)", 60, 2, 3, 40, 1, 0.5, 0.5, 0.1, None])
    b.save(bm)
    cfg = dict(built, library_xlsx=lib2, targets_xlsx=tg, out=str(tmp_path / "tr.xlsx"), benchmarks=dict(built["benchmarks"], path=bm),
               params=dict(built["params"], op_route=ct.OP_ROUTES[0], op_year=2030, construction_start_year=2027))
    cfg.pop("takeoff_csv")
    cfg["options"] = [dict(name="A", takeoff_csv=built["takeoff_csv"], operational=dict(elec=100000, gas=20000, water=1000))]
    ct.build(cfg).save(cfg["out"])
    w = _calc(cfg["out"], str(tmp_path / "c_tr"))
    R, T = w["O1_Results"], w["O1_Traj"]
    g = lambda key: R["Y%d" % ct.SUM_ROW[key]].value                      # noqa: E731
    f0, rsp = ct.TRAJ_FIRST, 60
    col = lambda c, r: T.cell(r, c).value                                 # noqa: E731
    last = f0 + rsp
    K = ct.TRAJ_KEY
    assert col(K["t"], f0) == 0 and col(K["t"], last) == rsp and col(K["year"], f0 + 1) == 2030
    assert col(K["emb_nd"], last) == pytest.approx(g("AC_ALL"), rel=1e-9)
    assert col(K["emb_d"], last) == pytest.approx(g("AC_DEC"), rel=1e-9)
    assert col(K["wlc_nd"], last) == pytest.approx(g("WLC_ND"), rel=1e-9)
    assert col(K["wlc_d"], last) == pytest.approx(g("WLC_D"), rel=1e-9)
    assert col(K["emb_nd"], f0) == pytest.approx(g("UP_ALL"), rel=1e-9)            # year 0 = the headline A1-A5 (no biogenic)
    assert col(K["emb_d"], f0) == pytest.approx(g("UP_ALL"), rel=1e-9)
    assert col(K["bio"], f0) == pytest.approx(g("BIO_STORED"), rel=1e-9)            # biogenic in its own column ...
    assert col(K["bio"], last) == pytest.approx(0, abs=1e-9)                        # ... netting to zero at the RSP
    b4 = [sum(col(c, r) or 0 for c in range(K["b4_first"], K["b4_first"] + 8)) for r in range(f0, last + 1)]
    gia = g("GIA")
    assert sum(b4) * 1000 / gia == pytest.approx(g("M_B4") / 1.15, rel=1e-6)      # every replacement lands in a year (B4 incl. its EoL)
    c_end = col(16, last) * 1000 / gia
    assert c_end == pytest.approx(g("M_C") / 1.15, rel=1e-6)                       # C1-C4 at the RSP = the C module
    svc = [col(K["b4_first"] + 5, r) or 0 for r in range(f0, last + 1)]  # benchmarked services: every 20 years
    assert [i for i, x in enumerate(svc) if x > 1e-9] == [20, 40]
    nd = [col(K["wlc_nd"], r) for r in range(f0, last + 1)]
    assert all(b_ >= a_ - 1e-9 for a_, b_ in zip(nd, nd[1:]))              # cumulative never falls (no storage after year 0)


def test_trajectory_layout_shared_with_the_reader():
    import wlca_results as wr
    assert wr.TRAJ_FIRST == ct.TRAJ_FIRST and wr.TRAJ_COLS == ct.TRAJ_KEY and wr.TRAJ_GROUPS == len(ct.GROUPS)
