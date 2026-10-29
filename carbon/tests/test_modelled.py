"""Detailed-model take-off rules (wlca_modelled.py) on INVENTED layers, library and figures.
Drafted by an AI agent (Claude) - review before trusting."""
import pytest

import wlca_modelled as wm
import wlca_state as ws

LIB = {
    "SLAB-M3": {"unit": "m3", "rics": "2.2.1", "desc": "RC slab per m3"},
    "COL-M3": {"unit": "m3", "rics": "2.1.1", "desc": "RC column per m3"},
    "BEAM-M3": {"unit": "m3", "rics": "2.1.2", "desc": "RC beam per m3"},
    "WALL-A": {"unit": "m2", "rics": "2.5.1", "desc": "Wall A"},
    "WALL-B": {"unit": "m2", "rics": "2.5.1", "desc": "Wall B"},
    "WIN": {"unit": "m2", "rics": "2.6", "desc": "Window"},
    "CW": {"unit": "m2", "rics": "2.5.2", "desc": "Curtain wall"},
    "OPQ": {"unit": "m2", "rics": "2.5.1", "desc": "Opaque"},
    "ROOF": {"unit": "m2", "rics": "2.5.3", "desc": "Roof"},
    "SUB": {"unit": "m2", "rics": "1.2.1", "desc": "Sub-base"},
}
B = {"pile": "PILE", "cap_raft": "CAP", "core_wall": "CORE", "column": "COLD", "edge_beam": "EB", "soffit_finish": "SOF",
     "louvre": "LOUV", "door_ext": "DOOR", "facade_glazed": "CW", "facade_opaque": "OPQ", "upper_floor": "FLAT",
     "roof_slab": "FLAT", "lowest_slab": "GF", "roof_finish": "ROOF"}
PATTERNS = [
    {"pattern": "*steel*frame*", "measure": "ignore", "note": "in the window build-up"},
    {"pattern": "*frame*", "rics": "2.1.1", "measure": "volume_v", "build_up": "COL-M3", "replaces": "columns"},
    {"pattern": "*frame*", "rics": "2.1.2", "measure": "volume_h", "build_up": "BEAM-M3", "replaces": "beams"},
    {"pattern": "*slab*", "rics": "2.2.1", "measure": "volume", "build_up": "SLAB-M3"},
    {"pattern": "*glass*", "rics": "2.6", "measure": "share", "build_up": "WIN", "factor": 1.25},
    {"pattern": "*brick*", "rics": "2.5.1", "measure": "share", "build_up": "WALL-A"},
]


def derived():
    def r(eid, code, bu, q, unit="m2"):
        return {"project_id": "T", "element_id": eid, "nrm_code": code, "build_up_code": bu, "quantity": str(q), "unit": unit,
                "method": "Derived", "stage": "2", "model_version": "A", "author": "XX", "source_layer": "M", "include": "Y", "notes": ""}
    return [r("MS-1", "2.2.1", "FLAT", 9000), r("MS-2", "2.5.1", "OPQ", 600), r("MS-3", "2.5.2", "CW", 400),
            r("MS-4", "2.5.1", "SOF", 50), r("MS-5", "2.1.1", "CORE", 800), r("MS-6", "2.1.1", "COLD", 300, "m"),
            r("MS-7", "2.1.2", "EB", 500, "m"), r("MS-8", "2.6", "LOUV", 30), r("MS-9", "2.6", "DOOR", 20),
            r("MS-10", "1.1", "PILE", 900, "m3"), r("MS-11", "2.5.3", "ROOF", 1000)]


def stats(**k):
    s = {"n": 1, "open": 0, "vol": 0.0, "vol_v": 0.0, "vol_h": 0.0, "plan": 0.0, "face": 0.0}
    s.update(k)
    return s


def test_rics_layer_names():
    assert wm.parse_rics_layer("RICS_2.2.1_Slabs_SLAB-M3") == ("2.2.1", "SLAB-M3")
    assert wm.parse_rics_layer("RICS_3_Internal Finishes_Floor Finishes_Carpet 1") == ("3", "Carpet 1")
    assert wm.parse_rics_layer("Slabs") is None
    r = wm.rules_from_layer_name("STR::RICS_2.2.1_Slabs_SLAB-M3", LIB)
    assert r[0]["measure"] == "volume" and r[0]["build_up"] == "SLAB-M3" and r[0]["replaces"] == "floors"
    r = wm.rules_from_layer_name("STR::RICS_3_Internal Finishes_Carpet 1", LIB)       # finishes: on benchmarks
    assert r[0]["measure"] == "ignore" and "benchmarks" in r[0]["note"]
    r = wm.rules_from_layer_name("STR::RICS_2.5.1_Wall_Unknown", LIB)                 # no build-up code: ignored, flagged
    assert r[0]["measure"] == "ignore" and "choose one" in r[0]["note"]
    assert wm.measure_for("WALL-A", LIB) == "face" and wm.measure_for("SUB", LIB) == "plan"


