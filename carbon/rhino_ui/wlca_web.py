#! python3
# r: openpyxl
"""
WLCA window for Rhino 8 - web interface  v0.1  (draft for review)

Drafted by an AI agent (Claude) - review before trusting.

The window is an Eto form holding one WebView (Edge WebView2 on Windows) that shows web/index.html. The page draws
the steps and the results; everything that touches Rhino, files or the workbook stays in Python:
  page -> Python   window.chrome.webview.postMessage(JSON)   {"type": "set" | "action" | "ready", ...}
  Python -> page   window.wlca.receive(model)                state + lists + checks + run status + results
The take-off / plan / workbook logic is the classic dialog's (wlca_dialog.WLCAForm), borrowed method by method,
so both windows run the same code. After "Create workbook" Excel (hidden) calculates and saves the workbook and
the results are read back from it (wlca_results) - the workbook stays the single source of the numbers.
"""
import json
import os
import sys
import traceback

import Rhino
import Eto.Drawing as drawing
import Eto.Forms as forms
import System

PKG = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("WLCA_PKG_DIR", "")
if PKG and PKG not in sys.path:
    sys.path.insert(0, PKG)
import wlca_state as ws  # noqa: E402
import wlca_results as wr  # noqa: E402
import wlca_dialog as wd  # noqa: E402  (the classic dialog: shared logic)

try:
    DOC = __rhino_doc__          # noqa: F821
except NameError:
    import scriptcontext
    DOC = scriptcontext.doc

_D = wd.WLCAForm
STEPS = ["Project & options", "Drawings & schedule", "Substructure", "Superstructure - Structure",
         "Superstructure - Façade", "Targets & reporting", "Run", "Results"]
PLAN_ROUTES = [("rhino", "Plan in Rhino (layers)"), ("pdf", "PDF plan extract (.json)"), ("none", "None - use office defaults")]


