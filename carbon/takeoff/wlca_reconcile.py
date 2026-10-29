"""
WLCA reconciliation  v0.1  (draft for review)
Office WLCA template - step 7 check between the take-off and the workbook: area schedule, 2D plans, massing and the
detailed model side by side, per quantity

Drafted by an AI agent (Claude) - review before trusting. Plain Python (no Rhino), unit-tested in carbon/tests.

Rows (decided with XW 29/10/2026)
  levels   GEA per level: schedule, massing slice, modelled slab top area at that level (slabs grouped by their top
           to the nearest level within LEVEL_SNAP_M); building totals below
  totals   slab concrete and average thickness, lowest slab, columns (concrete; count at the typical level), edge beams,
           facade area (massing envelope vs modelled developed face), glazing ratio (step 5 mix vs modelled glass),
           core height, basement depth and wall length
  checks   duplicate pieces, open pieces with no volume, flat plates on facade layers, pieces outside the massing
Every comparison is against a reference source (the schedule where there is one); a difference above TOL (5%) is
flagged. Only two rows change the take-off - each a choice the designer makes on the Run step:
  core height      plan wall length x the sum of the storey heights (default), or x the height of the core in the model
  basement depth   the schedule / step 3 levels (default), or the height of the modelled retaining walls
Everything else is decided where it is set (step 2: the model lines and their modes; step 5: the facade mix) - the
row says where. scale_factors() turns the two choices into factors on the derived rows (wlca_state.finish_rows()).
"""
TOL = 0.05
LEVEL_SNAP_M = 1.5
SOURCES = ("schedule", "plan", "massing", "model")
CHOICES = {
    "core_height": [["storeys", "Storey heights"], ["model", "Core in the model"]],
    "basement_depth": [["levels", "Schedule / step 3 levels"], ["model", "Retaining walls in the model"]],
}
SLAB_GROUPS = ("floors", "lowest_slab")
VOLUME_MEASURES = ("volume", "volume_v", "volume_h")
FLAT_MIN_M2 = 0.5          # a facade piece whose top is at least this and larger than its face is a plate lying flat
                           # (bricks and mortar beds are smaller; layers without per-piece records are not checked)


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return (a - b) / b


def row(key, label, unit, values, ref, group="totals", note="", where="", choice=None, level=None, digits=0):
    """One comparison: values {source: number or None}; differences of every other source against `ref`."""
    v = dict((s, None if values.get(s) is None else round(float(values[s]), 3)) for s in SOURCES if s in values)
    diff = dict((s, None if _pct(x, v.get(ref)) is None else round(_pct(x, v.get(ref)), 4)) for s, x in v.items() if s != ref)
    flag = any(d is not None and abs(d) > TOL for d in diff.values())
    return {"key": key, "label": label, "unit": unit, "values": v, "ref": ref, "diff": diff, "flag": flag, "group": group,
            "note": note, "where": where, "choice": choice, "level": level, "digits": digits}


def check(key, label, text):
    return {"key": key, "label": label, "unit": "", "values": {}, "ref": None, "diff": {}, "flag": True, "group": "checks",
            "note": text, "where": "step 2", "choice": None, "level": None, "digits": 0}


# --------------------------------------------------------------------------------------------- helpers
def _lines(rules, groups=None, measures=None):
    out = []
    for r in rules or []:
        m = r.get("measure", "ignore")
        if m == "ignore":
            continue
        if groups is not None and r.get("replaces") not in groups:
            continue
        if measures is not None and m not in measures:
            continue
        out.append(r)
    return out


def _layers(lines):
    return list(dict.fromkeys(r["layer"] for r in lines))


def _objects(measured, layers):
    out = []
    for p in layers:
        out += ((measured.get("layers") or {}).get(p) or {}).get("objects") or []
    return out


def _derived(rows, kinds, build_ups, lib, what="q"):
    """Sum of derived rows of these kinds: quantity (what='q', with units) or concrete m3 (what='conc')."""
    import wlca_modelled as wm
    tot, units, missing = 0.0, set(), False
    for r in rows:
        if wm.kind_of(r, build_ups) not in kinds:
            continue
        q = float(r["quantity"])
        if what == "conc":
            c = (lib.get(r["build_up_code"]) or {}).get("conc")
            if c is None:
                missing = True
                continue
            tot += q * c
        else:
            tot += q
            units.add(r["unit"])
    return (None if missing and tot == 0 else tot), units


