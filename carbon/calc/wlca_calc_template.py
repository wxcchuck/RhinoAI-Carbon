"""
WLCA calculation template generator  v0.1  (draft for review)
Office WLCA template - build step 5: take-off export + build-up library + benchmarks -> Excel workbook

Drafted by an AI agent (Claude) - review before trusting.

Writes ONE self-contained .xlsx with live formulas, so an assessor can change an input, a factor or a
build-up in Excel and see the result move. Nothing in this script is project data or library data:
every number comes from the three inputs named in the config.

  inputs                              -> sheets
  take-off export (schema v0.1 CSV)   -> Takeoff        one row per exported quantity
  build-up library (.xlsx)            -> Materials, Layers, Buildups, Rebar_Rates, Offsite_Params, REF_*
  benchmark table (.xlsx)             -> Benchmarks     kgCO2e/m2 GIA by use class and element group

Calculation (RICS WLCA PS 2nd ed., module logic ported from the office dwelling workbook):
  Lines     take-off row x build-up layer (16 slots per row, looked up live from Layers)
            A1-A3 = qty x factor; A3 offsite (CWCT) = mass x (assembly + A2 to fabricator)
            + fabrication waste WR/(1-WR) x (A1-A3 + A2); A4 = mass x A4/kg (Materials, lorry loads);
            A5.3 = site WR x (A1-A3 + A3 offsite + A4 + C2-C4 of the waste)  [PS 5.1.4: WR x factor];
            B4 = replacements x (A1-A3 + A3 offsite + A4 + A5.3), replacements = ROUNDUP(RSP/life) - 1;
            C2-C4 and D = mass x per-kg factor x (1 + replacements)
  Materials per material: lorry loads for A4 (T17 distances, REF_Vehicles) and C2 (Table 26
            distances, 50% laden); C3/C4 = PS default (Table 23 route x Table 28) unless overridden
  Results   RICS element categories x modules; site lumps A5.1 / A5.2 / C1; contingency; per m2 GIA
  QA        checks with OK / FLAG / INFO, and a scope coverage table

Run:  python wlca_calc_template.py config.json        (see config.example.json)
"""
import csv
import io
from copy import copy
import json
import os
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

VERSION = "0.1"
SLOTS = 16                      # layers per build-up the Lines sheet can expand (library max is 15)
SPARE_ROWS = 30                 # blank Takeoff rows for manual additions

INPUT = PatternFill("solid", fgColor="FFF2CC")
HEAD = PatternFill("solid", fgColor="D9E1F2")
SECTION = PatternFill("solid", fgColor="EDEDED")
TOTAL = PatternFill("solid", fgColor="E2EFDA")
GREEN = PatternFill("solid", fgColor="C6EFCE")
AMBER = PatternFill("solid", fgColor="FFEB9C")
RED = PatternFill("solid", fgColor="FFC7CE")
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14)
WRAP = Alignment(wrap_text=True, vertical="top")
THIN = Border(bottom=Side(style="thin", color="BFBFBF"))

# Reporting rows: (code or criteria, label, kind). kind "x" = exact code, "p" = code prefix.
# Codes follow the office scope matrix (RICS building element categories).
MODELLED_ROWS = [
    ("0", "0 Facilitating works", "p"),
    ("1.1", "1.1 Foundations and piling", "x"),
    ("1.2.1", "1.2.1 Lowest slab", "x"),
    ("1.2.2", "1.2.2 Basement suspended slabs", "x"),
    ("1.2.3", "1.2.3 Basement retaining walls", "x"),
    ("2.1.1", "2.1.1 Frame - vertical (columns, core walls)", "x"),
    ("2.1.2", "2.1.2 Frame - horizontal (beams)", "x"),
    ("2.2.1", "2.2.1 Upper floors and roof slabs", "x"),
    ("2.3", "2.3 Roof - other elements", "x"),
    ("2.4", "2.4 Stairs, ramps, guarding", "p"),
    ("2.5.1", "2.5.1 External - opaque envelope", "x"),
    ("2.5.2", "2.5.2 External - glazed envelope / curtain walling", "x"),
    ("2.5.3", "2.5.3 External - roof coverings", "x"),
    ("2.6", "2.6 Windows and external doors", "x"),
    ("2.7", "2.7 Internal walls and partitions", "x"),
    ("2.8", "2.8 Internal doors", "x"),
    ("3", "3 Finishes", "p"),
    ("4", "4 FF&E", "p"),
    ("5", "5 Services (MEP)", "p"),
    ("6", "6 Prefabricated buildings", "p"),
    ("7", "7 Works to existing buildings", "p"),
    ("8", "8 External works", "p"),
]
# Element groups the benchmark table can cover -> key used to drop overlapping modelled layers
BENCH_KEYS = [("2.7/2.8", "2.7 + 2.8 Internal walls and doors"), ("3", "3 Finishes"),
              ("4", "4 FF&E (building-related, S&C + Cat A)"), ("5", "5 Services (MEP)"), ("8", "8 External works")]
# Scope coverage table: code, label, expected default ("Y", "N" or "DEMO" = only if demolition)
COVERAGE = [
    ("0.1", "Demolition / site clearance", "DEMO"), ("1.1", "Foundations and piling", "Y"),
    ("1.2.1", "Lowest slab", "Y"), ("1.2.2", "Basement suspended slabs", "Y"), ("1.2.3", "Basement retaining walls", "Y"),
    ("2.1.1", "Frame - vertical", "Y"), ("2.1.2", "Frame - horizontal (beams, transfers)", "Y"),
    ("2.2.1", "Upper floors and roof slabs", "Y"), ("2.3", "Roof - other elements", "Y"), ("2.4", "Stairs and ramps", "Y"),
    ("2.5.1", "External - opaque envelope", "Y"), ("2.5.2", "External - glazed envelope", "Y"),
    ("2.5.3", "External - roof coverings", "Y"), ("2.6", "Windows and external doors", "Y"),
    ("2.7", "Internal walls and partitions", "Y"), ("2.8", "Internal doors", "Y"), ("3", "Finishes", "Y"),
    ("4", "FF&E", "Y"), ("5", "Services (MEP)", "Y"), ("6", "Prefabricated buildings", "N"),
    ("7", "Works to existing buildings", "N"), ("8", "External works", "Y"),
]
MODULES = ["A1-A3", "A4", "A5.1", "A5.2", "A5.3", "A1-A5", "B4", "C1", "C2", "C3", "C4", "A-C", "D", "Bio"]


# --------------------------------------------------------------------------------------- inputs
def read_export(path):
    """Interchange schema v0.1 CSV: '# key: value' header lines, then a CSV table."""
    header, lines = {}, []
    with open(path, encoding="utf-8-sig") as f:
        for ln in f:
            if ln.startswith("#"):
                k, _, v = ln[1:].partition(":")
                header[k.strip()] = v.strip()
            elif ln.strip():
                lines.append(ln)
    rows = list(csv.DictReader(io.StringIO("".join(lines))))
    for r in rows:
        r["quantity"] = float(r["quantity"])
    return header, rows


def read_sheet(wb, name, header_row=4, first=5):
    ws = wb[name]
    hdr = [c.value for c in ws[header_row]]
    out = []
    for r in range(first, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, len(hdr) + 1)]
        if vals[0] in (None, ""):
            continue
        out.append(vals)
    return hdr, out


