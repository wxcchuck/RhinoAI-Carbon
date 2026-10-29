#! python3
"""
WLCA modelled elements - Rhino side  v0.1  (draft for review)

Drafted by an AI agent (Claude) - review before trusting. Measures the objects on the model layers the rule table
(step 2) lists; the rules themselves are in wlca_modelled.py (plain Python, tested).

Per object, only Rhino's own fast routines are called (surface area, volume, bounding box), so a model of 150,000+
pieces measures in seconds:
  closed solid / closed mesh   volume V, surface area A, height H (bounding box), plan extent W
                               top area = V / H        face (one side) = (A - 2 V / H) / 2
                               vertical piece when H >= W (columns), else horizontal (beams, slabs)
  open surface / open mesh     no volume; its area counts as plan when it lies flat (H < 0.1 W), else as face
Exact for prismatic pieces with flat tops (slabs, panels, bricks, columns, glass); approximate for sloped or curved ones.
Objects carrying user text WLCA_BUILDUP=<code> are measured apart and grouped by that code. Block instances are not
measured (they are counted and reported). Hidden objects and objects on layers that are off are measured: the rule
table decides what counts.
For the reconciliation (step 3) a layer of up to OBJECT_LIMIT pieces also keeps one record per piece
[z bottom, z top, top area, volume, face, vertical 1/0] (slabs per level, column counts, core and retaining-wall
heights); every layer reports pieces whose centre lies outside the massing (when its extent is given), and pieces
repeated exactly (same bounding box and volume, on any layers) are listed as duplicates.
"""
import Rhino
import Rhino.Geometry as rg

TAG_KEY = "WLCA_BUILDUP"
OBJECT_LIMIT = 5000
OUTSIDE_MARGIN_M = 2.0
_GEOM = (rg.Brep, rg.Extrusion, rg.Mesh, rg.SubD)


def _stats():
    return {"n": 0, "open": 0, "vol": 0.0, "vol_v": 0.0, "vol_h": 0.0, "plan": 0.0, "face": 0.0, "n_v": 0, "blocks": 0,
            "outside": 0}


def _settings(layer_index=None):
    st = Rhino.DocObjects.ObjectEnumeratorSettings()
    st.HiddenObjects = True
    st.LockedObjects = True
    st.NormalObjects = True
    st.IncludeLights = False
    st.IncludeGrips = False
    st.ReferenceObjects = True
    if layer_index is not None:
        st.LayerIndexFilter = layer_index
    return st


def model_layers(doc, exclude=()):
    """Full paths of the layers holding 3D objects (solids, meshes, surfaces), except WLCA* and `exclude`."""
    seen = {}
    for o in doc.Objects.GetObjectList(_settings()):
        if isinstance(o.Geometry, _GEOM):
            seen[o.Attributes.LayerIndex] = seen.get(o.Attributes.LayerIndex, 0) + 1
    out = []
    for idx, n in seen.items():
        p = doc.Layers[idx].FullPath
        if p.startswith("WLCA") or p in exclude:
            continue
        out.append(p)
    return sorted(out)


def object_stats(g):
    """(closed, area, volume, height, plan extent) in model units, or None for geometry that is not measured."""
    if isinstance(g, rg.Extrusion):
        g = g.ToBrep()
    elif isinstance(g, rg.SubD):
        g = g.ToBrep(rg.SubDToBrepOptions.Default)
    if isinstance(g, rg.Mesh):
        closed = g.IsClosed
        amp = rg.AreaMassProperties.Compute(g, True, False, False, False)
        a = amp.Area if amp else 0.0
        v = abs(g.Volume()) if closed else 0.0
    elif isinstance(g, rg.Brep):
        closed = g.IsSolid
        a = g.GetArea()
        v = abs(g.GetVolume()) if closed else 0.0
    else:
        return None
    bb = g.GetBoundingBox(False)
    return closed, a, v, bb.Max.Z - bb.Min.Z, max(bb.Max.X - bb.Min.X, bb.Max.Y - bb.Min.Y), bb