def _model_stat(measured, lines, stat):
    """Sum of a stat over the lines' layers (each layer once, for the line's own measure)."""
    import wlca_modelled as wm
    seen, tot = set(), 0.0
    for r in lines:
        key = (r["layer"], wm.STAT.get(r["measure"], stat) if stat is None else stat)
        if key in seen:
            continue
        seen.add(key)
        st = (measured.get("layers") or {}).get(r["layer"])
        if st:
            tot += float(st.get(key[1]) or 0) * (float(r.get("factor") or 1) if stat is None else 1)
    return tot


def levels_of(geom):
    """[(name, z, ftf, schedule GEA or None, massing GEA or None)] bottom-up, from the take-off geometry. z is the
    level's height in the model (metres, as the massing was sliced), the schedule AOD only for a level the massing
    does not reach."""
    rec = geom.get("schedule_reconciliation") or []
    zs = dict((b["name"], b["z"]) for b in geom.get("basement") or [])
    zs.update((s["name"], s["z"]) for s in geom.get("storeys") or [])
    if rec:
        return [(r["level"], zs.get(r["level"], r.get("aod")), r.get("ftf"), r.get("schedule_gea"), r.get("massing_gea"))
                for r in rec]
    out = [(b["name"], b["z"], b["ftf"], None, b.get("massing_gea")) for b in geom.get("basement") or []]
    out += [(s["name"], s["z"], s["height"], None, s["gea"]) for s in geom.get("storeys") or []]
    return out


def slabs_by_level(objects, levels):
    """{level name: top area} - each modelled slab piece to the level whose z is nearest its top, within LEVEL_SNAP_M;
    the rest under None (roofs, podium slabs, pieces between levels)."""
    out = {}
    zs = [(n, z) for n, z, _, _, _ in levels if z is not None]
    for o in objects:
        top, area = o[1], o[2]
        best = min(zs, key=lambda t: abs(t[1] - top)) if zs else None
        name = best[0] if best and abs(best[1] - top) <= LEVEL_SNAP_M else None
        out[name] = out.get(name, 0.0) + area
    return out