def read_benchmarks(spec):
    """Benchmark table with a header row naming 'Building Type', 'Building Element Category' and module
    columns (A1-A3, A4, A5, B4, C1..C4, optionally D). Returns dict rows."""
    wb = load_workbook(spec["path"], data_only=True, read_only=True)
    ws = wb[spec.get("sheet") or wb.sheetnames[0]]
    hdr, out = None, []
    for row in ws.iter_rows(values_only=True):
        cells = [str(v).strip() if v is not None else "" for v in row]
        if hdr is None:
            if "Building Type" in cells and "Building Element Category" in cells:
                hdr = cells
            continue
        d = dict(zip(hdr, row))
        if not d.get("Building Type") or not d.get("Building Element Category"):
            continue
        out.append(d)
    if hdr is None:
        raise ValueError("Benchmark sheet: header with 'Building Type' / 'Building Element Category' not found")
    return out


def bench_key(label):
    s = str(label).strip()
    if s.startswith("2.7"):
        return "2.7/2.8"
    for k in ("3", "4", "5", "8"):
        if s.startswith(k + " ") or s == k:
            return k
    return None


# --------------------------------------------------------------------------------------- helpers
def col(n):
    return get_column_letter(n)


def head(ws, row, labels, widths=None, height=45):
    for i, h in enumerate(labels, start=1):
        c = ws.cell(row, i, h)
        c.font = BOLD
        c.fill = HEAD
        c.alignment = WRAP
    ws.row_dimensions[row].height = height
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[col(i)].width = w


def title(ws, text, note):
    ws["A1"] = text
    ws["A1"].font = TITLE
    ws["A2"] = note
    ws["A2"].alignment = Alignment(wrap_text=False)


def name(wb, nm, ref):
    dn = DefinedName(nm, attr_text=ref)
    try:
        wb.defined_names[nm] = dn          # openpyxl >= 3.1
    except TypeError:
        wb.defined_names.append(dn)