def _add(s, closed, a, v, h, w, bb=None):
    s["n"] += 1
    if closed and h > 1e-9:
        top = v / h
        s["vol"] += v
        s["plan"] += top
        s["face"] += max(0.0, (a - 2.0 * top) / 2.0)
        if h >= w:
            s["vol_v"] += v
            s["n_v"] += 1
        else:
            s["vol_h"] += v
    else:
        s["open"] += 1
        if h < 0.1 * w:
            s["plan"] += a
        else:
            s["face"] += a


def _scaled(s, k):
    out = dict(s)
    for key in ("vol", "vol_v", "vol_h"):
        out[key] = round(s[key] * k ** 3, 3)
    for key in ("plan", "face"):
        out[key] = round(s[key] * k ** 2, 3)
    return out


def extent(doc, paths):
    """Bounding box of the objects on the given layers (the massing), model units, or None."""
    box = rg.BoundingBox.Empty
    for p in paths:
        idx = doc.Layers.FindByFullPath(p, -1)
        if idx < 0:
            continue
        for o in doc.Objects.GetObjectList(_settings(idx)):
            if isinstance(o.Geometry, _GEOM):
                box.Union(o.Geometry.GetBoundingBox(False))
    return box if box.IsValid else None


def _record(closed, a, v, h, w, bb, k):
    top = v / h if closed and h > 1e-9 else (a if h < 0.1 * w else 0.0)
    face = max(0.0, (a - 2.0 * top) / 2.0) if closed and h > 1e-9 else (0.0 if h < 0.1 * w else a)
    return [round(bb.Min.Z * k, 3), round(bb.Max.Z * k, 3), round(top * k * k, 3), round(v * k ** 3, 3), round(face * k * k, 3),
            1 if h >= w else 0]


def measure(doc, paths, envelope=None):
    """{"layers": {path: stats}, "tagged": {code: stats + "layers"}, "duplicates": [[layer, layer, count]], "units": "m"}
    for the given layer paths. Quantities in metres (m3 / m2 / nr), whatever the model units. envelope = the massing's
    bounding box (model units): pieces whose centre lies more than OUTSIDE_MARGIN_M outside it are counted per layer."""
    k = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Meters)
    layers, tagged, tag_layers, keys = {}, {}, {}, {}
    env = None
    if envelope is not None:
        env = rg.BoundingBox(envelope.Min, envelope.Max)
        env.Inflate(OUTSIDE_MARGIN_M / k)
    tol = 0.01 / k                              # 10 mm
    for p in paths:
        idx = doc.Layers.FindByFullPath(p, -1)
        if idx < 0:
            continue
        s = _stats()
        objs = list(doc.Objects.GetObjectList(_settings(idx)))
        keep = len(objs) <= OBJECT_LIMIT
        recs = []
        for o in objs:
            g = o.Geometry
            if isinstance(g, rg.InstanceReferenceGeometry):
                s["blocks"] += 1
                continue
            r = object_stats(g)
            if r is None:
                continue
            bb = r[5]
            if env is not None and not env.Contains(bb.Center):
                s["outside"] += 1
            code = (o.Attributes.GetUserString(TAG_KEY) or "").strip()
            if code:
                _add(tagged.setdefault(code, _stats()), *r)
                tag_layers.setdefault(code, set()).add(p)
            else:
                _add(s, *r)
            if keep:
                recs.append(_record(*(r + (k,))))
                key = tuple(int(round(c / tol)) for c in (bb.Min.X, bb.Min.Y, bb.Min.Z, bb.Max.X, bb.Max.Y, bb.Max.Z)) + \
                    (int(round(r[2] / tol ** 3)) if r[0] else -1,)
                keys.setdefault(key, []).append(p)
        layers[p] = _scaled(s, k)
        if keep:
            layers[p]["objects"] = recs
    out_tagged = {}
    for code, s in tagged.items():
        d = _scaled(s, k)
        d["layers"] = sorted(tag_layers[code])
        out_tagged[code] = d
    dup = {}
    for ps in keys.values():
        if len(ps) > 1:
            for i in range(1, len(ps)):
                pair = tuple(sorted((ps[0], ps[i])))
                dup[pair] = dup.get(pair, 0) + 1
    return {"layers": layers, "tagged": out_tagged, "units": "m",
            "duplicates": [[a, b, n] for (a, b), n in sorted(dup.items())]}