# --------------------------------------------------------------------------------------------- reconcile
def reconcile(derived, geom, plan, rules, measured, lib, build_ups, option=None, glazing_mix=None):
    """Rows for one option (see the module docstring). derived = the take-off's own rows (before the facade mix and
    the model); geom = its geometry; plan = the plan json or None; rules / measured = step 2's table and measurement;
    lib = wlca_modelled.read_library(); glazing_mix = the step 5 mix's glazed share of the net facade (0-1)."""
    import wlca_modelled as wm
    measured = measured or {}
    option = option or {}
    choices = dict({"core_height": "storeys", "basement_depth": "levels"}, **(option.get("reconcile") or {}))
    use_model = bool(option.get("use_modelled", True)) and bool(_lines(rules))
    rules = rules if use_model else []
    out = []

    # --- GEA per level
    lv = levels_of(geom)
    slab_lines = _lines(rules, SLAB_GROUPS, VOLUME_MEASURES + ("plan",))
    slab_objs = _objects(measured, _layers(slab_lines))
    if slab_lines and not slab_objs:
        slab_lines = []                     # more than OBJECT_LIMIT pieces: not placed per level
    by_lv = slabs_by_level(slab_objs, lv) if slab_lines else {}
    has_sched = any(x[3] is not None for x in lv)
    ref = "schedule" if has_sched else "massing"
    for name, z, ftf, sg, mg in lv:
        vals = {"massing": mg}
        if has_sched:
            vals["schedule"] = sg
        if slab_lines:
            vals["model"] = by_lv.get(name)
        out.append(row("gea:%s" % name, "Level %s" % name, "m2", vals, ref, "levels", level=name))
    tot = {"massing": sum(x[4] or 0 for x in lv)}
    if has_sched:
        tot["schedule"] = sum(x[3] or 0 for x in lv)
    if slab_lines:
        tot["model"] = sum(v for k, v in by_lv.items() if k is not None)
    notes = []
    if slab_lines:
        notes.append("Model: slab top area at each level - openings, cores and risers make it smaller than GEA")
    if by_lv.get(None):
        notes.append("modelled slabs not at a level (roofs, podiums): %.0f m2" % by_lv[None])
    out.append(row("gea:total", "GEA, all levels", "m2", tot, ref, "levels", where="step 2 (area schedule)", note="; ".join(notes)))

    if not use_model:
        return out

    # --- slabs
    fl = _lines(rules, ("floors",), VOLUME_MEASURES)
    if fl:
        d, _ = _derived(derived, ("upper_floor",), build_ups, lib, "conc")
        mv = _model_stat(measured, fl, "vol")
        out.append(row("slabs_m3", "Upper floor and roof slabs: concrete", "m3", {"massing": d, "model": mv}, "massing",
                       where="step 2 (model lines: keep the larger / replace)"))
        area, units = _derived(derived, ("upper_floor",), build_ups, lib)
        area = area if units == {"m2"} else None
        mp = _model_stat(measured, fl, "plan")
        out.append(row("slabs_t", "Upper floor slabs: average thickness", "m",
                       {"massing": (d / area) if d and area else None, "model": (mv / mp) if mp else None}, "massing", digits=3,
                       where="step 2", note="Massing: the slab build-up's thickness; model: volume / top area"))
    lo = _lines(rules, ("lowest_slab",), VOLUME_MEASURES)
    if lo:
        d, _ = _derived(derived, ("lowest_slab",), build_ups, lib, "conc")
        out.append(row("lowest_m3", "Lowest slab: concrete", "m3", {"massing": d, "model": _model_stat(measured, lo, "vol")},
                       "massing", where="step 2"))
    # --- columns and beams
    cl = _lines(rules, ("columns",), VOLUME_MEASURES)
    if cl:
        d, _ = _derived(derived, ("column",), build_ups, lib, "conc")
        mv = sum(_model_stat(measured, [r], wm.STAT[r["measure"]]) for r in cl)
        out.append(row("columns_m3", "Columns: concrete", "m3", {"massing": d, "model": mv}, "massing", where="step 2"))
        typ = (geom.get("structure") or {}).get("typical_level")
        z = dict((n, (zz, f)) for n, zz, f, _, _ in lv).get(typ)
        pc = ((plan or {}).get("columns") or {}).get("count_per_floor")
        if z and z[0] is not None:
            mid = z[0] + (z[1] or 3.0) / 2.0
            n = sum(1 for o in _objects(measured, _layers(cl)) if o[5] and o[0] <= mid <= o[1])
            out.append(row("columns_n", "Columns at the typical level (%s)" % typ, "nr", {"plan": pc, "model": n},
                           "plan" if pc else "model", where="step 2 (plan layers)"))
    bl = _lines(rules, ("beams",), VOLUME_MEASURES)
    if bl:
        d, _ = _derived(derived, ("edge_beam",), build_ups, lib, "conc")
        mv = sum(_model_stat(measured, [r], wm.STAT[r["measure"]]) for r in bl)
        out.append(row("beams_m3", "Edge beams: concrete", "m3", {"massing": d, "model": mv}, "massing",
                       where="step 2 (keep the larger at every stage)"))

    # --- facade
    fac = [r for r in rules if r.get("measure") in ("share", "face") and r.get("replaces") == "facade"]
    if fac:
        net, _ = _derived(derived, ("facade_opaque", "facade_glazed"), build_ups, lib)
        face = _model_stat(measured, fac, None)
        out.append(row("facade", "Façade area (net of louvres and doors)", "m2", {"massing": net, "model": face}, "massing",
                       where="step 2", note="Model: developed face area, reveals and returns included; with 'share' lines the "
                                            "massing sets the amount and the model the make-up"))
        glass = sum(_model_stat(measured, [r], None) for r in fac if str(r.get("rics", "")).startswith(("2.5.2", "2.6")))
        out.append(row("glazing", "Glazing ratio", "%", {"massing": glazing_mix, "model": glass / face if face else None}, "massing",
                       digits=3, where="step 5 (façade mix)" if not any(r["measure"] == "share" for r in fac) else "step 2",
                       note="Massing: step 5 façade mix (curtain wall counts as glazed); model: glass lines / all façade lines"))

    # --- core height (choice)
    core = [r for r in rules if r.get("measure") == "core_ref" or r.get("replaces") == "core_walls"]
    h_st = sum(float(s.get("height") or 0) for s in geom.get("storeys") or []) + \
        sum(float(b.get("ftf") or 0) for b in geom.get("basement") or [])
    if core:
        objs = _objects(measured, _layers(core))
        h_m = (max(o[1] for o in objs) - min(o[0] for o in objs)) if objs else None
        out.append(row("core_height", "Core walls: height", "m", {"plan": h_st, "model": h_m}, "plan", digits=2,
                       where="here", note="Plan wall length x height; the plan sets the length either way",
                       choice={"key": "core_height", "options": CHOICES["core_height"], "value": choices["core_height"]}))

    # --- basement (choice)
    bw = _lines(rules, ("basement_walls",))
    depth = (geom.get("structure") or {}).get("basement_depth_m")
    if bw and depth:
        objs = _objects(measured, _layers(bw))
        h_m = (max(o[1] for o in objs) - min(o[0] for o in objs)) if objs else None
        out.append(row("basement_depth", "Basement depth", "m", {"schedule": depth, "model": h_m}, "schedule", digits=2,
                       where="here", note="Scales the derived basement walls (secant piles keep their embedment); a modelled "
                                          "wall set to replace takes their place either way",
                       choice={"key": "basement_depth", "options": CHOICES["basement_depth"], "value": choices["basement_depth"]}))
        per = (geom.get("basement_wall_perimeter") or {}).get("m")
        length = sum(o[4] / (o[1] - o[0]) for o in objs if o[1] - o[0] > 0.5) if objs else None
        out.append(row("basement_len", "Basement walls: length", "m", {"massing": per, "model": length}, "massing",
                       where="step 3", note="Model: face area / height of each wall piece"))

    return out + model_checks(rules, measured)


