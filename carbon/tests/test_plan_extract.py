"""Plan extractor test on a synthetic vector PDF. Drafted by an AI agent (Claude) - review before trusting.

Drawn at 1:100: a 10 x 8 m core with 0.25 m walls (outer + inner outline, wall pen 0.72 pt), six
0.6 m columns in the same pen, plus decoys that must be ignored: a column-sized circle in a thinner
pen, a 0.2 m circle (below the size range) and a column-sized circle inside the core window.
Hand values: wall centreline = (outer 36 m + inner 34 m) / 2 = 35 m; plan area 80 - 71.25 = 8.75 m2;
mean thickness 8.75 / 35 = 0.25 m.
"""
import json
import os

import pytest

pymupdf = pytest.importorskip("pymupdf")
pytest.importorskip("shapely")
pytest.importorskip("matplotlib")

import wlca_plan_extract as px  # noqa: E402

M = 72 / 25.4 * 10            # pt per metre at 1:100
PEN = 0.72


def _pdf(path):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    x0, y0 = 100.0, 100.0
    page.draw_rect(pymupdf.Rect(x0, y0, x0 + 10 * M, y0 + 8 * M), color=(0, 0, 0), width=PEN)
    t = 0.25 * M
    page.draw_rect(pymupdf.Rect(x0 + t, y0 + t, x0 + 10 * M - t, y0 + 8 * M - t), color=(0, 0, 0), width=PEN)
    for i in range(6):                                            # columns, right of the core
        c = pymupdf.Point(x0 + 13 * M + (i % 3) * 6 * M, y0 + 2 * M + (i // 3) * 6 * M)
        page.draw_circle(c, 0.3 * M, color=(0, 0, 0), width=PEN)
    page.draw_circle(pymupdf.Point(x0 + 13 * M, y0 + 12 * M), 0.3 * M, color=(0, 0, 0), width=0.36)   # thin pen
    page.draw_circle(pymupdf.Point(x0 + 19 * M, y0 + 12 * M), 0.1 * M, color=(0, 0, 0), width=PEN)   # too small
    page.draw_circle(pymupdf.Point(x0 + 5 * M, y0 + 4 * M), 0.3 * M, color=(0, 0, 0), width=PEN)     # inside core
    doc.save(path)
    return x0, y0


def test_plan_extract_measures_core_walls_and_columns(tmp_path):
    pdf = str(tmp_path / "plan.pdf")
    x0, y0 = _pdf(pdf)
    mm = 25.4 / 72
    cfg = dict(px.CONFIG)
    cfg.update(pdf=pdf, scale=100, out_dir=str(tmp_path), stem="t",
               core_windows_mm=[[(x0 - 10) * mm, (y0 - 10) * mm, (x0 + 10 * M + 10) * mm, (y0 + 8 * M + 10) * mm]],
               plate_window_mm=[5, 5, 290, 205])
    res, paths = px.extract(cfg)
    core = res["core"]
    assert res["wall_pen_width_pt"] == PEN
    assert core["wall_length_m_per_floor"] == pytest.approx(35.0, abs=0.2)
    assert core["wall_plan_area_m2_per_floor"] == pytest.approx(8.75, abs=0.1)
    assert core["mean_thickness_m"] == pytest.approx(0.25, abs=0.01)
    cols = res["columns"]
    assert cols["count_per_floor"] == 6
    assert cols["size_m"] == pytest.approx(0.6, abs=0.01)
    for p in paths:
        assert os.path.exists(p)
    assert json.load(open(paths[0]))["columns"]["count_per_floor"] == 6
