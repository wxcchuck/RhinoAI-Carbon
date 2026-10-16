#! python3
# r: openpyxl
"""
WLCA dialog for Rhino 8  v0.1  (draft for review)

Drafted by an AI agent (Claude) - review before trusting.

Opens from the WLCA toolbar button (or the WLCA alias). Six steps:
  1 Project & options   2 Drawings & schedule   3 Facade   4 Structure   5 Targets & reporting   6 Run
Everything is saved in the .3dm (document user text), so the next run starts where the last one ended.
Run take-off measures every ticked option and writes its export; Create workbook builds the Excel
calculation workbook with the office library, benchmarks, targets and branding from the office settings.

Files this script expects next to it (the package folder): wlca_state.py, wlca_core.py,
wlca_massing_takeoff.py, wlca_calc_template.py, wlca_dashboard.py.
Office settings: WLCA_OFFICE_SETTINGS environment variable, else ..\\07_Settings\\wlca_office_settings.json
relative to the package folder.
"""
import os
import sys
import traceback

import Rhino
import Rhino.Geometry as rg
import Eto.Drawing as drawing
import Eto.Forms as forms

PKG = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else globals().get("WLCA_PKG_DIR", "")
if PKG and PKG not in sys.path:
    sys.path.insert(0, PKG)
import wlca_state as ws  # noqa: E402

try:
    DOC = __rhino_doc__          # noqa: F821  (injected when run remotely)
except NameError:
    import scriptcontext
    DOC = scriptcontext.doc

STEPS = ["1  Project & options", "2  Drawings & schedule", "3  Facade", "4  Structure", "5  Targets & reporting", "6  Run"]
USES = ["Office", "Residential", "Schools & Universities", "Retail"]
try:
    import wlca_core as _core          # noqa: E402
    FRAMES = list(_core.FRAME_SYSTEMS)
except Exception:                      # dialog still opens if the take-off core is missing
    FRAMES = ["RC flat slab"]
SCENARIOS = ["GLA aspirational", "GLA benchmark", "None"]
BUDGETS = ["UKNZCBS", "LETI 2030 (A)", "LETI 2020 (C)", "RIBA 2030", "GLA aspirational A1-A5", "GLA benchmark A1-A5"]
ACCENT = drawing.Color.FromArgb(1, 100, 109)
MUTED = drawing.Color.FromArgb(95, 99, 104)
WARN = drawing.Color.FromArgb(122, 74, 0)
GOOD = drawing.Color.FromArgb(30, 86, 49)


def office_settings_path():
    p = os.environ.get("WLCA_OFFICE_SETTINGS")
    if p:
        return p
    return os.path.normpath(os.path.join(PKG, "..", "07_Settings", "wlca_office_settings.json"))


def pct(text, default=None):
    """'70%', '70' or '0.7' -> 0.7"""
    try:
        t = str(text).strip().rstrip("%").strip()
        v = float(t)
        return v / 100.0 if (v > 1 or str(text).strip().endswith("%")) else v
    except ValueError:
        return default


def num(text, default=None):
    try:
        return float(str(text).strip())
    except ValueError:
        return default


# ------------------------------------------------------------------------------------- small control helpers
def mk(cls, *args, **props):
    """Construct an Eto control, then set properties (pythonnet has no keyword initialisers for most Eto types)."""
    obj = cls(*args)
    for k, v in props.items():
        setattr(obj, k, v)
    return obj


def label(text, muted=False, bold=False, size=None, color=None):
    lb = mk(forms.Label, Text=text)
    if muted or color is not None:
        lb.TextColor = color if color is not None else MUTED
    if bold:      # FontStyle.None is a Python keyword - only the bold case is set explicitly
        lb.Font = drawing.Font(lb.Font.Family, size or lb.Font.Size, drawing.FontStyle.Bold)
    lb.Wrap = forms.WrapMode.Word
    return lb


def textbox(value, on_change, width=None):
    t = mk(forms.TextBox, Text="" if value is None else str(value))
    if width:
        t.Width = width
    t.TextChanged += lambda s, e: on_change(t.Text)
    return t


def dropdown(items, selected, on_change, width=None):
    d = forms.DropDown()
    d.DataStore = list(items)
    d.SelectedIndex = list(items).index(selected) if selected in items else (0 if items else -1)
    if width:
        d.Width = width
    d.SelectedIndexChanged += lambda s, e: on_change(items[d.SelectedIndex]) if d.SelectedIndex >= 0 else None
    return d


