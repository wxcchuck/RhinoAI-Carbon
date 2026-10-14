"""Shared fixtures for the WLCA take-off tests. Drafted by an AI agent (Claude) - review before trusting.

The test building is INVENTED (no project data in this public repo):

  level  use      AOD    FTF   GEA    GIA    NIA
  B2     Plant   -9.00   4.50  1200   1100   -
  B1     Plant   -4.50   4.50  1200   1100   -
  0      Lobby    0.00   4.50  1000    960   600
  1..10  Office   4.50+  3.75  1100   1060   800   (L1 overhangs L0 by 100 m2)
  11     Office  42.00   3.75   800    770   560   (setback)
  12     Plant   45.75   5.00   300    280   -
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "takeoff"))


def test_levels():
    lv = [("B2", "Plant", -9.0, 4.5, 1200, 1100, None),
          ("B1", "Plant", -4.5, 4.5, 1200, 1100, None),
          ("0", "Lobby", 0.0, 4.5, 1000, 960, 600)]
    z = 4.5
    for i in range(1, 11):
        lv.append((str(i), "Office", z, 3.75, 1100, 1060, 800))
        z += 3.75
    lv.append(("11", "Office", z, 3.75, 800, 770, 560)); z += 3.75
    lv.append(("12", "Plant", z, 5.0, 300, 280, None))
    return lv


def write_schedule(path, with_aod=True, title_rows=True):
    """Write the test schedule laid out like a practice area schedule: titles, header, units row,
    levels listed top-down, then a TOTAL row."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Office"
    r = 1
    if title_rows:
        ws.cell(1, 2, "Test Tower"); ws.cell(2, 2, "Development Area Summary"); ws.cell(3, 2, "2026.10.14")
        r = 5
    hdr = ["Level", "Use"] + (["AOD"] if with_aod else []) + ["Floor to Floor", "GEA", "GIA", "NIA "]
    for c, h in enumerate(hdr, start=2):
        ws.cell(r, c, h)
    nia_col = 2 + len(hdr) - 1
    ws.cell(r + 1, nia_col, "Total")                     # NIA sub-header like a real schedule
    r += 2
    ws.cell(r, 2 + (3 if with_aod else 2), "m")          # units row (no level name -> skipped)
    r += 1
    for name, use, aod, ftf, gea, gia, nia in reversed(test_levels()):
        vals = [name, use] + ([aod] if with_aod else []) + [ftf, gea, gia, nia]
        for c, v in enumerate(vals, start=2):
            if v is not None:
                ws.cell(r, c, float(v) if isinstance(v, (int, float)) else v)
        r += 1
    ws.cell(r, 5, "TOTAL"); ws.cell(r, 6 if with_aod else 5, 99999.0)   # level column empty -> stops parsing
    wb.save(path)
    return path


@pytest.fixture
def schedule_xlsx(tmp_path):
    return write_schedule(str(tmp_path / "schedule.xlsx"))


@pytest.fixture
def schedule(schedule_xlsx):
    import wlca_core as core
    w = []
    lv = core.parse_area_schedule({"path": schedule_xlsx, "sheet": "Office"}, w)
    assert w == []
    return lv


@pytest.fixture
def defaults():
    """The CONFIG blocks from the Rhino wrapper, read without importing Rhino."""
    import ast
    src = open(os.path.join(os.path.dirname(__file__), "..", "takeoff", "wlca_massing_takeoff.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "CONFIG":
            return ast.literal_eval(node.value)
    raise AssertionError("CONFIG not found")
