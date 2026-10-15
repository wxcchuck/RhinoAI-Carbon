"""Pilot regression on real project data, kept OUT of this public repo.

Drafted by an AI agent (Claude) - review before trusting.

Set WLCA_PILOT_DIR to a private folder containing pilot.json:
  {
    "schedule": {"file": "<area schedule>.xlsx", "sheet": "Office"},
    "plan_json": "<plan extract>.json",
    "ground": ["0", <ground perimeter m>, <ground GEA m2>],     # from the Rhino massing
    "structure": {...}, "substructure": {...}, "stairs": {...}, # optional CONFIG overrides
    "expected": [[rics_code, build_up_key, quantity, unit], ...]   # hand-checked values
  }
Without WLCA_PILOT_DIR the test is skipped.
"""
import json
import os

import pytest

import wlca_core as core

PILOT = os.environ.get("WLCA_PILOT_DIR")
pytestmark = pytest.mark.skipif(not PILOT, reason="WLCA_PILOT_DIR not set (private pilot data)")


def test_pilot_quantities_match_hand_checked_values(defaults):
    spec = json.load(open(os.path.join(PILOT, "pilot.json"), encoding="utf-8"))
    w = []
    sched = core.parse_area_schedule({"path": os.path.join(PILOT, spec["schedule"]["file"]),
                                      "sheet": spec["schedule"]["sheet"]}, w)
    hz, _ = core.schedule_horizontals(sched)
    S = dict(defaults["structure"], **spec.get("structure", {}))
    SUB = {k: (dict(v) if isinstance(v, dict) else v) for k, v in defaults["substructure"].items()}
    for k, v in spec.get("substructure", {}).items():
        SUB[k].update(v)
    plan = json.load(open(os.path.join(PILOT, spec["plan_json"]), encoding="utf-8")) if spec.get("plan_json") else None
    lv_all = [(lv["name"], lv["ftf"], lv["gea"], lv["gia"], lv["nia"]) for lv in sched]
    st, info = core.structure_rows(lv_all, plan, S, "Derived", w)
    sub, _ = core.substructure_rows(lv_all, core.ground_index(sched), True, tuple(spec["ground"]), sched[0]["gea"],
                                    info["columns_by_level"], info["core_area_m2"], info["core_area_source"],
                                    SUB, "Derived", w)
    stairs = core.stair_rows(lv_all, info["typical_level"], plan, dict(defaults["stairs"], **spec.get("stairs", {})), "Derived", w)
    got = [(k, round(v, 1)) for k, v in hz.items() if v > 0.01] + [(r[1], round(r[2], 1)) for r in st + sub + stairs]
    exp = [(e[1], e[2]) for e in spec["expected"]]
    assert sorted(got) == sorted(exp)