def test_suggest_keeps_edits_patterns_and_drops_missing_layers():
    layers = ["FAC::Steel frames", "STR::Frame", "STR::Slabs", "FAC::Glass", "FAC::brick black", "FAC::metal"]
    rules, dropped = wm.suggest_rules(layers, PATTERNS, LIB)
    by = lambda p: [r for r in rules if r["layer"] == p]           # noqa: E731
    assert by("FAC::Steel frames")[0]["measure"] == "ignore"          # first matching pattern wins
    assert [r["measure"] for r in by("STR::Frame")] == ["volume_v", "volume_h"]
    assert by("FAC::Glass")[0]["factor"] == 1.25 and by("FAC::Glass")[0]["replaces"] == "facade"
    assert by("FAC::metal")[0]["source"] == "not mapped"
    edited = [dict(r) for r in rules]
    edited[-1].update(measure="face", build_up="WALL-B", source="edited")
    again, dropped = wm.suggest_rules(layers[1:], PATTERNS, LIB, edited)
    assert dropped == ["FAC::Steel frames"]
    assert [r for r in again if r["layer"] == "FAC::metal"][0]["build_up"] == "WALL-B"


def test_checks():
    ok = wm.new_rule("L", "2.2.1", "volume", "SLAB-M3")
    assert wm.check_rules([ok], LIB) == []
    bad = [wm.new_rule("L", "2.2.1", "plan", "SLAB-M3"), wm.new_rule("L", "2.2.1", "volume", ""),
           wm.new_rule("L", "2.2.1", "volume", "NOPE"), wm.new_rule("L", "", "volume", "SLAB-M3"),
           wm.new_rule("L", "2.2.1", "volume", "SLAB-M3", factor=0)]
    msgs = [m for _, m in wm.check_rules(bad, LIB)]
    assert any("is per m3" in m for m in msgs) and any("choose a build-up" in m for m in msgs)
    assert any("not in the office library" in m for m in msgs) and any("RICS element" in m for m in msgs)
    assert any("above 0" in m for m in msgs) and all("(step 2)" in m for m in msgs)
    assert wm.check_rules([wm.new_rule("L")], LIB) == []                # ignored lines are never checked


def test_modelled_rows_replace_their_groups_only():
    rules = [wm.new_rule("STR::Slabs", "2.2.1", "volume", "SLAB-M3"),
             wm.new_rule("STR::Frame", "2.1.1", "volume_v", "COL-M3", replaces="columns"),
             wm.new_rule("STR::Frame", "2.1.2", "volume_h", "BEAM-M3", replaces="beams")]
    measured = {"layers": {"STR::Slabs": stats(n=50, vol=5000.0), "STR::Frame": stats(n=139, open=12, vol=2151.0, vol_v=2079.0, vol_h=72.0)},
                "tagged": {"WALL-B": stats(n=3, face=12.0, layers=["FAC::metal"])}}
    rows, shares, rep, notes = wm.modelled_rows(rules, measured, LIB, {"project_id": "T"})
    assert [(r["build_up_code"], r["quantity"], r["unit"]) for r in rows] == \
        [("SLAB-M3", 5000.0, "m3"), ("COL-M3", 2079.0, "m3"), ("BEAM-M3", 72.0, "m3"), ("WALL-B", 12.0, "m2")]
    assert all(r["method"] == "Modelled" for r in rows) and shares == []
    assert any("12 open object(s)" in n for n in notes)
    out, report = wm.apply_modelled(derived(), rows, rep, B)
    kept = set(r["element_id"] for r in out if r["method"] == "Derived")
    # floors, columns and edge beams replaced; the core walls (2.1.1 from the plan) and everything else stay;
    # the tagged wall (2.5.1, facade group) removes the derived facade walls and glazing, not the soffit, louvres, doors
    assert kept == {"MS-4", "MS-5", "MS-8", "MS-9", "MS-10", "MS-11"}
    g = dict((x["group"], x) for x in report)
    assert g["floors"]["derived"] == {"m2": 9000.0} and g["floors"]["modelled"] == {"m3": 5000.0}
    assert g["facade"]["derived"] == {"m2": 1000.0}


