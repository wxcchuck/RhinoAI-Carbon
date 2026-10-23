#! python3
"""
WLCA - Rhino side of the WLCA window  (draft for review)

Drafted by an AI agent (Claude) - review before trusting.

Everything the window (wlca_web.py) does in Rhino, kept apart from the page: office settings, massing and plan
layers, the plan reader, file pickers, the take-off run and the layer checks. WLCAWebForm borrows these methods, so
`self` is the window: it has doc, state, office, exports, run_rows, messages, save() and refresh().
(Moved here from the classic Eto dialog, wlca_dialog.py, when that dialog was retired on 23/10/2026.)
"""
import os
import sys

import Rhino
import Rhino.Geometry as rg
import Eto.Drawing as drawing
import Eto.Forms as forms

PKG = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("WLCA_PKG_DIR", "")
if PKG and PKG not in sys.path:
    sys.path.insert(0, PKG)
import wlca_state as ws  # noqa: E402

USES = ["Office", "Residential", "Schools & Universities", "Retail"]
try:
    import wlca_core as _core          # noqa: E402
    FRAMES = list(_core.FRAME_SYSTEMS)
except Exception:                      # the window still opens if the take-off core is missing
    FRAMES = ["RC flat slab"]
SCENARIOS = ["GLA aspirational", "GLA benchmark", "None"]
OP_ROUTES = ["Engineer prediction (TM54)", "Indicative - EUI estimate or UKNZCBS limit", "Not assessed"]
OP_FIELDS = [("elec", "Grid electricity (kWh)"), ("gas", "Natural gas (kWh)"), ("dh", "District heat (kWh)"),
             ("pv_self", "PV used on site (kWh)"), ("pv_export", "PV exported (kWh)"), ("water", "Water (m³)"),
             ("eui", "Indicative EUI (kWh/m² GIA)")]
BUDGETS = ["UKNZCBS", "LETI 2030 (A)", "LETI 2020 (C)", "RIBA 2030", "GLA aspirational A1-A5", "GLA benchmark A1-A5"]


def office_settings_path():
    return ws.find_office_settings(PKG)


def System_Color_Gray():
    import System.Drawing
    return System.Drawing.Color.Gray


