"""Stair grouping (plan extractor v0.2) on invented tread rectangles. Drafted by an AI agent (Claude) - review before trusting.

Two dog-leg stairs: each two flights of 11 treads (0.25 m going x 1.25 m wide), side by side with a
0.10 m gap; the stairs are 10 m apart. Decoys: three equal rectangles in a row (below the minimum
flight), a 0.3 x 1.8 m threshold on its own, and a 0.1 m wide strip (too narrow for a tread).
"""
import wlca_plan_extract as px


def _flight(x0, y0, n=11, going=0.25, width=1.25):
    return [(x0 + i * going, y0, x0 + (i + 1) * going, y0 + width) for i in range(n)]


def test_group_stairs_counts_dogleg_stairs():
    rects = []
    for sx in (0.0, 10.0):
        rects += _flight(sx, 0.0) + _flight(sx + 0.25, 1.35)
    rects += [(20 + i * 0.25, 0, 20.25 + i * 0.25, 1.25) for i in range(3)]      # 3 in a row: not a flight
    rects += [(30, 0, 30.3, 1.8), (40, 0, 40.1, 1.25)]                          # threshold, thin strip
    stairs = px.group_stairs(rects)
    assert len(stairs) == 2
    for st in stairs:
        assert [f["treads"] for f in st["flights"]] == [11, 11]
        for f in st["flights"]:
            assert abs(f["width"] - 1.25) < 1e-6 and abs(f["going"] - 0.25) < 1e-6


def test_group_stairs_horizontal_flights_and_duplicates():
    rects = [(0, i * 0.28, 1.1, (i + 1) * 0.28) for i in range(9)]
    rects += rects[:4]                                                       # duplicated items (PDF often repeats)
    stairs = px.group_stairs(rects)
    assert len(stairs) == 1 and stairs[0]["flights"][0]["treads"] == 9
    assert abs(stairs[0]["flights"][0]["going"] - 0.28) < 1e-6