def checkbox(text, value, on_change):
    c = mk(forms.CheckBox, Text=text, Checked=bool(value))
    c.CheckedChanged += lambda s, e: on_change(bool(c.Checked))
    return c


def button(text, on_click, primary=False):
    b = mk(forms.Button, Text=text)
    b.Click += lambda s, e: on_click()
    if primary:
        b.BackgroundColor = ACCENT
        b.TextColor = drawing.Colors.White
    return b


def section(layout, title):
    layout.AddRow(label(title, bold=True, size=11))


# ------------------------------------------------------------------------------------- the form
class WLCAForm(forms.Form):

    def __init__(self, doc=None):
        super().__init__()
        self.doc = doc or DOC
        self.Title = "WLCA - whole life carbon (RICS PS 2nd ed.)"
        self.ClientSize = drawing.Size(1000, 700)
        self.Resizable = True
        self.Padding = drawing.Padding(0)
        self.state = ws.loads(self.doc.Strings.GetValue(ws.STATE_KEY) or "")
        self.office, self.office_error = None, None
        try:
            self.office = ws.load_office(office_settings_path())
        except Exception as e:  # shown on step 6; the form still opens
            self.office_error = "Office settings not found (%s): %s" % (office_settings_path(), e)
        self.exports, self.run_rows, self.messages = [], [], []
        self.step = 0
        self.sel_option = 0
        if not self.state["project"]["name"]:
            self.state["project"]["name"] = os.path.splitext(self.doc.Name or "")[0]
        if not self.state["output"]["folder"] and self.doc.Path:
            self.state["output"]["folder"] = os.path.join(os.path.dirname(self.doc.Path), "WLCA")
        if not self.state["options"]:
            layers = self.massing_layers()
            self.state["options"] = [ws.default_option("A", layer=layers[0] if layers else "")]

        self.nav = forms.ListBox()
        self.nav.DataStore = STEPS
        self.nav.Width = 190
        self.nav.SelectedIndex = 0
        self.nav.SelectedIndexChanged += lambda s, e: self.show_step(self.nav.SelectedIndex)
        self.body = forms.Scrollable()
        self.footer_back = button("Back", lambda: self.goto(self.step - 1))
        self.footer_next = button("Next", lambda: self.goto(self.step + 1), primary=True)
        footer = mk(forms.DynamicLayout, Padding=drawing.Padding(12, 8), Spacing=drawing.Size(8, 8))
        footer.AddRow(None, self.footer_back, self.footer_next, button("Close", self.Close))
        main = mk(forms.TableLayout, Spacing=drawing.Size(0, 0))
        main.Rows.Add(forms.TableRow(forms.TableCell(self.nav), forms.TableCell(self.body, True)))
        main.Rows[0].ScaleHeight = True
        main.Rows.Add(forms.TableRow(forms.TableCell(None), forms.TableCell(footer)))
        self.Content = main
        self.show_step(0)

    # ---------------------------------------------------------------- state helpers
    def save(self):
        self.doc.Strings.SetString(ws.STATE_KEY, ws.dumps(self.state))

    def setter(self, d, key, conv=None):
        def f(v):
            d[key] = conv(v) if conv else v
            self.save()
        return f

    def massing_layers(self):
        out = []
        for lay in self.doc.Layers:
            if lay.IsDeleted or lay.FullPath.startswith("WLCA"):
                continue
            if any(o.Geometry and isinstance(o.Geometry, (rg.Brep, rg.Extrusion)) for o in self.doc.Objects.FindByLayer(lay) or []):
                out.append(lay.FullPath)
        return sorted(out)

    def all_layers(self):
        return sorted(l.FullPath for l in self.doc.Layers if not l.IsDeleted and not l.FullPath.startswith("WLCA"))

    def goto(self, i):
        if 0 <= i < len(STEPS):
            self.nav.SelectedIndex = i

    def show_step(self, i):
        self.step = i
        builders = [self.page_project, self.page_drawings, self.page_facade, self.page_structure, self.page_targets, self.page_run]
        lay = mk(forms.DynamicLayout, Padding=drawing.Padding(22, 18), Spacing=drawing.Size(10, 8))
        try:
            builders[i](lay)
        except Exception:
            lay.AddRow(label("This step could not be drawn:\n" + traceback.format_exc(), color=WARN))
        lay.Add(None)
        self.body.Content = lay
        self.footer_back.Enabled = i > 0
        self.footer_next.Enabled = i < len(STEPS) - 1

    def refresh(self):
        self.show_step(self.step)

    # ---------------------------------------------------------------- 1 project & options
    def page_project(self, L):
        p = self.state["project"]
        section(L, "Project")
        L.BeginVertical(None, drawing.Size(12, 6))
        L.AddRow(label("Project name"), textbox(p["name"], self.setter(p, "name")),
                 label("Use class"), dropdown(USES, p["use_class"], self.setter(p, "use_class")))
        L.AddRow(label("RIBA stage"), dropdown(["0", "1", "2", "3", "4"], str(p["riba_stage"]), self.setter(p, "riba_stage", int)),
                 label("Construction start year"), textbox(p["start_year"], self.setter(p, "start_year", lambda v: int(num(v, 2027)))))
        L.AddRow(label("Existing GIA demolished (m²)"), textbox(p["demolished_gia_m2"], self.setter(p, "demolished_gia_m2", lambda v: num(v, 0.0))),
                 label("Assessor"), textbox(p["assessor"], self.setter(p, "assessor")))
        L.EndVertical()
        section(L, "Design options")
        L.AddRow(label("Each option is one massing layer in this file, or another .3dm. Facade and structure are set per option "
                       "on steps 3 and 4, so options can share a massing.", muted=True))
        layers = self.massing_layers() or self.all_layers()
        L.BeginVertical(None, drawing.Size(8, 6))
        L.AddRow(label("Include", muted=True), label("Option name", muted=True), label("Massing from", muted=True),
                 label("Layer / file", muted=True), None)
        for i, o in enumerate(self.state["options"]):
            src = dropdown(["This file", "Other .3dm"], "This file" if o["source"] == "layer" else "Other .3dm",
                           self._set_source(o))
            if o["source"] == "layer":
                where = dropdown(layers, o["layer"], self.setter(o, "layer"), width=260)
            else:
                where = forms.DynamicLayout()
                where.AddRow(textbox(o["file"], self.setter(o, "file"), width=200), button("...", self._pick_3dm(o)))
            L.AddRow(checkbox("", o["include"], self.setter(o, "include")), textbox(o["name"], self.setter(o, "name"), width=200),
                     src, where, button("Remove", self._remove_option(i)))
        L.EndVertical()
        L.AddRow(button("+ Option", self.add_option), button("Duplicate last option", self.duplicate_option), None)

    def _set_source(self, o):
        def f(v):
            o["source"] = "layer" if v == "This file" else "file"
            self.save()
            self.refresh()
        return f

    def _pick_3dm(self, o):
        def f():
            dlg = forms.OpenFileDialog()
            dlg.Filters.Add(forms.FileFilter("Rhino model", ".3dm"))
            if dlg.ShowDialog(self) == forms.DialogResult.Ok:
                o["file"] = dlg.FileName
                self.save()
                self.refresh()
        return f

    def _remove_option(self, i):
        def f():
            if len(self.state["options"]) > 1:
                self.state["options"].pop(i)
                self.save()
                self.refresh()
        return f

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

    # ---------------------------------------------------------------- 2 drawings & schedule
    def page_drawings(self, L):
        s = self.state["schedule"]
        section(L, "Area schedule")
        L.AddRow(label("Excel file with levels, GEA and GIA (optional: AOD, floor-to-floor, NIA, use). Without it, levels come "
                       "from the massing and the storey heights.", muted=True))
        sheets = self.sheet_names(s["path"])
        L.BeginVertical(None, drawing.Size(8, 6))
        L.AddRow(textbox(s["path"], self.setter(s, "path"), width=520), button("Browse...", self.pick_schedule),
                 dropdown(sheets or [""], s["sheet"], self.setter(s, "sheet"), width=140))
        L.EndVertical()
        L.AddRow(self.schedule_preview())
        section(L, "Typical floor plan (cores, columns, stairs)")
        pl = self.state["plan"]
        routes = ["None - use office defaults", "PDF plan extract (.json)", "Plan in Rhino (next release)"]
        cur = {"none": routes[0], "pdf": routes[1], "rhino": routes[2]}.get(pl["route"], routes[0])
        L.AddRow(dropdown(routes, cur, self._set_plan_route, width=320), None)
        if pl["route"] == "pdf":
            L.BeginVertical(None, drawing.Size(8, 6))
            L.AddRow(textbox(pl["pdf_json"], self.setter(pl, "pdf_json"), width=520), button("Browse...", self.pick_plan_json))
            L.EndVertical()
            L.AddRow(label("Output of the plan extractor (WLCA_plan_extract). Check its overlay image before using it.", muted=True))
        elif pl["route"] == "rhino":
            L.AddRow(label("Reading the plan straight from Rhino curves comes in the next release. Put the plan on its own layer "
                           "at true scale in model units; it can sit anywhere in the model.", color=WARN))

    def _set_plan_route(self, v):
        self.state["plan"]["route"] = "none" if v.startswith("None") else ("pdf" if v.startswith("PDF") else "rhino")
        self.save()
        self.refresh()

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

    def schedule_preview(self):
        s = self.state["schedule"]
        if not s["path"]:
            return label("No schedule chosen.", muted=True)
        if not os.path.exists(s["path"]):
            return label("File not found.", color=WARN)
        try:
            import wlca_core as core
            w = []
            lv = core.parse_area_schedule({"path": s["path"], "sheet": s["sheet"] or None}, w)
            gea = sum(float(x["gea"] or 0) for x in lv)
            gia = sum(float(x["gia"] or 0) for x in lv)
            txt = "Read: %d levels, %s to %s  |  GEA %s m²  |  GIA %s m²" % (
                len(lv), lv[0]["name"], lv[-1]["name"], "{:,.0f}".format(gea), "{:,.0f}".format(gia))
            return label(txt + ("\n" + "\n".join(w) if w else ""), color=GOOD if not w else WARN)
        except Exception as e:
            return label("Could not read the schedule: %s" % e, color=WARN)

    # ---------------------------------------------------------------- 3 facade
    def option_picker(self, L):
        names = [o["name"] for o in self.state["options"]]
        self.sel_option = min(self.sel_option, len(names) - 1)

        def pick(v):
            self.sel_option = names.index(v)
            self.refresh()
        L.AddRow(label("Option"), dropdown(names, names[self.sel_option], pick, width=280), None)
        return self.state["options"][self.sel_option]

    def page_facade(self, L):
        o = self.option_picker(L)
        cat = ws.facade_catalogue(self.office or {})
        labels = ["%s (%s)" % (c["label"], c["code"]) for c in cat]
        section(L, "Facade types and their share")
        L.AddRow(label("Up to three types; shares are of the whole net facade and must add up to 100%. Curtain-wall types carry "
                       "their glazing in the system; other types take a glazing ratio.", muted=True))
        L.BeginVertical(None, drawing.Size(8, 6))
        L.AddRow(label("Type (from the office library)", muted=True), label("Share", muted=True), label("Glazing ratio", muted=True), None)
        for i, f in enumerate(o["facade"]):
            cur = next((l for l, c in zip(labels, cat) if c["code"] == f["build_up"]), None)
            wwr = textbox("" if f.get("wwr") is None else "%.0f%%" % (100 * f["wwr"]), self._set_f(f, "wwr", pct), width=70)
            wwr.Enabled = f.get("kind") != ws.FACADE_UNITISED
            L.AddRow(dropdown(labels, cur, self._set_type(f, cat, labels), width=380),
                     textbox("%.0f%%" % (100 * f["share"]), self._set_f(f, "share", pct), width=70),
                     wwr if wwr.Enabled else label("in the system", muted=True),
                     button("Remove", self._remove_facade(o, i)))
        L.EndVertical()
        tot = sum(float(f.get("share") or 0) for f in o["facade"])
        ok = abs(tot - 1) < 0.005
        L.AddRow(button("+ Add a type", lambda: self._add_facade(o, cat)),
                 label("Shares add up to %.0f%%" % (tot * 100), color=GOOD if ok else WARN), None)
        L.AddRow(label("The list shows the facade types in the office library. A new type is added to the library once and then "
                       "appears here for every project.", muted=True))

    def _set_f(self, f, key, conv):
        def g(v):
            f[key] = conv(v, f.get(key))
            self.save()
        return g

    def _set_type(self, f, cat, labels):
        def g(v):
            c = cat[labels.index(v)]
            f["build_up"], f["kind"] = c["code"], c["kind"]
            if c["kind"] == ws.FACADE_PUNCHED and f.get("wwr") is None:
                f["wwr"] = 0.4
            self.save()
            self.refresh()
        return g

    def _remove_facade(self, o, i):
        def g():
            if len(o["facade"]) > 1:
                o["facade"].pop(i)
                self.save()
                self.refresh()
        return g

    def _add_facade(self, o, cat):
        if len(o["facade"]) < ws.MAX_FACADE_TYPES:
            c = cat[min(len(o["facade"]), len(cat) - 1)]
            o["facade"].append({"build_up": c["code"], "kind": c["kind"], "share": 0.0,
                                "wwr": 0.4 if c["kind"] == ws.FACADE_PUNCHED else None})
            self.save()
            self.refresh()

    # ---------------------------------------------------------------- 4 structure
    def page_structure(self, L):
        o = self.option_picker(L)
        s = o["structure"]
        section(L, "Frame")
        L.BeginVertical(None, drawing.Size(12, 6))
        L.AddRow(label("Frame system"), dropdown(FRAMES, s["frame"], self.setter(s, "frame"), width=260),
                 label("Steel and timber frames use the PF Stage 1 rates per m² of floor; their columns are scaled with "
                       "height (tagged [ASSUMED]). Cores stay RC.", muted=True))
        L.AddRow(label("Column grid x (m)"), textbox(s["grid_x_m"], self.setter(s, "grid_x_m", lambda v: num(v, 9.0)), width=80),
                 label("Column grid y (m)"), textbox(s["grid_y_m"], self.setter(s, "grid_y_m", lambda v: num(v, 8.0)), width=80))
        L.AddRow(label("Column size (m, square)"), textbox(s["column_size_m"], self.setter(s, "column_size_m", lambda v: num(v, 0.75)), width=80),
                 None, None)
        L.EndVertical()
        L.AddRow(label("Cores, columns and stairs come from the plan on step 2 when there is one; otherwise these values and the "
                       "office defaults are used and the rows are tagged [ASSUMED] in the workbook. Foundations and basement walls "
                       "use the office defaults (piles 750 mm, 3 per column, 25 m; secant wall + 200 RC liner) until the "
                       "engineer's figures are entered.", muted=True))

    # ---------------------------------------------------------------- 5 targets & reporting
    def page_targets(self, L):
        t = self.state["targets"]
        section(L, "Targets to compare against")
        L.BeginVertical(None, drawing.Size(12, 6))
        L.AddRow(checkbox("UKNZCBS upfront limits (offices: shell & core limit)", t["show"]["UKNZCBS"], self.setter(t["show"], "UKNZCBS")),
                 checkbox("LETI bands", t["show"]["LETI"], self.setter(t["show"], "LETI")))
        L.AddRow(checkbox("RIBA 2030 Climate Challenge", t["show"]["RIBA"], self.setter(t["show"], "RIBA")),
                 checkbox("GLA London Plan Guidance", t["show"]["GLA"], self.setter(t["show"], "GLA")))
        L.EndVertical()
        section(L, "UKNZCBS offices")
        sc = t["sc_share"]
        L.BeginVertical(None, drawing.Size(12, 6))
        L.AddRow(label("Shell & core share - finishes"), textbox("%.0f%%" % (100 * sc["finishes"]), self._set_share("finishes"), width=70),
                 label("- FF&E"), textbox("%.0f%%" % (100 * sc["ffe"]), self._set_share("ffe"), width=70),
                 label("- services"), textbox("%.0f%%" % (100 * sc["services"]), self._set_share("services"), width=70))
        L.AddRow(label("Cat B + loose FF&E (kgCO2e/m²)"), textbox(t["catb_allowance"] or "", self.setter(t, "catb_allowance", lambda v: num(v, None))),
                 label("blank = whole-building limit not assessed", muted=True), None, None, None)
        L.EndVertical()
        section(L, "Scenario and budget")
        L.BeginVertical(None, drawing.Size(12, 6))
        L.AddRow(label("Elements not yet designed - scenario"), dropdown(SCENARIOS, t["scenario"], self.setter(t, "scenario")),
                 label("Carbon budget against"), dropdown(BUDGETS, t["budget_target"], self.setter(t, "budget_target")))
        L.EndVertical()
        section(L, "Where to save")
        out = self.state["output"]
        L.BeginVertical(None, drawing.Size(8, 6))
        L.AddRow(textbox(out["folder"], self.setter(out, "folder"), width=520), button("Browse...", self.pick_folder))
        L.EndVertical()
        L.AddRow(label("Take-off exports go to a 'takeoff' folder inside it; the workbook is saved there too. Everything set in "
                       "this dialog is written into the workbook - nothing has to be typed in Excel.", muted=True))

    def _set_share(self, key):
        def g(v):
            self.state["targets"]["sc_share"][key] = pct(v, self.state["targets"]["sc_share"][key])
            self.save()
        return g

    def pick_folder(self):
        dlg = forms.SelectFolderDialog()
        if dlg.ShowDialog(self) == forms.DialogResult.Ok:
            self.state["output"]["folder"] = dlg.Directory
            self.save()
            self.refresh()

    # ---------------------------------------------------------------- 6 run
    def page_run(self, L):
        if self.office_error:
            L.AddRow(label(self.office_error, color=WARN))
        checks = ws.validate(self.state, self.office)
        for lv, m in checks:
            L.AddRow(label(("Fix: " if lv == "error" else "Note: ") + m, color=WARN if lv == "error" else MUTED))
        blocked = any(lv == "error" for lv, _ in checks) or self.office is None
        b1 = button("1  Run take-off", self.run_takeoff)
        b1.Enabled = not blocked
        L.AddRow(b1, label("Measures every ticked option and draws floor plates and GIA curves on the WLCA layers for checking.", muted=True))
        if self.run_rows:
            L.BeginVertical(None, drawing.Size(18, 4))
            L.AddRow(*([label("Quantity", muted=True)] + [label(o["name"], bold=True) for o, _ in self.exports] + [None]))
            for row in self.run_rows:
                L.AddRow(*([label(row[0])] + [label(v) for v in row[1:]] + [None]))
            L.EndVertical()
        for m in self.messages:
            L.AddRow(label(m, color=WARN))
        b2 = button("2  Create workbook", self.create_workbook, primary=True)
        b2.Enabled = bool(self.exports) and not blocked
        L.AddRow(b2, label("Uses the office library, benchmarks and targets in the office settings.", muted=True))
        if self.state["output"].get("last_workbook"):
            wb = self.state["output"]["last_workbook"]
            L.AddRow(label("Saved: " + wb, color=GOOD), button("Open in Excel", lambda: os.startfile(wb)),
                     button("Open folder", lambda: os.startfile(os.path.dirname(wb))))

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
                glaz = sum(float(r["quantity"]) for r in r2 if str(r["nrm_code"]) == "2.5.2" and r["unit"] == "m2")
                asm = sum(1 for r in r2 if str(r.get("notes", "")).startswith("[ASSUMED]"))
                cols.append([geom["gia_m2"], geom["facade_total_m2"], glaz, geom["horizontals"].get("upper", 0), "%d of %d" % (asm, len(r2))])
                for w in geom.get("warnings", []):
                    self.messages.append("%s: %s" % (o["name"], w))
            except Exception as e:
                self.messages.append("%s: take-off refused - %s" % (o["name"], e))
            finally:
                for i in tmp_ids:
                    self.doc.Objects.Delete(i, True)
        names = ["GIA (m²)", "Facade (m²)", "Curtain wall + windows (m²)", "Upper floor slabs (m²)", "Rows resting on an assumption"]
        fmt = lambda v: "{:,.0f}".format(v) if isinstance(v, (int, float)) else str(v)  # noqa: E731
        self.run_rows = [[n] + [fmt(c[i]) for c in cols] for i, n in enumerate(names)] if cols else []
        self.doc.Views.Redraw()
        self.refresh()

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
            self.save()
        except PermissionError:
            self.messages.append("The workbook is open in Excel - close it and press Create workbook again.")
        except Exception:
            self.messages.append("Workbook not created:\n" + traceback.format_exc(limit=3))
        self.refresh()


def System_Color_Gray():
    import System.Drawing
    return System.Drawing.Color.Gray


def main():
    form = WLCAForm()
    form.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    form.Show()
    return form


if __name__ == "__main__" and not globals().get("WLCA_NO_AUTORUN"):
    main()
