#! python3
# r: openpyxl
"""
WLCA dialog for Rhino 8  v0.1  (draft for review)

Drafted by an AI agent (Claude) - review before trusting.

Opens from the WLCA toolbar button (or the WLCA alias). Seven steps:
  1 Project & options   2 Drawings & schedule   3 Substructure   4 Superstructure - Structure
  5 Superstructure - Facade   6 Targets & reporting   7 Run
Everything is saved in the .3dm (document user text), so the next run starts where the last one ended.
Run take-off measures every ticked option and writes its export; Create workbook builds the Excel
calculation workbook with the office library, benchmarks, targets and branding from the office settings.

Files this script expects next to it (the package folder): wlca_state.py, wlca_core.py,
wlca_massing_takeoff.py, wlca_calc_template.py, wlca_dashboard.py.
Office settings (library, benchmarks, targets, branding): the WLCA_OFFICE_SETTINGS environment variable, else the
file chosen on step 7 (remembered per PC), else the package default (wlca_package.json), else
..\\07_Settings\\wlca_office_settings.json next to the package folder.
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

STEPS = ["1  Project & options", "2  Drawings & schedule", "3  Substructure", "4  Superstructure - Structure",
         "5  Superstructure - Façade", "6  Targets & reporting", "7  Run"]
USES = ["Office", "Residential", "Schools & Universities", "Retail"]
try:
    import wlca_core as _core          # noqa: E402
    FRAMES = list(_core.FRAME_SYSTEMS)
except Exception:                      # dialog still opens if the take-off core is missing
    FRAMES = ["RC flat slab"]
SCENARIOS = ["GLA aspirational", "GLA benchmark", "None"]
OP_ROUTES = ["Engineer prediction (TM54)", "Indicative - EUI estimate or UKNZCBS limit", "Not assessed"]
OP_FIELDS = [("elec", "Grid electricity (kWh)"), ("gas", "Natural gas (kWh)"), ("dh", "District heat (kWh)"),
             ("pv_self", "PV used on site (kWh)"), ("pv_export", "PV exported (kWh)"), ("water", "Water (m³)"),
             ("eui", "Indicative EUI (kWh/m² GIA)")]
BUDGETS = ["UKNZCBS", "LETI 2030 (A)", "LETI 2020 (C)", "RIBA 2030", "GLA aspirational A1-A5", "GLA benchmark A1-A5"]
ACCENT = drawing.Color.FromArgb(1, 100, 109)
MUTED = drawing.Color.FromArgb(95, 99, 104)
WARN = drawing.Color.FromArgb(122, 74, 0)
GOOD = drawing.Color.FromArgb(30, 86, 49)
REQ = drawing.Color.FromArgb(176, 0, 32)
DISABLED = drawing.Color.FromArgb(225, 225, 225)
MIN_CONTENT = 560                    # narrowest page (px) before the page scrolls sideways
SC_SHARE_NOTE = ("The share of each element group - 3 finishes, 4 FF&E, 5 services - that is shell & core. The rest counts as Cat A "
                 "and is taken off A1-A5 (excl. external works) for the UKNZCBS offices shell & core limit only (5.1.6.2). "
                 "100% = nothing taken off: the strict default, which overstates the shell & core figure if the design includes "
                 "Cat A. Example: services 60% takes 40% of services off. Headline figures, LETI, RIBA, GLA, the UKNZCBS "
                 "whole-building limit and other uses are not affected.")
REQ_NOTE = "Fields marked * are needed to run the assessment; the rest have defaults or are optional."


def office_settings_path():
    return ws.find_office_settings(PKG)


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


def amp(text):
    """Windows reads '&' in a label or check box as a keyboard-shortcut marker and hides it; '&&' shows one '&'."""
    return (text or "").replace("&", "&&")


def label(text, muted=False, bold=False, size=None, color=None, width=None):
    lb = mk(forms.Label, Text=amp(text))
    if width:
        lb.Width = width
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


def req(text, muted=False, on=True):
    """Label for a field the run needs, with a red * after it (on=False: plain label, for fields required only sometimes)."""
    if not on:
        return label(text, muted=muted)
    row = mk(forms.StackLayout, Orientation=forms.Orientation.Horizontal, Spacing=3)
    txt, star = mk(forms.Label, Text=amp(text)), mk(forms.Label, Text="*")
    for lb in (txt, star):
        lb.Wrap = forms.WrapMode.NONE                     # pythonnet's name for WrapMode.None (a Python keyword)
        row.Items.Add(forms.StackLayoutItem(lb))
    if muted:
        txt.TextColor = MUTED
    star.TextColor = REQ
    star.Font = drawing.Font(star.Font.Family, star.Font.Size, drawing.FontStyle.Bold)
    return row


def hrow(L, *cells):
    """One row of a DynamicLayout table. A cell is a control, (control, True) for a column that stretches with the
    window, or None for a stretching blank. Rows inside one BeginVertical share their columns."""
    L.BeginHorizontal()
    for c in cells:
        if c is None:
            L.Add(None, True)
        elif isinstance(c, tuple):
            L.Add(c[0], True)
        else:
            L.Add(c)
    L.EndHorizontal()


def stretch(*cells):
    """A small layout of its own (e.g. a path box + Browse button) whose (control, True) cells stretch."""
    d = mk(forms.DynamicLayout, Spacing=drawing.Size(6, 0))
    hrow(d, *cells)
    return d


def checkbox(text, value, on_change):
    c = mk(forms.CheckBox, Text=amp(text), Checked=bool(value))
    c.CheckedChanged += lambda s, e: on_change(bool(c.Checked))
    return c


def button(text, on_click, primary=False, enabled=True):
    b = mk(forms.Button, Text=text)
    b.Click += lambda s, e: on_click()
    if primary:
        b.BackgroundColor = ACCENT
        b.TextColor = drawing.Colors.White
    set_enabled(b, enabled)
    return b


def set_enabled(b, on):
    """Enable / disable a button; a disabled primary button turns grey so its text stays readable."""
    b.Enabled = bool(on)
    if b.BackgroundColor == ACCENT or b.BackgroundColor == DISABLED:
        b.BackgroundColor = ACCENT if on else DISABLED
        b.TextColor = drawing.Colors.White if on else MUTED


def section(layout, title):
    layout.AddRow(label(title, bold=True, size=11))


# ------------------------------------------------------------------------------------- the form
class WLCAForm(forms.Form):

    def __init__(self, doc=None):
        super().__init__()
        self.doc = doc or DOC
        name, ver = ws.package_info(PKG)
        self.Title = "%s%s - whole life carbon (RICS PS 2nd ed.)" % (name, (" " + ver) if ver else "")
        self.ClientSize = drawing.Size(940, 680)
        self.MinimumSize = drawing.Size(MIN_CONTENT + 220, 420)
        self.Resizable = True
        self.Padding = drawing.Padding(0)
        self.state = ws.loads(self.doc.Strings.GetValue(ws.STATE_KEY) or "")
        self.load_office()
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
        self.body = mk(forms.Scrollable, Border=forms.BorderType.NONE, ExpandContentWidth=True)
        self.body.SizeChanged += lambda s, e: self.fit_width()
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

    # ---------------------------------------------------------------- office settings
    def load_office(self):
        """Read the office settings (library, benchmarks, targets, branding); the form opens without them."""
        self.office, self.office_error = None, None
        self.office_path, self.office_source = office_settings_path()
        try:
            if self.office_source == "not found":
                raise IOError("no office settings file found")
            self.office = ws.load_office(self.office_path)
        except Exception as e:
            self.office_error = ("Office settings not loaded (%s). Choose the office settings file on step 7 - it names the "
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
        builders = [self.page_project, self.page_drawings, self.page_substructure, self.page_structure, self.page_facade,
                    self.page_targets, self.page_run]
        lay = mk(forms.DynamicLayout, Padding=drawing.Padding(22, 18), Spacing=drawing.Size(10, 8))
        # every row of the page is one cell of a single column; that column takes the page width, so text wraps
        # (a column sized to its content would let long labels run off to the right). Multi-cell rows go in
        # stretch() / BeginVertical() so they never add columns to the page itself.
        lay.Add(None, True, False)
        if self.office is None and i != 6:
            lay.AddRow(label("Office settings not loaded - choose the file on step 7 (Run) before running.", color=WARN))
        if i in (0, 2, 4, 5):
            lay.AddRow(label(REQ_NOTE, muted=True))
        try:
            builders[i](lay)
        except Exception:
            lay.AddRow(label("This step could not be drawn:\n" + traceback.format_exc(), color=WARN))
        lay.Add(None)
        self.body.Content = lay
        self.fit_width(force=True)
        set_enabled(self.footer_back, i > 0)
        set_enabled(self.footer_next, i < len(STEPS) - 1)

    def refresh(self):
        self.show_step(self.step)

    def fit_width(self, force=False):
        """Keep the page as wide as the window (text wraps, path boxes stretch); below MIN_CONTENT it scrolls sideways."""
        c = self.body.Content
        w = self.body.ClientSize.Width
        if c is None or w <= 0:
            return
        w = max(MIN_CONTENT, w - 20)        # room for the vertical scroll bar, so no sideways bar appears with it
        if force or abs((c.Width or 0) - w) > 2:
            c.Width = w

    # ---------------------------------------------------------------- 1 project & options
    def page_project(self, L):
        p = self.state["project"]
        section(L, "Project")
        L.BeginVertical(None, drawing.Size(12, 6))
        hrow(L, req("Project name"), (textbox(p["name"], self.setter(p, "name")), True),
             label("Use class"), (dropdown(USES, p["use_class"], self.setter(p, "use_class")), True))
        hrow(L, label("RIBA stage"), (dropdown(["0", "1", "2", "3", "4"], str(p["riba_stage"]), self.setter(p, "riba_stage", int)), True),
             label("Construction start year"), (textbox(p["start_year"], self.setter(p, "start_year", lambda v: int(num(v, 2027)))), True))
        hrow(L, label("Existing GIA demolished (m²)"), (textbox(p["demolished_gia_m2"], self.setter(p, "demolished_gia_m2", lambda v: num(v, 0.0))), True),
             label("Assessor"), (textbox(p["assessor"], self.setter(p, "assessor")), True))
        hrow(L, label("Estimated occupancy (people)"), (textbox(p.get("occupancy") or "", self.setter(p, "occupancy", lambda v: num(v, None))), True),
             label("Occupied days per year"), (textbox(p.get("occ_days") or "", self.setter(p, "occ_days", lambda v: num(v, None))), True))
        L.EndVertical()
        L.AddRow(label("Occupancy sets the project's water budget (B7) against the RIBA 2030 Climate Challenge potable water target: workplaces for "
                       "offices, residents for homes, pupils for schools. Days default to 250 (office), 365 (homes), 190 (schools).", muted=True))
        section(L, "Design options")
        L.AddRow(label("Each option is one massing layer in this file, or another .3dm. Substructure, structure and façade are set "
                       "per option on steps 3 to 5, so options can share a massing.", muted=True))
        layers = self.massing_layers() or self.all_layers()
        L.BeginVertical(None, drawing.Size(8, 6))
        hrow(L, label("Include", muted=True), req("Option name", muted=True), label("Massing from", muted=True),
             (req("Layer / file", muted=True), True), label(""))
        for i, o in enumerate(self.state["options"]):
            src = dropdown(["This file", "Other .3dm"], "This file" if o["source"] == "layer" else "Other .3dm",
                           self._set_source(o))
            if o["source"] == "layer":
                where = dropdown(layers, o["layer"], self.setter(o, "layer"))
            else:
                where = stretch((textbox(o["file"], self.setter(o, "file")), True), button("...", self._pick_3dm(o)))
            hrow(L, checkbox("", o["include"], self.setter(o, "include")), textbox(o["name"], self.setter(o, "name"), width=150),
                 src, (where, True), button("Remove", self._remove_option(i)))
        L.EndVertical()
        L.AddRow(stretch(button("+ Option", self.add_option), button("Duplicate last option", self.duplicate_option), None))
        L.AddRow(label("Tick at least one option. Option names must be different from each other.", muted=True))

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
        L.AddRow(stretch((textbox(s["path"], self.setter(s, "path")), True), button("Browse...", self.pick_schedule),
                         dropdown(sheets or [""], s["sheet"], self.setter(s, "sheet"), width=140)))
        L.AddRow(self.schedule_preview())
        section(L, "Typical floor plan (cores, columns, stairs)")
        pl = self.state["plan"]
        routes = ["Plan in Rhino (layers)", "PDF plan extract (.json)", "None - use office defaults"]
        cur = {"rhino": routes[0], "pdf": routes[1], "none": routes[2]}.get(pl["route"], routes[0])
        L.AddRow(stretch(dropdown(routes, cur, self._set_plan_route, width=300), None))
        if pl["route"] == "pdf":
            L.AddRow(stretch((textbox(pl["pdf_json"], self.setter(pl, "pdf_json")), True), button("Browse...", self.pick_plan_json)))
            L.AddRow(label("Output of the plan extractor (WLCA_plan_extract). Check its overlay image before using it.", muted=True))
        elif pl["route"] == "rhino":
            L.AddRow(label("Import or paste the typical floor plan (DWG, DGN or .3dm linework) into this model at true scale - it can sit "
                           "anywhere. The layers below fill themselves from the office layer names and the shapes on each layer; "
                           "change one only if it is wrong. Walls and columns may share a layer.", muted=True))
            if not (pl.get("walls_layer") or pl.get("columns_layer") or pl.get("stairs_layer")):
                self.find_plan_layers(refresh=False)
            names = ["(none)"] + self.all_layers()
            L.BeginVertical(None, drawing.Size(8, 6))
            for key, lbl in (("walls_layer", "Core walls"), ("columns_layer", "Columns"), ("stairs_layer", "Stairs")):
                cur = pl.get(key) if pl.get(key) in names else "(none)"
                hrow(L, label(lbl), (dropdown(names, cur, self._set_plan_layer(key)), True))
            L.EndVertical()
            L.AddRow(stretch(button("Find layers again", self.find_plan_layers), button("Read plan", self.read_plan, primary=True), None))
            for line in pl.get("summary") or []:
                L.AddRow(label(line, color=WARN if line.startswith(("No ", "Units")) else MUTED))

    def _set_plan_layer(self, key):
        def f(v):
            self.state["plan"][key] = "" if v == "(none)" else v
            self.state["plan"]["summary"], self.state["plan"]["json"] = [], ""
            self.save()
        return f

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

    # ---------------------------------------------------------------- option picker (steps 3-5)
    def option_picker(self, L):
        names = [o["name"] for o in self.state["options"]]
        self.sel_option = min(self.sel_option, len(names) - 1)

        def pick(v):
            self.sel_option = names.index(v)
            self.refresh()
        L.AddRow(stretch(label("Option"), dropdown(names, names[self.sel_option], pick, width=260), None))
        return self.state["options"][self.sel_option]

    # ---------------------------------------------------------------- 3 substructure
    def page_substructure(self, L):
        o = self.option_picker(L)
        u = ws.fill_substructure(o)["substructure"]
        sch = self.state["schedule"]
        B = ws.basement_from_schedule(sch.get("path"), sch.get("sheet"))

        def numbox(d, k, width=80):
            v = d.get(k)
            return textbox("" if v in (None, "") else ("%g" % v), self.setter(d, k, lambda t: num(str(t).replace(",", ""), None)),
                           width=width)

        def choice(d, k, items):
            vals, lbls = [v for v, _ in items], [l for _, l in items]

            def f(lbl):
                d[k] = vals[lbls.index(lbl)]
                self.save()
                self.refresh()
            cur = lbls[vals.index(d.get(k))] if d.get(k) in vals else None
            return dropdown(lbls, cur, f, width=380)

        def rows(pairs):
            L.BeginVertical(None, drawing.Size(12, 6))
            for lbl_, ctl in pairs:
                hrow(L, lbl_ if not isinstance(lbl_, str) else label(lbl_), ctl, None)
            L.EndVertical()

        section(L, "Basement")
        if B:
            if B["levels"]:
                L.AddRow(label("From the area schedule: %d level(s) below ground (%s), %.2f m deep. The basement walls use this depth; the "
                               "lowest level's GEA is the lowest slab (1.2.1) and the levels above it up to ground are basement "
                               "suspended slabs (1.2.2)." % (len(B["levels"]), ", ".join(B["levels"]), B["depth_m"]), muted=True))
                if B["lowest_gea"] > 1.05 * B["ground_gea"]:
                    L.AddRow(label("Basement GEA {:,.0f} m² is larger than the ground floor {:,.0f} m²: the ground-floor perimeter may "
                                   "understate the basement walls - enter the basement perimeter below.".format(B["lowest_gea"], B["ground_gea"]),
                                   color=WARN))
            else:
                L.AddRow(label("From the area schedule: no levels below ground - no basement walls or basement slabs.", muted=True))
        else:
            rows([("Basement depth below ground (m)", numbox(u, "basement_depth_m"))])
            L.AddRow(label("No area schedule (step 2): enter the depth for the basement walls; blank = no basement. Without a schedule the "
                           "massing is measured from its lowest point, so a basement modelled in the massing is counted as storeys - the "
                           "area schedule is the reliable route for basements.", muted=True))
        w = u["retaining_walls"]
        section(L, "Basement walls (1.2.3)")
        rows([("Basis", choice(w, "source", ws.WALL_SOURCES))])
        if w.get("source") == "engineer":
            rows([("Wall volume - piled wall (m³)", numbox(w, "volume_m3")), ("Wall area (m²)", numbox(w, "area_m2")),
                  ("Perimeter (m)", numbox(w, "perimeter_m")), ("Depth (m; blank = basement depth)", numbox(w, "depth_m"))])
            L.AddRow(label("The first figure given is used: volume (piled wall), else area (RC wall), else perimeter x depth.", muted=True))
        else:
            pairs = [("Wall type", choice(w, "type", ws.WALL_TYPES))]
            if w.get("type", "secant") == "secant":
                pairs += [(req("Pile diameter (m)"), numbox(w, "pile_diameter_m")), (req("Hard-to-hard spacing (m)"), numbox(w, "pile_spacing_m")),
                          ("Pile length (m; blank = depth x (1 + embedment))", numbox(w, "pile_length_m")),
                          ("Embedment below formation (x retained height)", numbox(w, "embedment_ratio")),
                          ("RC liner thickness (m; blank = no liner)", numbox(w, "liner_thickness_m"))]
            pairs.append(("Basement perimeter (m; blank = ground floor from the massing)", numbox(w, "perimeter_m")))
            rows(pairs)
        p = u["piles"]
        section(L, "Piles (1.1)")
        rows([("Basis", choice(p, "source", ws.PILE_SOURCES))])
        if p.get("source") == "assumed":
            rows([(req("Pile diameter (m)"), numbox(p, "diameter_m")), (req("Piles per column"), numbox(p, "per_column")),
                  (req("Pile length (m)"), numbox(p, "length_m")), ("Core pile spacing (x diameter)", numbox(p, "core_spacing_x_dia"))])
            L.AddRow(checkbox("Pile group under the core (core area from the plan or the schedule)", p.get("core_group"),
                              self.setter(p, "core_group")))
        elif p.get("source") == "engineer":
            rows([(req("Number of piles"), numbox(p, "count")), (req("Pile diameter (m)"), numbox(p, "diameter_m")),
                  (req("Pile length (m)"), numbox(p, "length_m"))])
        c = u["caps_raft"]
        section(L, "Pile caps / raft (1.1)")
        rows([("Basis", choice(c, "source", ws.CAP_SOURCES))])
        if c.get("source") == "assumed":
            rows([(req("Column cap depth (m)"), numbox(c, "depth_m")), ("Cap edge beyond pile (m)", numbox(c, "edge_m")),
                  (req("Core cap thickness (m)"), numbox(c, "core_thickness_m")), ("Core cap margin all round (m)", numbox(c, "core_margin_m"))])
        elif c.get("source") == "engineer":
            rows([(req("Caps / raft volume (m³)"), numbox(c, "volume_m3"))])
        if len(self.state["options"]) > 1:
            L.AddRow(stretch(button("Use these settings for every option", lambda: self._copy_substructure(o)), None))
        L.AddRow(label("Rows resting on these assumptions are tagged [ASSUMED] in the workbook; replace them with the engineer's figures "
                       "when there are some. The lowest slab (1.2.1) and basement slabs (1.2.2) come from the schedule or the massing.",
                       muted=True))

    def _copy_substructure(self, src):
        import copy
        for o in self.state["options"]:
            o["substructure"] = copy.deepcopy(src["substructure"])
        self.save()
        self.refresh()

    # ---------------------------------------------------------------- 5 superstructure - facade
    def page_facade(self, L):
        o = self.option_picker(L)
        cat = ws.facade_catalogue(self.office or {})
        labels = ["%s (%s)" % (c["label"], c["code"]) for c in cat]
        section(L, "Façade types and their share")
        L.AddRow(label("Up to three types; shares are of the whole net facade and must add up to 100%. Curtain-wall types carry "
                       "their glazing in the system; other types take a glazing ratio.", muted=True))
        L.BeginVertical(None, drawing.Size(8, 6))
        punched = any(f.get("kind") != ws.FACADE_UNITISED for f in o["facade"])
        hrow(L, (req("Type (from the office library)", muted=True), True), req("Share", muted=True),
             req("Glazing ratio", muted=True, on=punched), label(""))
        for i, f in enumerate(o["facade"]):
            cur = next((l for l, c in zip(labels, cat) if c["id"] == f["build_up"]), None)
            wwr = textbox("" if f.get("wwr") is None else "%.0f%%" % (100 * f["wwr"]), self._set_f(f, "wwr", pct), width=70)
            wwr.Enabled = f.get("kind") != ws.FACADE_UNITISED
            hrow(L, (dropdown(labels, cur, self._set_type(f, cat, labels)), True),
                 textbox("%.0f%%" % (100 * f["share"]), self._set_f(f, "share", pct), width=70),
                 wwr if wwr.Enabled else label("in the system", muted=True),
                 button("Remove", self._remove_facade(o, i)))
        L.EndVertical()
        tot = sum(float(f.get("share") or 0) for f in o["facade"])
        ok = abs(tot - 1) < 0.005
        L.AddRow(stretch(button("+ Add a type", lambda: self._add_facade(o, cat)),
                         label("Shares add up to %.0f%%" % (tot * 100), color=GOOD if ok else WARN), None))
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
            f["build_up"], f["kind"] = c["id"], c["kind"]
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
            o["facade"].append({"build_up": c["id"], "kind": c["kind"], "share": 0.0,
                                "wwr": 0.4 if c["kind"] == ws.FACADE_PUNCHED else None})
            self.save()
            self.refresh()

    # ---------------------------------------------------------------- 4 superstructure - structure
    def page_structure(self, L):
        o = self.option_picker(L)
        s = o["structure"]
        section(L, "Frame")
        L.AddRow(stretch(label("Frame system"), dropdown(FRAMES, s["frame"], self.setter(s, "frame"), width=260), None))
        L.AddRow(label("Steel and timber frames use the PF Stage 1 rates per m² of floor; their columns are scaled with "
                       "height (tagged [ASSUMED]). Cores stay RC.", muted=True))
        L.BeginVertical(None, drawing.Size(12, 6))
        hrow(L, label("Column grid x (m)"), textbox(s["grid_x_m"], self.setter(s, "grid_x_m", lambda v: num(v, 9.0)), width=80),
             label("Column grid y (m)"), textbox(s["grid_y_m"], self.setter(s, "grid_y_m", lambda v: num(v, 8.0)), width=80), None)
        hrow(L, label("Column size (m, square)"), textbox(s["column_size_m"], self.setter(s, "column_size_m", lambda v: num(v, 0.75)), width=80),
             label(""), label(""), None)
        L.EndVertical()
        L.AddRow(label("Cores, columns and stairs come from the plan on step 2 when there is one; otherwise these values and the "
                       "office defaults are used and the rows are tagged [ASSUMED] in the workbook. Foundations and basement walls "
                       "are set on step 3.", muted=True))

    # ---------------------------------------------------------------- 6 targets & reporting
    def page_targets(self, L):
        t = self.state["targets"]
        section(L, "Targets to compare against")
        L.BeginVertical(None, drawing.Size(12, 6))
        hrow(L, checkbox("UKNZCBS upfront limits (offices: shell & core limit)", t["show"]["UKNZCBS"], self.setter(t["show"], "UKNZCBS")),
             checkbox("LETI bands", t["show"]["LETI"], self.setter(t["show"], "LETI")), None)
        hrow(L, checkbox("RIBA 2030 Climate Challenge", t["show"]["RIBA"], self.setter(t["show"], "RIBA")),
             checkbox("GLA London Plan Guidance", t["show"]["GLA"], self.setter(t["show"], "GLA")), None)
        L.EndVertical()
        section(L, "UKNZCBS offices")
        sc = t["sc_share"]
        L.AddRow(stretch(label("Shell & core share - finishes"), textbox("%.0f%%" % (100 * sc["finishes"]), self._set_share("finishes"), width=60),
                         label("FF&E"), textbox("%.0f%%" % (100 * sc["ffe"]), self._set_share("ffe"), width=60),
                         label("services"), textbox("%.0f%%" % (100 * sc["services"]), self._set_share("services"), width=60), None))
        L.AddRow(label(SC_SHARE_NOTE, muted=True))
        L.AddRow(stretch(label("Cat B + loose FF&E (kgCO2e/m²)"),
                         textbox(t["catb_allowance"] or "", self.setter(t, "catb_allowance", lambda v: num(v, None)), width=80), None))
        L.AddRow(label("Allowance added to the whole building for the UKNZCBS whole-building limit. Blank = that limit is not assessed.",
                       muted=True))
        section(L, "Scenario and budget")
        L.BeginVertical(None, drawing.Size(12, 6))
        hrow(L, label("Elements not yet designed - scenario"), dropdown(SCENARIOS, t["scenario"], self.setter(t, "scenario"), width=220), None)
        hrow(L, label("Carbon budget against"), dropdown(BUDGETS, t["budget_target"], self.setter(t, "budget_target"), width=220), None)
        L.EndVertical()
        section(L, "Operational energy and water (B6 / B7)")
        op = self.state.setdefault("operational", {"route": "Not assessed", "op_year": None, "dh_factor": 0.0})
        L.AddRow(label("Whole life carbon needs a predictive energy model (CIBSE TM54 or equivalent - never Part L). Without one, the "
                       "'Indicative' basis uses each option's EUI estimate, else the UKNZCBS limit, x GIA (all electric).", muted=True))
        if (op.get("route") or "").startswith("Indicative") and op["route"] != OP_ROUTES[1]:
            op["route"] = OP_ROUTES[1]                     # older saves used a shorter label
        L.BeginVertical(None, drawing.Size(12, 6))
        hrow(L, label("Basis"), dropdown(OP_ROUTES, op.get("route") or OP_ROUTES[2], self._set_op_route, width=320), None)
        hrow(L, label("First year of operation"),
             stretch(textbox(op.get("op_year") or "", self.setter(op, "op_year", lambda v: num(v, None)), width=80), None), None)
        hrow(L, label("District heat factor (kgCO2e/kWh)"),
             stretch(textbox(op.get("dh_factor") or "", self.setter(op, "dh_factor", lambda v: num(v, 0.0)), width=80), None), None)
        L.EndVertical()
        if (op.get("route") or "Not assessed") != "Not assessed" or any(any((o.get("operational") or {}).values()) for o in self.state["options"]):
            eng = (op.get("route") or "").startswith("Engineer")
            inc = [o for o in self.state["options"] if o["include"]]
            L.BeginVertical(None, drawing.Size(8, 4))
            hrow(L, *([label("Per year", muted=True)] + [label(o["name"], bold=True, width=110) for o in inc] + [None]))
            for k, lbl_ in OP_FIELDS:
                cells = [req(lbl_, muted=True, on=eng and k in ("elec", "gas", "dh"))]
                for o in inc:
                    ov = o.setdefault("operational", {})
                    cells.append(textbox("" if ov.get(k) in (None, "") else "{:,.0f}".format(ov[k]),
                                         self.setter(ov, k, lambda v: num(str(v).replace(",", ""), None)), width=110))
                hrow(L, *(cells + [None]))
            L.EndVertical()
            if eng:
                L.AddRow(label("* Engineer basis: at least one of grid electricity, gas or district heat for every option.", color=REQ))
            L.AddRow(label("Engineer basis: kWh from the energy model (TM54 mid-range). Indicative basis: only the EUI column is used (blank = "
                           "UKNZCBS limit). Water from the public health engineer; blank = occupancy x RIBA 2025 target. PV used on site counts in "
                           "the EUI at no carbon; PV exported is reported in D2.", muted=True))
        section(L, "Where to save")
        L.AddRow(req("Output folder"))
        out = self.state["output"]
        L.AddRow(stretch((textbox(out["folder"], self.setter(out, "folder")), True), button("Browse...", self.pick_folder)))
        L.AddRow(label("Take-off exports go to a 'takeoff' folder inside it; the workbook is saved there too. Everything set in "
                       "this dialog is written into the workbook - nothing has to be typed in Excel.", muted=True))

    def _set_op_route(self, v):
        self.state["operational"]["route"] = v
        self.save()
        self.refresh()

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

    # ---------------------------------------------------------------- 7 run
    def page_run(self, L):
        section(L, "Office settings")
        L.AddRow(stretch((label(self.office_path or "(none)", muted=self.office is not None, color=None if self.office else WARN), True),
                         button("Choose...", self.pick_office_settings),
                         button("Use default", self.reset_office_settings, enabled=self.office_source == "chosen on this PC")))
        if self.office_error:
            L.AddRow(label(self.office_error, color=WARN))
        else:
            L.AddRow(label("Library, benchmarks, targets and branding come from this file (%s)." % self.office_source, muted=True))
        section(L, "Run")
        checks = ws.validate(self.state, self.office)
        for lv, m in checks:
            L.AddRow(label(("Fix: " if lv == "error" else "Note: ") + m, color=WARN if lv == "error" else MUTED))
        blocked = any(lv == "error" for lv, _ in checks) or self.office is None
        b1 = button("1  Run take-off", self.run_takeoff, enabled=not blocked)
        L.AddRow(stretch(b1, (label("Measures every ticked option and draws floor plates and GIA curves on the WLCA layers for "
                                    "checking.", muted=True), True)))
        L.AddRow(label("Before running, turn on the massing layers (step 1) and the plan layers (step 2), with their parent layers - "
                       "the take-off and the plan reader skip anything on a layer that is off, and objects hidden with Hide "
                       "(use Show first). Easiest: turn all layers on.", color=WARN))
        off = self.layers_off()
        if off:
            L.AddRow(stretch((label("These layers are off now: " + "; ".join(off), color=WARN), True),
                             button("Turn these layers on", self.turn_layers_on)))
        if self.run_rows:
            L.BeginVertical(None, drawing.Size(18, 4))
            L.AddRow(*([label("Quantity", muted=True)] + [label(o["name"], bold=True) for o, _ in self.exports] + [None]))
            for row in self.run_rows:
                L.AddRow(*([label(row[0])] + [label(v) for v in row[1:]] + [None]))
            L.EndVertical()
        for m in self.messages:
            L.AddRow(label(m, color=WARN))
        self.page_appearance(L)
        b2 = button("2  Create workbook", self.create_workbook, primary=True, enabled=bool(self.exports) and not blocked)
        L.AddRow(stretch(b2, (label("Uses the office library, benchmarks and targets in the office settings.", muted=True), True)))
        if self.state["output"].get("last_workbook"):
            wb = self.state["output"]["last_workbook"]
            L.AddRow(stretch((label("Saved: " + wb, color=GOOD), True), button("Open in Excel", lambda: os.startfile(wb)),
                             button("Open folder", lambda: os.startfile(os.path.dirname(wb)))))

    # ---------------------------------------------------------------- workbook font and logo
    _fonts = None

    @classmethod
    def font_names(cls):
        if cls._fonts is None:
            try:
                cls._fonts = sorted(set(f.Name for f in drawing.Fonts.AvailableFontFamilies), key=str.lower)
            except Exception:
                cls._fonts = []
        return cls._fonts

    def page_appearance(self, L):
        out = self.state["output"]
        out.setdefault("font", "Arial")
        out.setdefault("logo", None)
        section(L, "Workbook appearance")
        fonts = self.font_names()
        cb = mk(forms.ComboBox, AutoComplete=True, Width=240)
        cb.DataStore = fonts
        cb.Text = out.get("font") or "Arial"
        status = label("", muted=True)

        def font_status():
            f = (cb.Text or "").strip()
            missing = bool(fonts) and f not in fonts
            status.Text = "not installed on this PC - Excel will show a substitute" if missing else "used on every sheet, charts included"
            status.TextColor = WARN if missing else MUTED

        def set_font(*_):
            out["font"] = (cb.Text or "").strip() or "Arial"
            self.save()
            font_status()
        cb.TextChanged += set_font
        font_status()
        L.BeginVertical(None, drawing.Size(10, 6))
        hrow(L, label("Font"), stretch(cb, (status, True)))
        logo = ws.effective_logo(self.state, self.office)
        hrow(L, label("Company logo (optional)"),
             stretch((textbox(logo, self._set_logo), True), button("Browse...", self.pick_logo), button("No logo", lambda: self._set_logo("", True))))
        L.EndVertical()
        if logo:
            L.AddRow(stretch(self.logo_preview(logo), None))
        L.AddRow(label("The logo goes at the top left of the Dashboard (30 px high). The font is stored by name: people opening the "
                       "workbook without it see Excel's substitute, so use a common font (Arial, Calibri) for files that leave the office.",
                       muted=True))

    def logo_preview(self, path):
        if not os.path.exists(path):
            return label("Logo file not found.", color=WARN)
        try:
            bmp = drawing.Bitmap(path)
            h = 40
            w = max(1, min(260, int(bmp.Width * h / float(bmp.Height))))
            iv = mk(forms.ImageView, Image=bmp)
            iv.Size = drawing.Size(w, int(w * bmp.Height / float(bmp.Width)))
            return iv
        except Exception as e:
            return label("Logo could not be read: %s" % e, color=WARN)

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