def model_checks(rules, measured):
    """Model problems worth fixing in Rhino: duplicates, open pieces, flat pieces on facade layers, pieces outside."""
    out = []
    layers = measured.get("layers") or {}
    used = set(r["layer"] for r in _lines(rules))
    for a, b, n in measured.get("duplicates") or []:
        if a in used or b in used:
            out.append(check("dup:%s|%s" % (a, b), "Duplicate pieces",
                             "%d piece(s) on '%s' repeat exactly on '%s' - delete the copies, or the quantity counts twice"
                             % (n, b.split("::")[-1], a.split("::")[-1]) if a != b else
                             "%d piece(s) repeated exactly on '%s'" % (n, a.split("::")[-1])))
    for p in sorted(used):
        st = layers.get(p) or {}
        if st.get("open") and any(r["layer"] == p and r["measure"] in VOLUME_MEASURES for r in rules):
            out.append(check("open:" + p, "Open pieces", "'%s': %d open piece(s) have no volume and are not counted - close "
                                                         "them (Cap / MeshRepair)" % (p.split("::")[-1], st["open"])))
        if st.get("outside"):
            out.append(check("out:" + p, "Outside the massing", "'%s': %d piece(s) lie outside the massing - another building, "
                                                                "a site element, or the model is offset?" % (p.split("::")[-1], st["outside"])))
        flat = sum(o[2] for o in st.get("objects") or [] if o[2] >= FLAT_MIN_M2 and o[2] > o[4])
        if any(r["layer"] == p and r["measure"] in ("share", "face") for r in rules) and flat > 0.25 * max(st.get("face", 0), 1):
            out.append(check("flat:" + p, "Flat pieces on a façade layer",
                             "'%s': %.0f m2 of plates lie flat (not counted as façade, face %.0f m2) - soffits, copings or slab "
                             "edges on the wrong layer?" % (p.split("::")[-1], flat, st.get("face", 0))))
    return out


def scale_factors(recon):
    """{derived kind: factor} from the two choices, for wlca_state.finish_rows()."""
    f = {}
    for r in recon or []:
        c = r.get("choice")
        if not c or c["value"] != "model":
            continue
        a, b = r["values"].get("model"), r["values"].get(r["ref"])
        if a and b:
            f["core_wall" if c["key"] == "core_height" else "basement_wall"] = a / b
    return f