# --------------------------------------------------------------------------------------- build
def build(cfg):
    header, rows = read_export(cfg["takeoff_csv"])
    lib = load_workbook(cfg["library_xlsx"])
    bench = read_benchmarks(cfg["benchmarks"])
    site = dict(A51=35.0, A52=40.0, C1=12.0)
    site.update(cfg.get("site", {}))
    params = dict(contingency=0.15, rsp=60, facade_route="Unitised curtain wall", cw_build_up="CW-UNIT-01",
                  facade_opaque_build_up="EW-SFS-BRK-01",
                  road_vehicle="RV-17PLUS", eol_vehicle="RV-17PLUS", sea_factor=0.01592,
                  eol_distances_km=[50, 50, 50], benchmark_c1="Exclude", cw_reference_a1a5=None)
    params.update(cfg.get("params", {}))

    wb = Workbook()
    wb.remove(wb.active)
    for nm in ["README", "Project", "Results", "QA", "Takeoff", "Lines", "Materials", "Layers", "Buildups",
               "Benchmarks"]:
        wb.create_sheet(nm)

    # ---- copy library reference sheets verbatim (values and formulas)
    for nm in ["Rebar_Rates", "Offsite_Params", "REF_T17_Transport", "REF_T18_Waste", "REF_T20_ServiceLife",
               "REF_T23_EoL", "REF_T28_C4", "REF_T27_D1", "REF_Vehicles"]:
        if nm not in lib.sheetnames:
            if nm == "Offsite_Params":
                raise ValueError("Library has no Offsite_Params sheet (needs library v0.8+)")
            continue
        src, dst = lib[nm], wb.create_sheet(nm)
        for row in src.iter_rows():
            for c in row:
                if c.value is not None:
                    d = dst.cell(c.row, c.column, c.value)
                    if c.has_style:
                        d.font = copy(c.font)
                        d.number_format = c.number_format
                        d.alignment = copy(c.alignment)
                        d.fill = copy(c.fill)
        for k, dim in src.column_dimensions.items():
            dst.column_dimensions[k].width = dim.width
        dst.sheet_properties.tabColor = "BFBFBF"

    lib_src = os.path.basename(cfg["library_xlsx"])
    bm_src = cfg["benchmarks"].get("source") or os.path.basename(cfg["benchmarks"]["path"])

    # =================================================================================== Materials
    mh, mats = read_sheet(lib, "Materials")
    M = wb["Materials"]
    title(M, "Materials - factors (from the library) and per-kg module factors computed for this project",
          "Columns A-V copied from %s. X onwards: formulas. Yellow = may be overridden for this project." % lib_src)
    m_first, m_last = 5, 5 + len(mats) - 1
    MR = "$%d:$%%s$%d" % (m_first, m_last)
    rng = lambda c: "Materials!$%s$%d:$%s$%d" % (c, m_first, c, m_last)   # noqa: E731
    mcols = mh[:22] + [None]
    calc_hdr = ["Life (yrs, T20)", "Site waste rate (T18)", "Road km (T17)", "Sea km (T17)", "Reuse", "Recycling",
                "Incineration", "Disposal", "T28 (kgCO2e/t)", "Project mass (kg)", "Project volume (m3)",
                "A4 total (kgCO2e)", "A4 (kgCO2e/kg)", "C2 total (kgCO2e)", "C2 (kgCO2e/kg)", "C3 (kgCO2e/kg)",
                "C4 (kgCO2e/kg)", "D (kgCO2e/kg)", "EoL C2-C4 (kgCO2e/kg)", "A1-A3 project (kgCO2e)", "In use"]
    head(M, 4, [h if h is not None else "" for h in mcols] + calc_hdr,
         [20, 34, 8, 9, 9, 10, 10, 11, 30, 7, 11, 13, 13, 13, 16, 12, 18, 10, 10, 10, 10, 24, 2] + [9] * len(calc_hdr))
    for i, m in enumerate(mats):
        r = m_first + i
        for c in range(1, 23):
            v = m[c - 1] if c - 1 < len(m) else None
            if c == 18:
                v = "=COUNTIF(Layers!$C:$C,A%d)" % r
            if isinstance(v, str) and v.startswith("=") and c != 18:
                v = None
            M.cell(r, c, v)
        for c in (6, 7, 19, 20, 21):
            M.cell(r, c).fill = INPUT
        f = {
            24: '=IFERROR(INDEX(REF_T20_ServiceLife!$D:$D,MATCH(M{r},REF_T20_ServiceLife!$A:$A,0))*1,RSP)',
            25: '=IFERROR(INDEX(REF_T18_Waste!$C:$C,MATCH(L{r},REF_T18_Waste!$A:$A,0))*1,0)',
            26: '=IFERROR(INDEX(REF_T17_Transport!$D:$D,MATCH(K{r},REF_T17_Transport!$A:$A,0))*1,0)',
            27: '=IFERROR(N(INDEX(REF_T17_Transport!$E:$E,MATCH(K{r},REF_T17_Transport!$A:$A,0))),0)',
            28: '=IFERROR(INDEX(REF_T23_EoL!$D:$D,MATCH(N{r},REF_T23_EoL!$A:$A,0))/100,0)',
            29: '=IFERROR(INDEX(REF_T23_EoL!$E:$E,MATCH(N{r},REF_T23_EoL!$A:$A,0))/100,0)',
            30: '=IFERROR(INDEX(REF_T23_EoL!$F:$F,MATCH(N{r},REF_T23_EoL!$A:$A,0))/100,0)',
            31: '=IFERROR(INDEX(REF_T23_EoL!$G:$G,MATCH(N{r},REF_T23_EoL!$A:$A,0))/100,1)',
            32: '=IFERROR(INDEX(REF_T28_C4!$C:$C,MATCH(O{r},REF_T28_C4!$A:$A,0))*1,0)',
            33: '=SUMIF(Lines!$F:$F,A{r},Lines!$O:$O)',
            34: '=IF(N(E{r})>0,AG{r}/E{r},0)',
            35: ('=IF(AG{r}=0,0,ROUNDUP(MAX(AG{r}/1000/V1_PAY,AH{r}/V1_VOL),0)*Z{r}*(V1_C1+V1_ERF*V1_C2)'
                 '+AG{r}/1000*AA{r}*SEA_F)'),
            36: '=IF(AG{r}=0,0,AI{r}/AG{r})',
            37: ('=IF(AG{r}=0,0,(ROUNDUP(MAX((AB{r}+AC{r})*AG{r}/1000/V2_PAY,(AB{r}+AC{r})*AH{r}/V2_VOL),0)*D_PROC'
                 '+ROUNDUP(MAX(AD{r}*AG{r}/1000/V2_PAY,AD{r}*AH{r}/V2_VOL),0)*D_EFW'
                 '+ROUNDUP(MAX(AE{r}*AG{r}/1000/V2_PAY,AE{r}*AH{r}/V2_VOL),0)*D_LAND)*2*V2_F50)'),
            38: '=IF(AG{r}=0,0,AK{r}/AG{r})',
            39: '=IF(S{r}<>"",S{r},(1-AE{r})*AF{r}/1000)',
            40: '=IF(T{r}<>"",T{r},AE{r}*AF{r}/1000)',
            41: '=N(U{r})',
            42: '=AL{r}+AM{r}+AN{r}',
            43: '=SUMIF(Lines!$F:$F,A{r},Lines!$Q:$Q)',
            44: '=IF(AG{r}>0,"Y","")',
        }
        for c, ftxt in f.items():
            M.cell(r, c, ftxt.format(r=r))
    M.freeze_panes = "C5"

    # =================================================================================== Layers
    lh, lays = read_sheet(lib, "Layers")
    lays.sort(key=lambda v: (str(v[0]), float(v[1] or 0)))       # contiguous per build-up, by Seq
    L = wb["Layers"]
    title(L, "Layers - Appendix M panels (from the library), quantity per ONE declared unit of the build-up",
          "Copied from %s; mass and unit conversion recomputed against this workbook's Materials." % lib_src)
    l_first, l_last = 5, 5 + len(lays) - 1
    head(L, 4, ["build_up_code", "Seq", "material_id", "Quantity", "Qty unit", "Basis / derivation",
                "Material declared unit", "Qty in material's declared unit", "Mass (kg)", "A1-A3 (kgCO2e)",
                "Biogenic (kgCO2e)", "Layer check", "Reports to RICS code (blank = build-up's)", "Assumed?",
                "Service life override (yrs)", "Site waste rate override", "Offsite fabrication waste rate (A3)"],
         [18, 5, 22, 10, 7, 50, 9, 11, 10, 10, 10, 14, 12, 8, 10, 10, 11])
    MA = rng("A")
    for i, v in enumerate(lays):
        r = l_first + i
        for c in (1, 2, 3, 4, 5, 6, 13, 14, 15, 16, 17):
            x = v[c - 1] if c - 1 < len(v) else None
            L.cell(r, c, x)
        L.cell(r, 4).fill = INPUT
        mm = 'MATCH(C{r},%s,0)' % MA
        L.cell(r, 7, ('=IFERROR(INDEX(%s,%s),"?")' % (rng("C"), mm)).format(r=r))
        L.cell(r, 8, ('=IFERROR(IF(E{r}=G{r},D{r},IF(AND(E{r}="m3",G{r}="kg"),D{r}*INDEX(%s,%s),'
                      'IF(AND(E{r}="kg",G{r}="m3"),D{r}/INDEX(%s,%s),NA()))),"")' % (rng("E"), mm, rng("E"), mm)).format(r=r))
        L.cell(r, 9, ('=IFERROR(H{r}*INDEX(%s,%s),"")' % (rng("D"), mm)).format(r=r))
        L.cell(r, 10, ('=IFERROR(IF(INDEX(%s,%s)="","",H{r}*INDEX(%s,%s)),"")' % (rng("F"), mm, rng("F"), mm)).format(r=r))
        L.cell(r, 11, ('=IFERROR(H{r}*INDEX(%s,%s),"")' % (rng("G"), mm)).format(r=r))
        L.cell(r, 12, ('=IF(COUNTIF(%s,C{r})=0,"Unknown material",IF(H{r}="","Unit mismatch",'
                       'IF(J{r}="","Factor needed",IF(COUNTIF(Buildups!$A:$A,A{r})=0,"Unknown build-up","OK"))))' % MA).format(r=r))
    L.freeze_panes = "D5"
    LA = "Layers!$A$1:$A$%d" % (l_last + SLOTS)

    # =================================================================================== Buildups
    bh, bus = read_sheet(lib, "Buildups")
    B = wb["Buildups"]
    title(B, "Build-ups - codes the take-off points to (from the library)", "Results per declared unit, recomputed from Layers.")
    b_first, b_last = 5, 5 + len(bus) - 1
    head(B, 4, ["build_up_code", "RICS code", "Description", "Declared unit", "Basis", "Version", "Status", "Provenance",
                "Layers", "Layers not OK", "Mass (kg/unit)", "A1-A3 (kgCO2e/unit)", "Library check", "Offsite (CWCT A3)"],
         [18, 8, 50, 8, 50, 7, 10, 30, 7, 8, 10, 11, 26, 9])
    off_idx = bh.index("Offsite manufactured (CWCT A3)") if "Offsite manufactured (CWCT A3)" in bh else None
    for i, v in enumerate(bus):
        r = b_first + i
        for c in range(1, 9):
            B.cell(r, c, v[c - 1])
        B.cell(r, 9, '=COUNTIF(Layers!$A:$A,A%d)' % r)
        B.cell(r, 10, '=COUNTIFS(Layers!$A:$A,A%d,Layers!$L:$L,"<>OK")' % r)
        B.cell(r, 11, '=IF(I{r}=0,"",SUMIF(Layers!$A:$A,A{r},Layers!$I:$I))'.format(r=r))
        B.cell(r, 12, '=IF(OR(I{r}=0,J{r}>0),"",SUMIF(Layers!$A:$A,A{r},Layers!$J:$J))'.format(r=r))
        B.cell(r, 13, '=IF(I{r}=0,"No layers - basis needed",IF(J{r}>0,"Incomplete - "&J{r}&" layer(s) not OK","OK"))'.format(r=r))
        B.cell(r, 14, (v[off_idx] if off_idx is not None else None) or "N")
    B.freeze_panes = "B5"
    BA, BD, BM, BN, BG = ("Buildups!$%s$%d:$%s$%d" % (c, b_first, c, b_last) for c in "ADMNG")

    # =================================================================================== Benchmarks
    K = wb["Benchmarks"]
    title(K, "Benchmarks - kgCO2e per m2 GIA for elements not taken off (RICS PS 4.5.2 method 2)",
          "Source: %s. Applied when the use class matches Project and Apply = Y." % bm_src)
    head(K, 4, ["Use class", "Element group", "Key", "A1-A3", "A4", "A5", "B4", "C1", "C2", "C3", "C4", "D",
                "Contingency already inside? (Y/N)", "Apply (Y/N)", "Applied", "Source / note"],
         [20, 34, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 12, 8, 8, 60])
    k_first = 5
    kr = 0
    for d in bench:
        key = bench_key(d["Building Element Category"])
        if key is None:
            continue
        r = k_first + kr
        kr += 1
        K.cell(r, 1, str(d["Building Type"]).strip())
        K.cell(r, 2, str(d["Building Element Category"]).strip())
        K.cell(r, 3, key)
        for c, mod in zip(range(4, 13), ["A1-A3", "A4", "A5", "B4", "C1", "C2", "C3", "C4", "D"]):
            v = d.get(mod)
            K.cell(r, c, float(v) if v not in (None, "") else 0.0)
        K.cell(r, 13, "N").fill = INPUT
        K.cell(r, 14, "Y").fill = INPUT
        K.cell(r, 15, '=IF(AND(A{r}=USE,N{r}="Y"),1,0)'.format(r=r))
        K.cell(r, 16, bm_src)
    k_last = k_first + kr - 1
    KC, KO = "Benchmarks!$C$%d:$C$%d" % (k_first, k_last), "Benchmarks!$O$%d:$O$%d" % (k_first, k_last)
    dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=False)
    dv.add("M%d:N%d" % (k_first, k_last))
    K.add_data_validation(dv)
    K.freeze_panes = "D5"

    # =================================================================================== Project
    P = wb["Project"]
    title(P, "Project inputs", "Yellow cells are inputs. Header values come from the take-off export; change them here if needed.")
    use_classes = sorted({K.cell(r, 1).value for r in range(k_first, k_last + 1)})
    gia = float(header.get("gia_m2") or 0)
    items = [
        ("Project ID", header.get("project_id", ""), "", "From export header", None),
        ("Use class", header.get("use_class", "Office"), "", "Selects the benchmark rows", "USE"),
        ("RIBA stage", int(float(header.get("riba_stage", 2))), "", "", "STAGE"),
        ("Model version", header.get("model_version", ""), "", "", None),
        ("GIA", gia, "m2", header.get("gia_source", ""), "GIA"),
        ("Existing GIA demolished", float(header.get("existing_gia_demolished_m2") or 0), "m2", "Drives A5.1", "GIA_DEMO"),
        ("Fit-out scope", header.get("fitout_scope", "Shell & core + Cat A"), "",
         "Benchmarks cover building-related items (shell & core + Cat A, London Plan Guidance). Cat B loose items excluded.", None),
        ("Reference study period", params["rsp"], "yrs", "PS 4.2", "RSP"),
        ("Contingency", params["contingency"], "", "PS Table 10 - 15% at RIBA 0-2. Applied to A-C (not D, not biogenic).", "CONT"),
        ("Facade route", params["facade_route"], "",
         "'Unitised curtain wall' sends 2.5.1 rows using the opaque facade build-up below to the curtain wall build-up, reported in 2.5.2 with the glazing (spandrels are part of the system). 'As exported' keeps the take-off split.",
         "FACADE"),
        ("Opaque facade build-up to route", params["facade_opaque_build_up"], "",
         "The take-off's opaque facade code (CONFIG build_ups.facade_opaque). Soffits and other 2.5.1 rows are not routed.", "OPQ_BU"),
        ("Curtain wall build-up", params["cw_build_up"], "", "", "CW_BU"),
        ("A5.1 rate (pre-construction demolition)", site["A51"], "kgCO2e/m2 existing GIA", "PS default", "R_A51"),
        ("A5.2 rate (construction activities)", site["A52"], "kgCO2e/m2 GIA", "PS default", "R_A52"),
        ("C1 rate (deconstruction / demolition)", site["C1"], "kgCO2e/m2 GIA", site.get("C1_note", "Lump sum"), "R_C1"),
        ("Benchmark C1 shares", params["benchmark_c1"], "",
         "Exclude = C1 only from the whole-building lump above (avoids counting C1 twice)", "BM_C1"),
        ("A4 road vehicle (REF_Vehicles mode ID)", params["road_vehicle"], "", "PS 5.1.3: average rigid HGV", "VEH_A4"),
        ("A4 sea freight factor", params["sea_factor"], "kgCO2e/t.km", "Per tonne-km; ships are not loaded as lorries", "SEA_F"),
        ("C2 vehicle (REF_Vehicles mode ID)", params["eol_vehicle"], "", "PS 5.6.3: average rigid HGV, 50% laden", "VEH_C2"),
        ("C2 distance - waste processing / recycling", params["eol_distances_km"][0], "km",
         "PS Table 26: average of the two closest facilities - PLACEHOLDER, replace per site", "D_PROC"),
        ("C2 distance - energy from waste", params["eol_distances_km"][1], "km", "PLACEHOLDER, replace per site", "D_EFW"),
        ("C2 distance - landfill", params["eol_distances_km"][2], "km", "PLACEHOLDER, replace per site", "D_LAND"),
    ]
    head(P, 4, ["", "Input", "Value", "Unit", "Note / source"], [3, 42, 24, 22, 110])
    r = 5
    for lbl, val, unit, note, nm in items:
        P.cell(r, 2, lbl)
        c = P.cell(r, 3, val)
        c.fill = INPUT
        P.cell(r, 4, unit)
        P.cell(r, 5, note)
        if nm:
            name(wb, nm, "Project!$C$%d" % r)
        if nm == "CONT":
            c.number_format = "0%"
        if nm == "USE":
            v = DataValidation(type="list", formula1='"%s"' % ",".join(use_classes))
            v.add(c.coordinate)
            P.add_data_validation(v)
        if nm == "FACADE":
            v = DataValidation(type="list", formula1='"Unitised curtain wall,As exported"')
            v.add(c.coordinate)
            P.add_data_validation(v)
        if nm == "BM_C1":
            v = DataValidation(type="list", formula1='"Exclude,Include"')
            v.add(c.coordinate)
            P.add_data_validation(v)
        r += 1
    r += 1
    P.cell(r, 2, "Derived parameters (formulas)").font = BOLD
    r += 1
    veh = lambda nm_, colx: '=INDEX(REF_Vehicles!$%s:$%s,MATCH(%s,REF_Vehicles!$A:$A,0))' % (colx, colx, nm_)  # noqa: E731
    derived = [
        ("A4 vehicle payload", veh("VEH_A4", "C"), "t", "V1_PAY"),
        ("A4 vehicle volume", veh("VEH_A4", "D"), "m3", "V1_VOL"),
        ("A4 c1 outward", veh("VEH_A4", "E"), "kgCO2e/km", "V1_C1"),
        ("A4 empty running factor", veh("VEH_A4", "F"), "", "V1_ERF"),
        ("A4 c2 return", veh("VEH_A4", "G"), "kgCO2e/km", "V1_C2"),
        ("C2 vehicle payload", veh("VEH_C2", "C"), "t", "V2_PAY"),
        ("C2 vehicle volume", veh("VEH_C2", "D"), "m3", "V2_VOL"),
        ("C2 50% laden factor", veh("VEH_C2", "H"), "kgCO2e/km", "V2_F50"),
        ("CWCT factory assembly (A3)", '=INDEX(Offsite_Params!$C:$C,MATCH("CWCT-A3-ASSEMBLY",Offsite_Params!$A:$A,0))', "kgCO2e/kg", "CWCT_ASM"),
        ("CWCT transport to fabricator (A2)", '=INDEX(Offsite_Params!$C:$C,MATCH("CWCT-A2-FAB",Offsite_Params!$A:$A,0))', "kgCO2e/kg", "CWCT_A2F"),
    ]
    for lbl, f, unit, nm in derived:
        P.cell(r, 2, lbl)
        P.cell(r, 3, f)
        P.cell(r, 4, unit)
        name(wb, nm, "Project!$C$%d" % r)
        r += 1

    # =================================================================================== Takeoff
    T = wb["Takeoff"]
    title(T, "Take-off - rows from the interchange export (schema %s)" % header.get("schema_version", "0.1"),
          "Source: %s. A-I are inputs; J onwards are formulas. Spare rows at the bottom take manual additions." % os.path.basename(cfg["takeoff_csv"]))
    t_hdr = ["element_id", "nrm_code", "build_up_code", "quantity", "unit", "method", "include", "source_layer", "notes",
             "Facade routed", "Build-up used", "RICS code used", "In library", "Declared unit", "Unit check", "Library check",
             "Active", "A1-A3 incl. offsite (kgCO2e)", "A4", "A5.3", "A1-A5 (kgCO2e)", "A1-A5 per unit", "B4", "C2-C4",
             "Status"]
    head(T, 4, t_hdr, [9, 7, 18, 11, 6, 9, 7, 20, 50, 7, 18, 8, 7, 7, 12, 22, 6, 13, 11, 11, 13, 10, 11, 11, 26])
    t_first = 5
    t_last = t_first + len(rows) + SPARE_ROWS - 1
    for i in range(len(rows) + SPARE_ROWS):
        r = t_first + i
        if i < len(rows):
            d = rows[i]
            vals = [d.get("element_id"), d.get("nrm_code"), d.get("build_up_code"), d["quantity"], d.get("unit"),
                    d.get("method"), d.get("include", "Y") or "Y", d.get("source_layer"), d.get("notes")]
            for c, v in enumerate(vals, start=1):
                T.cell(r, c, v)
        for c in range(1, 10):
            T.cell(r, c).fill = INPUT
        fx = {
            10: '=IF(AND(FACADE="Unitised curtain wall",B{r}&""="2.5.1",C{r}=OPQ_BU),1,0)',
            11: '=IF(C{r}="","",IF(J{r}=1,CW_BU,C{r}))',
            12: '=IF(C{r}="","",IF(J{r}=1,"2.5.2",B{r}&""))',
            13: '=IF(K{r}="","",IF(COUNTIF(%s,K{r})>0,"Y","N"))' % BA,
            14: '=IF(K{r}="","",IFERROR(INDEX(%s,MATCH(K{r},%s,0)),""))' % (BD, BA),
            15: '=IF(K{r}="","",IF(N{r}="","No build-up",IF(N{r}=E{r},"OK","Unit mismatch")))',
            16: '=IF(K{r}="","",IFERROR(INDEX(%s,MATCH(K{r},%s,0)),"Not in library"))' % (BM, BA),
            17: '=IF(AND(K{r}<>"",G{r}="Y",M{r}="Y",O{r}="OK"),1,0)',
            18: '=SUMIF(Lines!$A:$A,ROW(),Lines!$Q:$Q)+SUMIF(Lines!$A:$A,ROW(),Lines!$T:$T)',
            19: '=SUMIF(Lines!$A:$A,ROW(),Lines!$U:$U)',
            20: '=SUMIF(Lines!$A:$A,ROW(),Lines!$W:$W)',
            21: '=R{r}+S{r}+T{r}',
            22: '=IF(N(D{r})=0,"",U{r}/D{r})',
            23: '=SUMIF(Lines!$A:$A,ROW(),Lines!$Z:$Z)',
            24: ('=SUMIF(Lines!$A:$A,ROW(),Lines!$AA:$AA)+SUMIF(Lines!$A:$A,ROW(),Lines!$AB:$AB)'
                 '+SUMIF(Lines!$A:$A,ROW(),Lines!$AC:$AC)'),
            25: ('=IF(C{r}="","",IF(G{r}<>"Y","Excluded (include = N)",IF(M{r}="N","NOT IN LIBRARY - not counted",'
                 'IF(O{r}<>"OK","UNIT MISMATCH - not counted",IF(P{r}<>"OK","Build-up "&P{r},"OK")))))'),
        }
        for c, f in fx.items():
            T.cell(r, c, f.format(r=r))
    T.freeze_panes = "D5"
    dvt = DataValidation(type="list", formula1='"Y,N"')
    dvt.add("G%d:G%d" % (t_first, t_last))
    T.add_data_validation(dvt)

    # =================================================================================== Lines
    N = wb["Lines"]
    title(N, "Lines - each take-off row expanded into its build-up layers (do not edit)",
          "kgCO2e. One block of %d slots per Takeoff row; empty slots read 0. Layers whose element group is benchmarked are dropped (col I)." % SLOTS)
    n_hdr = ["Takeoff row", "Slot", "Build-up", "Layers row", "Valid", "material_id", "Reports to", "Group key",
             "Dropped (benchmarked)", "Active", "Qty/unit (decl.)", "Mass/unit (kg)", "Take-off qty", "Qty (decl. unit)",
             "Mass (kg)", "Materials row", "A1-A3", "Offsite flag", "Fab. waste rate", "A3 offsite (CWCT)", "A4",
             "Site waste rate", "A5.3", "Life (yrs)", "Replacements", "B4", "C2", "C3", "C4", "D", "Biogenic stored",
             "Biogenic released"]
    head(N, 4, n_hdr, [7, 5, 18, 8, 5, 20, 8, 7, 9, 6, 9, 9, 10, 11, 11, 8] + [10] * 16)
    n_first = 5
    MAcol = "Materials!$A$%d:$A$%d" % (m_first, m_last)
    mi = lambda c: "INDEX(Materials!$%s$%d:$%s$%d,P{r})" % (c, m_first, c, m_last)   # noqa: E731
    li = lambda c: "INDEX(Layers!$%s$1:$%s$%d,D{r})" % (c, c, l_last + SLOTS)         # noqa: E731
    r = n_first
    for t in range(t_first, t_last + 1):
        for k in range(1, SLOTS + 1):
            fx = {
                1: t, 2: k,
                3: '=Takeoff!K%d' % t,
                4: '=IF(C{r}="",0,IFERROR(MATCH(C{r},%s,0)+B{r}-1,0))' % LA,
                5: '=IF(D{r}=0,0,IF(%s=C{r},1,0))' % li("A"),
                6: '=IF(E{r}=1,%s,"")' % li("C"),
                7: '=IF(E{r}<>1,"",IF(%s&""="",Takeoff!L%d,%s&""))' % (li("M"), t, li("M")),
                8: '=IF(G{r}="","",IF(OR(LEFT(G{r},3)="2.7",LEFT(G{r},3)="2.8"),"2.7/2.8",LEFT(G{r},1)))',
                9: '=IF(H{r}="",0,IF(COUNTIFS(%s,H{r},%s,1)>0,1,0))' % (KC, KO),
                10: '=IF(AND(E{r}=1,Takeoff!Q%d=1,I{r}=0),1,0)' % t,
                11: '=IF(E{r}=1,N(%s),0)' % li("H"),
                12: '=IF(E{r}=1,N(%s),0)' % li("I"),
                13: '=N(Takeoff!D%d)' % t,
                14: '=J{r}*M{r}*K{r}',
                15: '=J{r}*M{r}*L{r}',
                16: '=IF(F{r}="",0,IFERROR(MATCH(F{r},%s,0),0))' % MAcol,
                17: '=IF(P{r}=0,0,N{r}*N(%s))' % mi("F"),
                18: '=IF(E{r}<>1,0,IF(IFERROR(INDEX(%s,MATCH(C{r},%s,0)),"N")="Y",1,0))' % (BN, BA),
                19: '=IF(E{r}=1,N(%s),0)' % li("Q"),
                20: '=IF(J{r}=0,0,R{r}*(O{r}*(CWCT_ASM+CWCT_A2F)+IF(S{r}>0,S{r}/(1-S{r})*(Q{r}+O{r}*CWCT_A2F),0)))',
                21: '=IF(P{r}=0,0,O{r}*%s)' % mi("AJ"),
                22: '=IF(E{r}<>1,0,IF(%s&""<>"",N(%s),IF(P{r}=0,0,%s)))' % (li("P"), li("P"), mi("Y")),
                23: '=IF(P{r}=0,0,V{r}*(Q{r}+T{r}+U{r}+O{r}*%s))' % mi("AP"),
                24: '=IF(E{r}<>1,RSP,IF(%s&""<>"",N(%s),IF(P{r}=0,RSP,%s)))' % (li("O"), li("O"), mi("X")),
                25: '=IF(OR(J{r}=0,X{r}<=0),0,MAX(0,ROUNDUP(RSP/X{r},0)-1))',
                26: '=Y{r}*(Q{r}+T{r}+U{r}+W{r})',
                27: '=IF(P{r}=0,0,O{r}*%s*(1+Y{r}))' % mi("AL"),
                28: '=IF(P{r}=0,0,O{r}*%s*(1+Y{r}))' % mi("AM"),
                29: '=IF(P{r}=0,0,O{r}*%s*(1+Y{r}))' % mi("AN"),
                30: '=IF(P{r}=0,0,O{r}*%s*(1+Y{r}))' % mi("AO"),
                31: '=IF(P{r}=0,0,N{r}*N(%s)*(1+Y{r}))' % mi("G"),
                32: '=-AE{r}',
            }
            for c, f in fx.items():
                N.cell(r, c, f.format(r=r) if isinstance(f, str) else f)
            r += 1
    n_last = r - 1
    N.freeze_panes = "C5"

    # =================================================================================== Results
    R = wb["Results"]
    title(R, "Results - whole life carbon by RICS element and module (tCO2e unless stated)",
          "RICS WLCA PS 2nd ed., RSP from Project. A-C = A1-A5 + B4 + C1-C4 (B1-B3, B5 not assessed; B6/B7 not in this version). D and biogenic are reported separately.")
    rh = ["Code", "Element", "Method", "A1-A3", "A4", "A5.1", "A5.2", "A5.3", "A1-A5", "B4", "C1", "C2", "C3", "C4",
          "A-C", "D (memo)", "Biogenic stored (memo)", "A1-A5 kgCO2e/m2 GIA", "A-C kgCO2e/m2 GIA"]
    head(R, 12, rh, [8, 46, 12] + [10] * 14 + [11, 11])
    NR = lambda c: "Lines!$%s$%d:$%s$%d" % (c, n_first, c, n_last)     # noqa: E731
    line_cols = {"A1-A3": ["Q", "T"], "A4": ["U"], "A5.3": ["W"], "B4": ["Z"], "C2": ["AA"], "C3": ["AB"], "C4": ["AC"],
                 "D": ["AD"], "Bio": ["AE"]}
    mod_col = {m: 4 + i for i, m in enumerate(["A1-A3", "A4", "A5.1", "A5.2", "A5.3", "A1-A5", "B4", "C1", "C2", "C3",
                                                "C4", "A-C", "D", "Bio"])}

    def row_formulas(rr):
        R.cell(rr, mod_col["A1-A5"], "=SUM(D{r}:H{r})".format(r=rr))
        R.cell(rr, mod_col["A-C"], "=I{r}+SUM(J{r}:N{r})".format(r=rr))
        R.cell(rr, 18, "=IF(GIA>0,I{r}*1000/GIA,0)".format(r=rr))
        R.cell(rr, 19, "=IF(GIA>0,O{r}*1000/GIA,0)".format(r=rr))
        for c in range(4, 20):
            R.cell(rr, c).number_format = "#,##0.0"

    rr = 13
    R.cell(rr, 1, "Modelled (take-off x build-up library)").font = BOLD
    for c in range(1, 20):
        R.cell(rr, c).fill = SECTION
    rr += 1
    mod_first = rr
    method_rows = []
    for code, label, kind in MODELLED_ROWS:
        crit = '"%s"' % code if kind == "x" else '"%s*"' % code
        R.cell(rr, 1, code)
        R.cell(rr, 2, label)
        method_rows.append((rr, crit))
        for m, cols in line_cols.items():
            parts = ["SUMIFS(%s,%s,%s)" % (NR(cc), NR("G"), crit) for cc in cols]
            R.cell(rr, mod_col[m], "=(" + "+".join(parts) + ")/1000")
        row_formulas(rr)
        rr += 1
    mod_last = rr - 1
    R.cell(rr, 1, "Benchmarked (kgCO2e/m2 GIA x GIA)").font = BOLD
    for c in range(1, 20):
        R.cell(rr, c).fill = SECTION
    rr += 1
    bm_first = rr
    KR = lambda c: "Benchmarks!$%s$%d:$%s$%d" % (c, k_first, c, k_last)    # noqa: E731
    for key, label in BENCH_KEYS:
        R.cell(rr, 1, key)
        R.cell(rr, 2, label)
        R.cell(rr, 3, '=IF(COUNTIFS(%s,"%s",%s,1)>0,"Benchmark","")' % (KR("C"), key, KR("O")))
        s = lambda c: "SUMIFS(%s,%s,\"%s\",%s,1)*GIA/1000" % (KR(c), KR("C"), key, KR("O"))   # noqa: E731
        R.cell(rr, mod_col["A1-A3"], "=" + s("D"))
        R.cell(rr, mod_col["A4"], "=" + s("E"))
        R.cell(rr, mod_col["A5.3"], "=" + s("F"))
        R.cell(rr, mod_col["B4"], "=" + s("G"))
        R.cell(rr, mod_col["C1"], '=IF(BM_C1="Include",1,0)*' + s("H"))
        R.cell(rr, mod_col["C2"], "=" + s("I"))
        R.cell(rr, mod_col["C3"], "=" + s("J"))
        R.cell(rr, mod_col["C4"], "=" + s("K"))
        R.cell(rr, mod_col["D"], "=" + s("L"))
        row_formulas(rr)
        rr += 1
    bm_last = rr - 1
    R.cell(rr, 1, "Site (whole building, PS defaults)").font = BOLD
    for c in range(1, 20):
        R.cell(rr, c).fill = SECTION
    rr += 1
    site_first = rr
    for code, label, mod, f in [("A5.1", "Pre-construction demolition (existing GIA x rate)", "A5.1", "=GIA_DEMO*R_A51/1000"),
                                ("A5.2", "Construction site activities (GIA x rate)", "A5.2", "=GIA*R_A52/1000"),
                                ("C1", "Deconstruction / demolition at end of life (GIA x rate)", "C1", "=GIA*R_C1/1000")]:
        R.cell(rr, 1, code)
        R.cell(rr, 2, label)
        R.cell(rr, 3, "Site lump")
        R.cell(rr, mod_col[mod], f)
        row_formulas(rr)
        rr += 1
    site_last = rr - 1
    rr += 1
    sub = rr
    R.cell(rr, 2, "Subtotal").font = BOLD
    for c in range(4, 18):
        L_ = col(c)
        R.cell(rr, c, "=SUM({l}{a}:{l}{b})".format(l=L_, a=mod_first, b=site_last))
    row_formulas(rr)
    rr += 1
    cont = rr
    R.cell(rr, 2, "Contingency (PS Table 10)")
    R.cell(rr, 3, "=CONT")
    R.cell(rr, 3).number_format = "0%"
    for c in range(4, 16):
        if c in (mod_col["A1-A5"], mod_col["A-C"]):
            continue
        R.cell(rr, c, "={l}{s}*CONT".format(l=col(c), s=sub))
    row_formulas(rr)
    rr += 1
    tot = rr
    R.cell(rr, 2, "TOTAL incl. contingency").font = BOLD
    for c in range(4, 18):
        R.cell(rr, c, "={l}{a}+{l}{b}".format(l=col(c), a=sub, b=cont))
    row_formulas(rr)
    for c in range(1, 20):
        R.cell(rr, c).fill = TOTAL
        R.cell(rr, c).font = BOLD

    # headline block
    R["A4"] = "Headline (incl. contingency)"
    R["A4"].font = BOLD
    hl = [("Upfront carbon A1-A5", "=R%d" % tot, "kgCO2e/m2 GIA"),
          ("Embodied carbon A-C (excl. B6/B7)", "=S%d" % tot, "kgCO2e/m2 GIA"),
          ("A1-A5 total", "=I%d" % tot, "tCO2e"),
          ("Modelled share of A1-A5 (before contingency)", "=IF(I%d=0,0,SUM(I%d:I%d)/I%d)" % (sub, mod_first, mod_last, sub), ""),
          ("Benchmarked share of A1-A5", "=IF(I%d=0,0,SUM(I%d:I%d)/I%d)" % (sub, bm_first, bm_last, sub), ""),
          ("Module D (memo, not in totals)", "=IF(GIA>0,P%d*1000/GIA,0)" % sub, "kgCO2e/m2 GIA"),
          ("QA flags open", "=QA!C4", "see QA")]
    for i, (lbl, f, unit) in enumerate(hl):
        R.cell(5 + i, 1, lbl)
        c = R.cell(5 + i, 3, f)
        c.font = BOLD
        c.number_format = "0%" if "share" in lbl else "#,##0"
        R.cell(5 + i, 4, unit)
    R.freeze_panes = "D13"

    # =================================================================================== QA
    Q = wb["QA"]
    title(Q, "QA - checks on this assessment", "FLAG = must be resolved or justified before issue. INFO = read and confirm.")
    Q["A4"] = "Flags open:"
    Q["A4"].font = BOLD
    head(Q, 6, ["#", "Check", "Result", "Status", "What to do"], [5, 60, 14, 9, 90])
    TR = lambda c: "Takeoff!$%s$%d:$%s$%d" % (c, t_first, c, t_last)    # noqa: E731
    MR_ = lambda c: "Materials!$%s$%d:$%s$%d" % (c, m_first, c, m_last)  # noqa: E731
    cw_ref = params.get("cw_reference_a1a5")
    cw_sum = ('SUMPRODUCT((%s=CW_BU)*(%s+%s+%s+%s))' % (NR("C"), NR("Q"), NR("T"), NR("U"), NR("W")))
    cw_qty = 'SUMIFS(%s,%s,CW_BU,%s,1)' % (TR("D"), TR("K"), TR("Q"))
    checks = [
        ("GIA entered and > 0", "=GIA", '=IF(N(C{r})>0,"OK","FLAG")', "Enter GIA on Project (from the area schedule or the take-off)."),
        ("Take-off rows whose build-up is not in the library (not counted)", '=COUNTIF(%s,"N")' % TR("M"),
         '=IF(C{r}=0,"OK","FLAG")', "Add the build-up to the library (owner) or change the code on the row. These quantities are currently missing from the result."),
        ("Take-off rows with a unit that differs from the build-up's declared unit (not counted)",
         '=COUNTIF(%s,"Unit mismatch")' % TR("O"), '=IF(C{r}=0,"OK","FLAG")', "Fix the export unit or the build-up."),
        ("Take-off rows using an incomplete build-up (layer missing a factor)",
         '=SUMPRODUCT((%s<>"")*(%s<>"OK")*(%s="Y"))' % (TR("K"), TR("P"), TR("M")),
         '=IF(C{r}=0,"OK","FLAG")', "Layers without a factor count as zero. Add the factor in the library."),
        ("Materials in use with no A1-A3 factor", '=SUMPRODUCT((%s>0)*(%s=""))' % (MR_("AG"), MR_("F")),
         '=IF(C{r}=0,"OK","FLAG")', "See Materials column F for rows with project mass in AG."),
        ("Materials in use with status CHECK", '=COUNTIFS(%s,"Y",%s,"CHECK")' % (MR_("AR"), MR_("P")),
         '=IF(C{r}=0,"OK","INFO")', "Usable, but provenance or value still to confirm (library owner)."),
        ("DRAFT build-ups in use", '=SUMPRODUCT((%s=1)*(COUNTIFS(%s,%s,%s,"DRAFT")>0))' % (TR("Q"), BA, TR("K"), BG),
         '=IF(C{r}=0,"OK","INFO")', "Expected before library v1.0. Only RELEASED build-ups should be used for issue."),
        ("Layers dropped because their element group is benchmarked", '=SUMPRODUCT((%s=1)*(%s=1))' % (NR("E"), NR("I")),
         '=IF(C{r}=0,"OK","INFO")', "Avoids double counting (BR-14 one method per element). Check the benchmark covers them."),
        ("Take-off rows excluded by include = N", '=COUNTIF(%s,"N")' % TR("G"), '=IF(C{r}=0,"OK","INFO")', "Confirm the exclusions are intended."),
        ("Opaque facade rows routed to the curtain wall build-up", '=SUM(%s)' % TR("J"), '=IF(C{r}=0,"OK","INFO")',
         "Facade route on Project. Whole envelope is reported in 2.5.2."),
        ("Curtain wall A1-A5 per m2 facade vs reference (kgCO2e/m2)",
         ('=IF(%s=0,"",%s/%s)' % (cw_qty, cw_sum, cw_qty)),
         ('=IF(C{r}="","INFO",IF(ABS(C{r}/%s-1)<=0.05,"OK","FLAG"))' % cw_ref) if cw_ref else '="INFO"',
         ("Reference %s kgCO2e/m2 FSA (ETPP-28 EWS-04A, CWCT). Within 5%% = OK. Differences come from A4 vehicles and Table 18 site waste." % cw_ref)
         if cw_ref else "No reference value configured."),
        ("Contingency at RIBA 0-2 at least 15%", "=CONT", '=IF(AND(STAGE<=2,CONT<0.15),"FLAG","OK")', "PS Table 10."),
        ("Scope elements with neither take-off nor benchmark (GAPS)", None, '=IF(C{r}=0,"OK","FLAG")',
         "RICS PS 4.4.1: all in-scope elements are included at every stage. Add a quantity, a benchmark, or mark the element not applicable in the coverage table below."),
    ]
    r = 7
    gap_row = None
    for i, (lbl, res, st, todo) in enumerate(checks, start=1):
        Q.cell(r, 1, i)
        Q.cell(r, 2, lbl)
        if res is not None:
            Q.cell(r, 3, res)
        else:
            gap_row = r
        Q.cell(r, 4, st.format(r=r))
        Q.cell(r, 5, todo).alignment = WRAP
        Q.cell(r, 3).number_format = "#,##0.0"
        r += 1
    q_last = r - 1
    Q["C4"] = '=COUNTIF(D7:D%d,"FLAG")' % q_last
    Q["C4"].font = Font(bold=True, color="C00000")
    r += 1
    Q.cell(r, 1, "Scope coverage").font = BOLD
    r += 1
    head(Q, r, ["Code", "Element", "Expected? (Y/N)", "Modelled (kgCO2e)", "Benchmarked", "Status"], None, 30)
    r += 1
    cov_first = r
    for code, label, exp in COVERAGE:
        Q.cell(r, 1, code)
        Q.cell(r, 2, label)
        Q.cell(r, 3, '=IF(GIA_DEMO>0,"Y","N")' if exp == "DEMO" else exp).fill = INPUT
        crit = '"%s"' % code if code.count(".") >= 1 and code not in ("2.4",) else '"%s*"' % code
        if code in ("2.4",):
            crit = '"2.4*"'
        Q.cell(r, 4, "=SUMIFS(%s,%s,%s)+SUMIFS(%s,%s,%s)" % (NR("Q"), NR("G"), crit, NR("T"), NR("G"), crit))
        Q.cell(r, 4).number_format = "#,##0"
        key = "2.7/2.8" if code in ("2.7", "2.8") else (code if code in ("3", "4", "5", "8") else "")
        Q.cell(r, 5, '=IF(COUNTIFS(%s,"%s",%s,1)>0,"Y","")' % (KR("C"), key, KR("O")) if key else "")
        Q.cell(r, 6, '=IF(C{r}<>"Y","n/a",IF(D{r}>0,"Modelled",IF(E{r}="Y","Benchmark","GAP")))'.format(r=r))
        r += 1
    cov_last = r - 1
    # Results method column: Modelled when lines report there, else the QA coverage status (GAP shows up red)
    for rr_, crit_ in method_rows:
        cs = 'INDEX(QA!$F${a}:$F${b},MATCH(A{r}&"",QA!$A${a}:$A${b},0))'
        R.cell(rr_, 3, ('=IF(COUNTIFS({g},{c},{j},1)>0,"Modelled",IFERROR(IF(' + cs + '="Benchmark","see benchmark",'
                        + cs + '),""))').format(r=rr_, g=NR("G"), c=crit_, j=NR("J"),
                                                                       a=cov_first, b=cov_last))
    R.conditional_formatting.add("C%d:C%d" % (mod_first, mod_last), CellIsRule(operator="equal", formula=['"GAP"'], fill=RED))
    Q.cell(gap_row, 3, '=COUNTIF(F%d:F%d,"GAP")' % (cov_first, cov_last))
    for rng_, rules in (("D7:D%d" % q_last, [("OK", GREEN), ("INFO", AMBER), ("FLAG", RED)]),
                        ("F%d:F%d" % (cov_first, cov_last), [("Modelled", GREEN), ("Benchmark", GREEN), ("GAP", RED)])):
        for txt, fill in rules:
            Q.conditional_formatting.add(rng_, CellIsRule(operator="equal", formula=['"%s"' % txt], fill=fill))
    T.conditional_formatting.add("Y%d:Y%d" % (t_first, t_last),
                                 FormulaRule(formula=['AND(Y%d<>"",Y%d<>"OK")' % (t_first, t_first)], fill=AMBER))

    # =================================================================================== README
    D = wb["README"]
    D.column_dimensions["A"].width = 26
    D.column_dimensions["B"].width = 130
    D["A1"] = "WLCA calculation workbook v%s - %s" % (VERSION, header.get("project_id", ""))
    D["A1"].font = TITLE
    D["A2"] = "Generated by carbon/calc/wlca_calc_template.py (AI-drafted - review before trusting). Regenerate when the take-off export changes."
    readme = [
        ("Inputs", "Take-off: %s\nLibrary: %s\nBenchmarks: %s" % (os.path.basename(cfg["takeoff_csv"]), lib_src, bm_src)),
        ("Standard", "RICS Whole life carbon assessment for the built environment, 2nd ed. (PS). RSP 60 years. Modules A1-A5, B4, C1-C4; D and biogenic carbon reported separately. B1-B3, B5, B6, B7 not in this version."),
        ("How to use", "1 Check Project (GIA, use class, stage, facade route).\n2 Read QA: every FLAG must be fixed or justified.\n3 Results: headline per m2 GIA and the element x module table.\n"
                       "Change factors or layer quantities on Materials / Layers only for project-specific overrides; library-wide changes go to the library owner."),
        ("Sheets", "Project inputs - Results - QA - Takeoff (export rows + status) - Lines (row x layer calculation) - Materials (factors + per-kg A4/C2-C4/D) - "
                   "Layers / Buildups (library snapshot) - Benchmarks - Rebar_Rates, Offsite_Params, REF_* (library reference tables)."),
        ("A1-A3", "Quantity x factor per material layer (GWP fossil + LULUC; biogenic separate). Offsite-manufactured build-ups (CWCT): + factory assembly and transport to fabricator per kg, "
                  "+ fabrication waste WR/(1-WR) x (A1-A3 + A2), reported in A3 (PS 5.1.4: offsite manufacturing waste belongs in A1-A3)."),
        ("A4", "Per material: lorry loads = ROUNDUP(max(mass/payload, volume/capacity)) x Table 17 road km x (c1 + empty running x c2), plus sea km x tonnes x sea factor. "
               "Spread over the material's project mass. DEFRA factors already include the return leg, so the empty running factor is 1.0 (see REF_T17_Transport)."),
        ("A5", "A5.1 = existing GIA demolished x rate; A5.2 = GIA x rate (PS defaults). A5.3 = Table 18 waste rate x (A1-A3 + A3 offsite + A4 + C2-C4 of the wasted material) (PS 5.1.4). "
               "A layer may carry its own site waste rate (e.g. unitised curtain wall). A5.4 not assessed."),
        ("B4", "Replacements = ROUNDUP(RSP / life) - 1 (PS 5.2.4: whole replacements, rounded up). Life = layer override, else Table 20 by material. "
               "B4 = replacements x (A1-A3 + A3 offsite + A4 + A5.3). End of life of replaced items is counted in C2-C4 (x (1 + replacements))."),
        ("C1-C4", "C1 = GIA x lump rate. C2 = lorry loads to processing / EfW / landfill (Table 26 distances, 50% laden). C3 / C4: PS default - Table 23 route x Table 28 landfill factor "
                  "(PS 5.6.4: landfill emissions when processing data is absent) - unless the library gives an override."),
        ("D", "Memo only. Per-kg values where the library gives one (metals); otherwise 0."),
        ("Benchmarks", "Elements not taken off use kgCO2e/m2 GIA by use class (PS 4.5.2 method 2). Benchmark A5 is reported in A5.3. Modelled layers in a benchmarked group are dropped (no double counting)."),
        ("Contingency", "PS Table 10 percentage applied to A-C (not D, not biogenic) as a separate row."),
    ]
    for i, (k, v) in enumerate(readme):
        D.cell(4 + i, 1, k).font = BOLD
        D.cell(4 + i, 2, v).alignment = WRAP
        D.cell(4 + i, 1).alignment = WRAP

    for ws in wb.worksheets:
        ws.sheet_view.zoomScale = 90
    wb["Results"].sheet_properties.tabColor = "70AD47"
    wb["QA"].sheet_properties.tabColor = "C00000"
    wb["Project"].sheet_properties.tabColor = "FFC000"
    wb.active = wb.sheetnames.index("Results")
    wb.calculation.fullCalcOnLoad = True        # no cached values from openpyxl: Excel calculates on open
    return wb


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cfg = json.load(open(argv[1], encoding="utf-8"))
    wb = build(cfg)
    out = cfg["out"]
    wb.save(out)
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