class WLCARhino(object):
    """Rhino-side methods of the WLCA window (borrowed by wlca_web.WLCAWebForm)."""

    def load_office(self):
        """Read the office settings (library, benchmarks, targets, branding); the form opens without them."""
        self.office, self.office_error = None, None
        self.office_path, self.office_source = office_settings_path()
        try:
            if self.office_source == "not found":
                raise IOError("no office settings file found")
            self.office = ws.load_office(self.office_path)
        except Exception as e:
            self.office_error = ("Office settings not loaded (%s). Choose the office settings file on step 7 (Run) - it names the "
                                 "build-up library, benchmarks, targets and branding." % e)

    def pick_office_settings(self):
        dlg = forms.OpenFileDialog()
        dlg.Filters.Add(forms.FileFilter("WLCA office settings", ".json"))
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            ws.remember_office_settings(dlg.FileName)
            self.load_office()
            self.refresh()

    def reset_office_settings(self):
        ws.remember_office_settings("")
        self.load_office()
        self.refresh()

    def massing_layers(self):
        out = []
        for lay in self.doc.Layers:
            if lay.IsDeleted or lay.FullPath.startswith("WLCA"):
                continue
            if any(o.Geometry and isinstance(o.Geometry, (rg.Brep, rg.Extrusion)) for o in self.doc.Objects.FindByLayer(lay) or []):
                out.append(lay.FullPath)
        return sorted(out)

    def massing_extent(self, o):
        """[lowest, highest] point of an option's massing layer in metres, or None (other .3dm / no solids)."""
        if o.get("source") != "layer" or not o.get("layer"):
            return None
        idx = self.doc.Layers.FindByFullPath(o["layer"], -1)
        if idx < 0:
            return None
        s = Rhino.RhinoMath.UnitScale(self.doc.ModelUnitSystem, Rhino.UnitSystem.Meters)
        zs = []
        for obj in self.doc.Objects.FindByLayer(self.doc.Layers[idx]) or []:
            if isinstance(obj.Geometry, (rg.Brep, rg.Extrusion)):
                bb = obj.Geometry.GetBoundingBox(True)
                zs += [bb.Min.Z * s, bb.Max.Z * s]
        return [round(min(zs), 2), round(max(zs), 2)] if zs else None

    def all_layers(self):
        return sorted(l.FullPath for l in self.doc.Layers if not l.IsDeleted and not l.FullPath.startswith("WLCA"))

    def add_option(self):
        layers = self.massing_layers()
        name = chr(ord("A") + len(self.state["options"]))
        self.state["options"].append(ws.default_option(name, layer=layers[0] if layers else ""))
        self.save()
        self.refresh()

    def duplicate_option(self):
        import copy
        o = copy.deepcopy(self.state["options"][-1])
        o["name"] = o["name"] + " (copy)"
        self.state["options"].append(o)
        self.save()
        self.refresh()

    def plan_module(self):
        import wlca_plan_rhino as pr
        return pr

    def find_plan_layers(self, refresh=True):
        try:
            pr = self.plan_module()
            pick, sc = pr.suggest_layers(pr.all_layer_shapes(self.doc), (self.office or {}).get("plan_layer_patterns"),
                                         (self.office or {}).get("plan_reader"))
            pl = self.state["plan"]
            pl["walls_layer"], pl["columns_layer"], pl["stairs_layer"] = pick["walls"], pick["columns"], pick["stairs"]
            pl["summary"] = ["Layers proposed: " + "; ".join("%s %s" % (r, "'%s' (%d)" % (pick[r], sc[pick[r]][i]) if pick[r] else "not found")
                                                          for r, i in (("walls", 0), ("columns", 1), ("stairs", 2))) + ". Press Read plan to measure."]
            pl["json"] = ""
            self.save()
        except Exception as e:
            self.state["plan"]["summary"] = ["Plan layers could not be scanned: %s" % e]
        if refresh:
            self.refresh()

    def read_plan(self, refresh=True):
        """Measure the plan, highlight what was counted and write the json the take-off reads. Returns the path or None."""
        pl = self.state["plan"]
        try:
            pr = self.plan_module()
            plan, ids, notes = pr.read_plan(self.doc, pl.get("walls_layer"), pl.get("columns_layer") or None,
                                            pl.get("stairs_layer") or None, cfg=(self.office or {}).get("plan_reader"))
            folder = os.path.join(self.state["output"]["folder"] or os.path.dirname(self.doc.Path or "") or ".", "takeoff")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "plan_rhino.json")
            import json
            with open(path, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=1)
            pl["json"] = path
            n = pr.highlight(self.doc, ids)
            pl["summary"] = ws.plan_summary(plan, notes) + ["%d objects counted are selected in Rhino - check them. Saved: %s" % (n, path)]
        except Exception as e:
            pl["json"], pl["summary"] = "", ["Plan could not be read: %s" % e]
        self.save()
        if refresh:
            self.refresh()
        return pl["json"] or None

    def pick_schedule(self):
        dlg = forms.OpenFileDialog()
        dlg.Filters.Add(forms.FileFilter("Excel", ".xlsx", ".xlsm"))
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            self.state["schedule"]["path"] = dlg.FileName
            names = self.sheet_names(dlg.FileName)
            self.state["schedule"]["sheet"] = names[0] if names else ""
            self.save()
            self.refresh()

    def pick_plan_json(self):
        dlg = forms.OpenFileDialog()
        dlg.Filters.Add(forms.FileFilter("Plan extract", ".json"))
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            self.state["plan"]["pdf_json"] = dlg.FileName
            self.save()
            self.refresh()

    @staticmethod
    def sheet_names(path):
        if not path or not os.path.exists(path):
            return []
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True)
            return list(wb.sheetnames)
        except Exception:
            return []

    def pick_folder(self):
        dlg = forms.SelectFolderDialog()
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            self.state["output"]["folder"] = dlg.Directory
            self.save()
            self.refresh()

    _fonts = None

    @classmethod
    def font_names(cls):
        if cls._fonts is None:
            try:
                cls._fonts = sorted(set(f.Name for f in drawing.Fonts.AvailableFontFamilies), key=str.lower)
            except Exception:
                cls._fonts = []
        return cls._fonts

    def _set_logo(self, v, refresh=False):
        self.state["output"]["logo"] = (v or "").strip()
        self.save()
        if refresh:
            self.refresh()

    def pick_logo(self):
        dlg = forms.OpenFileDialog()
        dlg.Filters.Add(forms.FileFilter("Image", ".png", ".jpg", ".jpeg", ".gif", ".bmp"))
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            self._set_logo(dlg.FileName, True)

    def needed_layers(self):
        """Layers the run reads: each ticked option's massing layer (this file) and the plan layers (Rhino route)."""
        out = [o["layer"] for o in self.state["options"] if o.get("include") and o["source"] == "layer" and o.get("layer")]
        pl = self.state["plan"]
        if pl.get("route") == "rhino":
            out += [pl.get(k) for k in ("walls_layer", "columns_layer", "stairs_layer") if pl.get(k)]
        return list(dict.fromkeys(out))

    def _layer_chain(self, path):
        """The layer and its parents (a child is not drawn when a parent is off)."""
        idx = self.doc.Layers.FindByFullPath(path, -1)
        chain = []
        while idx >= 0:
            lay = self.doc.Layers[idx]
            chain.append(lay)
            parent = lay.ParentLayerId
            if parent == type(parent).Empty:
                break
            p = self.doc.Layers.FindId(parent)
            idx = p.Index if p is not None else -1
        return chain

    def layers_off(self):
        try:
            return [p for p in self.needed_layers() if any(not l.IsVisible for l in self._layer_chain(p))]
        except Exception:
            return []

    def turn_layers_on(self):
        for p in self.needed_layers():
            for lay in self._layer_chain(p):
                if not lay.IsVisible:
                    lay.IsVisible = True
        self.doc.Views.Redraw()
        self.refresh()

    def load_takeoff(self):
        g = {"__rhino_doc__": self.doc, "WLCA_LIB_DIR": PKG, "WLCA_NO_AUTORUN": True, "__name__": "wlca_takeoff"}
        path = os.path.join(PKG, "wlca_massing_takeoff.py")
        with open(path, encoding="utf-8") as f:
            exec(compile(f.read(), path, "exec"), g)
        return g

    def import_option_file(self, o):
        """Copy the closed solids of another .3dm onto a temporary layer; returns (layer name, object ids)."""
        f3 = Rhino.FileIO.File3dm.Read(o["file"])
        if f3 is None:
            raise ValueError("Cannot read %s" % o["file"])
        scale = Rhino.RhinoMath.UnitScale(f3.Settings.ModelUnitSystem, self.doc.ModelUnitSystem)
        name = "WLCA_import_" + ws.safe_stem(o["name"])
        idx = self.doc.Layers.FindByFullPath(name, -1)
        if idx < 0:
            idx = self.doc.Layers.Add(name, System_Color_Gray())
        attr = Rhino.DocObjects.ObjectAttributes()
        attr.LayerIndex = idx
        ids = []
        for obj in f3.Objects:
            g = obj.Geometry
            if isinstance(g, rg.Extrusion):
                g = g.ToBrep()
            if isinstance(g, rg.Brep) and g.IsSolid:
                g = g.DuplicateBrep()
                if abs(scale - 1) > 1e-9:
                    g.Transform(rg.Transform.Scale(rg.Point3d.Origin, scale))
                ids.append(self.doc.Objects.AddBrep(g, attr))
        return name, ids

    def run_takeoff(self):
        self.exports, self.run_rows, self.messages = [], [], []
        try:
            tk = self.load_takeoff()
        except Exception as e:
            self.messages.append("Take-off script could not load: %s" % e)
            self.refresh()
            return
        os.makedirs(os.path.join(self.state["output"]["folder"], "takeoff"), exist_ok=True)
        pl = self.state["plan"]
        if pl.get("route") == "rhino" and (pl.get("walls_layer") or pl.get("columns_layer")):
            if not self.read_plan(refresh=False):         # re-read: the plan may have changed since step 2
                self.messages.append("Plan: " + " ".join(pl.get("summary") or []))
        cols = []
        for o in [o for o in self.state["options"] if o["include"]]:
            tmp_ids = []
            try:
                cfg = ws.takeoff_config(self.state, o, self.office, tk["CONFIG"])
                if o["source"] == "file":
                    layer, tmp_ids = self.import_option_file(o)
                    cfg["massing_layers"] = [layer]
                header, rows, geom, paths = tk["run"](cfg)
                csv = paths[0]
                h2, r2 = ws.read_export(csv)
                r2 = ws.apply_facade_mix(r2, o, self.office, glazed_code=cfg["build_ups"]["facade_glazed"],
                                         opaque_code=cfg["build_ups"]["facade_opaque"])
                ws.write_export(csv, h2, r2)
                self.exports.append((o, csv))
                glaz = sum(float(r["quantity"]) for r in r2 if r["unit"] == "m2" and (str(r["nrm_code"]) == "2.5.2" or
                           (str(r["nrm_code"]) == "2.6" and "windows:" in str(r.get("notes", "")))))
                asm = sum(1 for r in r2 if str(r.get("notes", "")).startswith("[ASSUMED]"))
                found = sum(float(r["quantity"]) for r in r2 if str(r["nrm_code"]) == "1.1" and r["unit"] == "m3")
                depth = (geom.get("structure") or {}).get("basement_depth_m") or 0
                cols.append([geom["gia_m2"], geom["facade_total_m2"], glaz, geom["horizontals"].get("upper", 0),
                             "%.1f" % depth if depth else "none", found, "%d of %d" % (asm, len(r2))])
                for w in geom.get("warnings", []):
                    self.messages.append("%s: %s" % (o["name"], w))
            except Exception as e:
                self.messages.append("%s: take-off refused - %s" % (o["name"], e))
            finally:
                for i in tmp_ids:
                    self.doc.Objects.Delete(i, True)
        names = ["GIA (m²)", "Façade (m²)", "Curtain wall + windows (m²)", "Upper floor slabs (m²)", "Basement depth (m)",
                 "Piles + caps (m³)", "Rows resting on an assumption"]
        fmt = lambda v: "{:,.0f}".format(v) if isinstance(v, (int, float)) else str(v)  # noqa: E731
        self.run_rows = [[n] + [fmt(c[i]) for c in cols] for i, n in enumerate(names)] if cols else []
        self.doc.Views.Redraw()
        self.refresh()