def test_facade_shares_split_the_massing_facade():
    rules = [wm.new_rule("FAC::brick", "2.5.1", "share", "WALL-A"), wm.new_rule("FAC::precast", "2.5.1", "share", "WALL-B"),
             wm.new_rule("FAC::Glass", "2.6", "share", "WIN", factor=1.25)]
    measured = {"layers": {"FAC::brick": stats(face=500.0), "FAC::precast": stats(face=300.0), "FAC::Glass": stats(face=160.0)},
                "tagged": {}}
    rows, shares, rep, notes = wm.modelled_rows(rules, measured, LIB)
    assert rows == [] and [s[3] for s in shares] == [500.0, 300.0, 200.0]
    base, new, net, old = wm.share_rows(derived(), shares, B, {"project_id": "T"})
    assert net == 1000.0                                                  # derived opaque 600 + glazed 400
    assert [(r["build_up_code"], r["quantity"]) for r in new] == [("WALL-A", 500.0), ("WALL-B", 300.0), ("WIN", 200.0)]
    out, report = wm.apply_modelled(base, rows, rep, B, new, old)
    assert report[0]["derived"] == {"m2": 1000.0} and report[0]["modelled"] == {"m2": 1000.0}
    assert sum(float(r["quantity"]) for r in out if wm.kind_of(r, B) in ("facade_opaque", "facade_glazed", "windows")) == 1000.0
    assert {"MS-4", "MS-8", "MS-9"} <= set(r["element_id"] for r in out)  # soffit, louvres, doors stay
    assert wm.facade_header_from_rows(out, B) == {"facade_curtain_wall_share": 0.0, "facade_punched_window_share": 0.2}


def test_state_finish_rows_uses_the_model_only_when_asked():
    st = ws.default_state()
    o = ws.default_option("A", layer="M")
    st["options"] = [o]
    st["modelled"]["rules"] = [wm.new_rule("STR::Slabs", "2.2.1", "volume", "SLAB-M3")]
    st["modelled"]["measured"] = {"layers": {"STR::Slabs": stats(vol=5000.0)}, "tagged": {}}
    office = {"facade_types": [{"code": "CW", "label": "CW", "kind": "unitised"}]}
    o["facade"] = [{"build_up": "CW", "kind": "unitised", "share": 1.0, "wwr": None}]
    o["use_modelled"] = False
    rows, hdr, rep, notes = ws.finish_rows(derived(), o, st, office, B)
    assert not any(r["method"] == "Modelled" for r in rows) and rep == []
    o["use_modelled"] = True
    ws._LIB_CACHE.clear()
    rows, hdr, rep, notes = ws.finish_rows(derived(), o, st, office, B)   # no library file: tagged objects skipped, rules apply
    assert [r["build_up_code"] for r in rows if r["method"] == "Modelled"] == ["SLAB-M3"]
    assert not any(r["element_id"] == "MS-1" for r in rows)
    assert rep and rep[0].startswith("Upper floors and roof slabs")


def test_rule_view_and_edits():
    st = ws.default_state()
    st["modelled"]["rules"] = [wm.new_rule("FAC::brick", "2.5.1", "share", "WALL-A"), wm.new_rule("FAC::Glass", "2.6", "share", "WIN", 1.25),
                               wm.new_rule("X", "", "ignore")]
    st["modelled"]["measured"] = {"layers": {"FAC::brick": stats(n=10, face=300.0), "FAC::Glass": stats(n=5, face=80.0)}, "tagged": {}}
    v = ws.rule_view(st)
    assert v[0]["q"] == 300.0 and v[1]["q"] == 100.0 and v[0]["share"] == 0.75 and v[2]["q"] is None
    r = st["modelled"]["rules"][2]
    r["build_up"] = "SLAB-M3"
    ws.after_rule_edit(st, 2, "build_up", LIB)
    assert r["measure"] == "volume" and r["rics"] == "2.2.1" and r["replaces"] == "floors" and r["source"] == "edited"
    r["rics"] = "2.1.1"
    ws.after_rule_edit(st, 2, "rics", LIB)
    assert r["replaces"] == "columns"