class WLCAWebForm(forms.Form):
    # ---- logic shared with the classic dialog (same code, same state)
    load_office = _D.load_office
    massing_layers = _D.massing_layers
    all_layers = _D.all_layers
    plan_module = _D.plan_module
    find_plan_layers = _D.find_plan_layers
    read_plan = _D.read_plan
    pick_schedule = _D.pick_schedule
    pick_plan_json = _D.pick_plan_json
    pick_folder = _D.pick_folder
    pick_office_settings = _D.pick_office_settings
    reset_office_settings = _D.reset_office_settings
    pick_logo = _D.pick_logo
    _set_logo = _D._set_logo
    needed_layers = _D.needed_layers
    _layer_chain = _D._layer_chain
    layers_off = _D.layers_off
    turn_layers_on = _D.turn_layers_on
    load_takeoff = _D.load_takeoff
    import_option_file = _D.import_option_file
    run_takeoff = _D.run_takeoff
    add_option = _D.add_option
    duplicate_option = _D.duplicate_option
    massing_extent = _D.massing_extent
    sheet_names = staticmethod(_D.sheet_names)

    def __init__(self, doc=None):
        super().__init__()
        self.doc = doc or DOC
        name, ver = ws.package_info(PKG)
        self.Title = "%s%s - whole life carbon (RICS PS 2nd ed.)" % (name, (" " + ver) if ver else "")
        self.ClientSize = drawing.Size(1080, 760)
        self.MinimumSize = drawing.Size(720, 480)
        self.Resizable = True
        self.state = ws.loads(self.doc.Strings.GetValue(ws.STATE_KEY) or "")
        self.load_office()
        self.exports, self.run_rows, self.messages = [], [], []
        self.calc = {"status": "", "message": ""}       # Excel calculation: "" | running | done | failed
        self.results = None
        self._proc, self._timer = None, None
        if not self.state["project"]["name"]:
            self.state["project"]["name"] = os.path.splitext(self.doc.Name or "")[0]
        if not self.state["output"]["folder"] and self.doc.Path:
            self.state["output"]["folder"] = os.path.join(os.path.dirname(self.doc.Path), "WLCA")
        if not self.state["options"]:
            layers = self.massing_layers()
            self.state["options"] = [ws.default_option("A", layer=layers[0] if layers else "")]
        self.load_results(quiet=True)
        self.view = forms.WebView()
        self.view.MessageReceived += self.on_message
        self.Content = self.view
        self.view.Url = System.Uri(os.path.join(PKG, "web", "index.html"))
        self.Closed += lambda s, e: self.stop_timer()

    # ---------------------------------------------------------------- bridge
    def save(self):
        self.doc.Strings.SetString(ws.STATE_KEY, ws.dumps(self.state))

    def refresh(self):
        self.post(self.model())

    def post(self, obj):
        script = "window.wlca && window.wlca.receive(%s);" % json.dumps(obj, default=str)
        self.view.ExecuteScriptAsync(script)

    def on_message(self, sender, e):
        # Rhino may reset sys.path between script runs; the window lives on, so put the package back first
        if PKG and PKG not in sys.path:
            sys.path.insert(0, PKG)
        try:
            msg = json.loads(e.Message)
        except ValueError:
            return
        try:
            t = msg.get("type")
            if t == "set":
                path = msg["path"]
                ws.apply_edit(self.state, path, msg.get("value"), msg.get("kind", "text"))
                self.after_set(path)
                self.save()
            elif t == "action":
                self.action(msg.get("name"), msg.get("args") or {})
            self.refresh()
        except Exception:
            self.messages = ["Something went wrong in the window:\n" + traceback.format_exc(limit=4)]
            self.refresh()

    def after_set(self, path):
        """Knock-on changes the classic dialog makes when a field changes."""
        if path[:1] == ["plan"] and path[-1] in ("walls_layer", "columns_layer", "stairs_layer"):
            self.state["plan"]["summary"], self.state["plan"]["json"] = [], ""
        if path[:2] == ["schedule", "path"]:
            names = self.sheet_names(self.state["schedule"]["path"])
            self.state["schedule"]["sheet"] = names[0] if names else ""

    # ---------------------------------------------------------------- actions from the page
    def action(self, name, a):
        st, opts = self.state, self.state["options"]
        if name == "add_option":
            self.add_option()
        elif name == "duplicate_option":
            self.duplicate_option()
        elif name == "remove_option" and len(opts) > 1:
            opts.pop(int(a["i"]))
        elif name == "option_source":
            opts[int(a["i"])]["source"] = a["source"]
        elif name == "pick_3dm":
            dlg = forms.OpenFileDialog()
            dlg.Filters.Add(forms.FileFilter("Rhino model", ".3dm"))
            if dlg.ShowDialog(self) == forms.DialogResult.Ok:
                opts[int(a["i"])]["file"] = dlg.FileName
        elif name == "add_facade":
            o, cat = opts[int(a["i"])], ws.facade_catalogue(self.office or {})
            if len(o["facade"]) < ws.MAX_FACADE_TYPES:
                c = cat[min(len(o["facade"]), len(cat) - 1)]
                o["facade"].append({"build_up": c["id"], "kind": c["kind"], "share": 0.0,
                                    "wwr": 0.4 if c["kind"] == ws.FACADE_PUNCHED else None})
        elif name == "remove_facade":
            o = opts[int(a["i"])]
            if len(o["facade"]) > 1:
                o["facade"].pop(int(a["j"]))
        elif name == "facade_type":
            f = opts[int(a["i"])]["facade"][int(a["j"])]
            c = next(c for c in ws.facade_catalogue(self.office or {}) if c["id"] == a["id"])
            f["build_up"], f["kind"] = c["id"], c["kind"]
            if c["kind"] == ws.FACADE_PUNCHED and f.get("wwr") is None:
                f["wwr"] = 0.4
        elif name == "copy_substructure":
            import copy
            src = opts[int(a["i"])]["substructure"]
            for o in opts:
                o["substructure"] = copy.deepcopy(src)
        elif name == "add_basement_level":
            b = ws.fill_substructure(opts[int(a["i"])])["substructure"]["basement"]
            b["levels"].append(ws.new_basement_level(len(b["levels"]) + 1))
        elif name == "remove_basement_level":
            opts[int(a["i"])]["substructure"]["basement"]["levels"].pop(int(a["j"]))
        elif name == "plan_route":
            st["plan"]["route"] = a["route"]
        elif name in ("pick_schedule", "pick_plan_json", "pick_folder", "pick_office_settings", "reset_office_settings",
                      "pick_logo", "turn_layers_on"):
            getattr(self, name)()
        elif name == "logo_none":
            self._set_logo("")
        elif name == "find_plan_layers":
            self.find_plan_layers(refresh=False)
        elif name == "read_plan":
            self.read_plan(refresh=False)
        elif name == "run_takeoff":
            self.run_takeoff()
        elif name == "create_workbook":
            self.create_workbook()
        elif name == "calculate":
            self.start_calculation()
        elif name == "open_workbook" and st["output"].get("last_workbook"):
            os.startfile(st["output"]["last_workbook"])
        elif name == "open_folder" and st["output"].get("last_workbook"):
            os.startfile(os.path.dirname(st["output"]["last_workbook"]))
        elif name == "classic":
            f = wd.WLCAForm(self.doc)
            f.Owner = Rhino.UI.RhinoEtoApp.MainWindow
            f.Show()
            self.Close()
            return
        self.save()

    # ---------------------------------------------------------------- workbook + Excel
    def create_workbook(self):
        self.messages = []
        try:
            import importlib
            import wlca_calc_template as ct
            importlib.reload(ct)
            cfg = ws.calc_config(self.state, self.office, self.exports)
            wb = ct.build(cfg)
            wb.save(cfg["out"])
            self.state["output"]["last_workbook"] = cfg["out"]
            self.results = None
            self.save()
        except PermissionError:
            self.messages.append("The workbook is open in Excel - close it and press Create workbook again.")
            return
        except Exception:
            self.messages.append("Workbook not created:\n" + traceback.format_exc(limit=3))
            return
        self.start_calculation()

    def start_calculation(self):
        path = self.state["output"].get("last_workbook")
        if not path or not os.path.exists(path):
            return
        if wr.is_locked(path):
            self.calc = {"status": "failed", "message": "The workbook is open in Excel - close it, then press Calculate results."}
            return
        try:
            self._proc = wr.start_excel_calculation(path)
        except Exception as e:
            self.calc = {"status": "failed", "message": "Excel could not be started: %s" % e}
            return
        self.calc = {"status": "running", "message": "Excel is calculating the workbook (hidden) - this takes about half a minute."}
        self._timer = forms.UITimer()
        self._timer.Interval = 1.0
        self._timer.Elapsed += self.poll_calculation
        self._timer.Start()

    def poll_calculation(self, sender, e):
        if PKG and PKG not in sys.path:
            sys.path.insert(0, PKG)
        if self._proc is None or self._proc.poll() is None:
            return
        rc = self._proc.returncode
        err = (self._proc.stderr.read() or b"").decode("utf-8", "ignore").strip()
        self._proc = None
        self.stop_timer()
        if rc != 0:
            self.calc = {"status": "failed", "message": "Excel could not calculate the workbook (%s). Open it in Excel to see "
                                                         "the numbers." % (err.splitlines()[-1] if err else "code %s" % rc)}
        else:
            self.load_results()
        self.refresh()

    def stop_timer(self):
        if self._timer is not None:
            self._timer.Stop()
            self._timer = None

    def load_results(self, quiet=False):
        path = self.state["output"].get("last_workbook")
        self.results = None
        if not path or not os.path.exists(path):
            return
        try:
            res = wr.read_results(path)
        except Exception as e:
            if not quiet:
                self.calc = {"status": "failed", "message": "Results could not be read: %s" % e}
            return
        if res["calculated"]:
            for o in res["options"]:
                o["verdicts"] = [wr.judge(o["values"].get(t["key"]), t["target"], res["cont"]) for t in res["targets"]]
            self.results = res
            self.calc = {"status": "done", "message": ""}
        elif not quiet:
            self.calc = {"status": "failed", "message": "The workbook has no calculated values yet."}

    # ---------------------------------------------------------------- the model the page draws
    def basement_info(self):
        s = self.state["schedule"]
        return ws.basement_from_schedule(s["path"], s["sheet"])

    def schedule_info(self):
        s = self.state["schedule"]
        if not s["path"]:
            return {"text": "No schedule chosen.", "level": "muted"}
        if not os.path.exists(s["path"]):
            return {"text": "File not found.", "level": "warn"}
        try:
            import wlca_core as core
            w = []
            lv = core.parse_area_schedule({"path": s["path"], "sheet": s["sheet"] or None}, w)
            gea = sum(float(x["gea"] or 0) for x in lv)
            gia = sum(float(x["gia"] or 0) for x in lv)
            txt = "Read: %d levels, %s to %s  |  GEA %s m²  |  GIA %s m²" % (
                len(lv), lv[0]["name"], lv[-1]["name"], "{:,.0f}".format(gea), "{:,.0f}".format(gia))
            return {"text": txt + ("\n" + "\n".join(w) if w else ""), "level": "warn" if w else "good"}
        except Exception as e:
            return {"text": "Could not read the schedule: %s" % e, "level": "warn"}

    def model(self):
        st, office = self.state, self.office or {}
        logo = ws.effective_logo(st, self.office)
        checks = ws.validate(st, self.office)
        branding = dict(office.get("branding") or {})
        branding.pop("logo", None)
        return {
            "type": "model",
            "title": self.Title,
            "steps": STEPS,
            "state": st,
            "lists": {
                "uses": wd.USES, "stages": ["0", "1", "2", "3", "4"], "frames": wd.FRAMES, "scenarios": wd.SCENARIOS,
                "budgets": wd.BUDGETS, "op_routes": wd.OP_ROUTES, "op_fields": wd.OP_FIELDS, "plan_routes": PLAN_ROUTES,
                "massing_layers": self.massing_layers() or self.all_layers(), "all_layers": self.all_layers(),
                "facade_types": ws.facade_catalogue(office), "sheets": self.sheet_names(st["schedule"]["path"]),
                "fonts": _D.font_names(),
                "wall_sources": ws.WALL_SOURCES, "wall_types": ws.WALL_TYPES, "pile_sources": ws.PILE_SOURCES,
                "cap_sources": ws.CAP_SOURCES,
            },
            "office": {"path": self.office_path, "source": self.office_source, "loaded": self.office is not None,
                       "error": self.office_error},
            "schedule": self.schedule_info(),
            "basement": self.basement_info(),
            "massing_z": [self.massing_extent(o) for o in st["options"]],
            "checks": [{"level": lv, "text": m} for lv, m in checks],
            "blocked": any(lv == "error" for lv, _ in checks) or self.office is None,
            "layers_off": self.layers_off(),
            "run": {"rows": self.run_rows, "names": [o["name"] for o, _ in self.exports], "ready": bool(self.exports),
                    "messages": self.messages},
            "logo": {"path": logo, "url": System.Uri(logo).AbsoluteUri if logo and os.path.exists(logo) else "",
                     "exists": bool(logo and os.path.exists(logo))},
            "calc": self.calc,
            "results": self.results,
            "branding": branding,
            "group_labels": ["Substructure", "Superstructure", "Facade", "Internal finishes", "FF&E", "Services (MEP)",
                             "External works", "Site (A5.1/A5.2)"],
        }


def main():
    form = WLCAWebForm()
    form.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    form.Show()
    return form


if __name__ == "__main__" and not globals().get("WLCA_NO_AUTORUN"):
    main()