def test_validate_flags_model_lines_on_step_2():
    st = ws.default_state()
    st["options"] = [ws.default_option("A", layer="M")]
    st["modelled"]["rules"] = [wm.new_rule("L", "2.2.1", "volume", "")]
    msgs = [m for lv, m in ws.validate(st) if lv == "error"]
    assert any("choose a build-up" in m and "(step 2)" in m for m in msgs)
    st["options"][0]["use_modelled"] = False
    assert not any("Model layer" in m for _, m in ws.validate(st))


def test_read_library(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws_ = wb.active
    ws_.title = "Buildups"
    ws_.append(["Build-up library"]); ws_.append([None]); ws_.append([None])
    ws_.append(["build_up_code", "RICS code", "Description", "Declared unit"])
    ws_.append(["SLAB-M3", "2.2.1", "RC slab", "m3"])
    p = tmp_path / "lib.xlsx"
    wb.save(p)
    assert wm.read_library(str(p)) == {"SLAB-M3": {"rics": "2.2.1", "desc": "RC slab", "unit": "m3", "a13": None}}


def test_keep_the_larger_compares_a1_a3():
    lib = dict(LIB, EB={"unit": "m", "rics": "2.1.2", "desc": "edge beam", "a13": 62.0},
               **{"BEAM-M3": dict(LIB["BEAM-M3"], a13=443.0)})
    a13 = dict((c, b.get("a13")) for c, b in lib.items() if b.get("a13") is not None)
    rule = wm.new_rule("STR::Frame", "2.1.2", "volume_h", "BEAM-M3")
    assert rule["replaces"] == "beams" and rule["mode"] == "auto"
    assert wm.resolve_mode("auto", "beams", 4) == "larger"                  # edge beams: conservative at every stage
    assert [wm.resolve_mode("auto", g, 2) for g in ("floors", "columns", "lowest_slab", "basement_walls", "facade")] == \
        ["larger", "larger", "larger", "replace", "replace"]
    assert [wm.resolve_mode("auto", g, 3) for g in ("floors", "columns", "lowest_slab")] == ["replace"] * 3
    assert wm.resolve_mode("replace", "beams", 2) == "replace"
    for vol, kept in ((50.0, "derived"), (100.0, "modelled")):
        rows, _, rep, _ = wm.modelled_rows([rule], {"layers": {"STR::Frame": stats(vol_h=vol)}, "tagged": {}}, lib, {"stage": 2})
        out, report = wm.apply_modelled(derived(), rows, rep, B, a13=a13)
        assert report[0]["kept"] == kept and report[0]["t"] == (31.0, round(vol * 0.443, 1))   # 500 m x 62 kg/m = 31.0 t
        ebs = [r["build_up_code"] for r in out if r["nrm_code"] == "2.1.2"]
        assert ebs == (["EB"] if kept == "derived" else ["BEAM-M3"])
        assert "taken forward" in wm.report_lines(report)[0]
    rule["mode"] = "replace"
    rows, _, rep, _ = wm.modelled_rows([rule], {"layers": {"STR::Frame": stats(vol_h=72.0)}, "tagged": {}}, lib)
    out, report = wm.apply_modelled(derived(), rows, rep, B, a13=a13)
    assert [r["build_up_code"] for r in out if r["nrm_code"] == "2.1.2"] == ["BEAM-M3"] and report[0]["t"] is None


def test_read_library_works_out_a1_a3_per_unit(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    sh = {n: wb.create_sheet(n) for n in ("Buildups", "Layers", "Materials", "Rebar_Rates")}
    del wb["Sheet"]
    for s in sh.values():
        for _ in range(4):
            s.append([None])
    sh["Buildups"].append(["BEAM", "2.1.2", "beam", "m"])
    sh["Materials"].append(["CONC", "c", "kg", 1, 2400, 0.10625])
    sh["Materials"].append(["REBAR", "r", "kg", 1, 7850, 0.8])
    sh["Rebar_Rates"].append(["RB-BEAM", "beams", 235])
    sh["Layers"].append(["BEAM", 1, "CONC", 0.14, "m3"])
    sh["Layers"].append(["BEAM", 2, "REBAR", '=0.14*INDEX(Rebar_Rates!$C$5:$C$30,MATCH("RB-BEAM",Rebar_Rates!$A$5:$A$30,0))', "kg"])
    p = tmp_path / "lib.xlsx"
    wb.save(p)
    assert wm.read_library(str(p))["BEAM"]["a13"] == pytest.approx(0.14 * 2400 * 0.10625 + 0.14 * 235 * 0.8)
