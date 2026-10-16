# carbon/ — WLCA massing take-off for Rhino and calculation template

Concept-stage (RIBA 0–2) whole life carbon quantities from a Rhino massing model, an area schedule
and plan drawings. It feeds an Excel-first office WLCA template that follows the RICS WLCA
Professional Statement (2nd ed.).

> **AI-drafted.** All files in this folder were drafted by an AI agent (Claude) and are meant to be
> reviewed before anyone relies on them. This follows the same provenance intent as the `.ai.cs`
> rule in `AGENTS.md`.

The tools output **quantities only, never carbon**. They write rows in the office interchange schema
v0.1, and factors and build-ups live in separate, owner-controlled libraries, which are not part of
this repo. Upstream McNeel code is untouched; everything here sits under `carbon/`.

## What's here

| Path | What it does | Runs in |
|---|---|---|
| `takeoff/wlca_massing_takeoff.py` | Measures the massing: slices storeys, bakes GEA and GIA curves, measures façade by orientation and envelope roofs, then writes CSV and JSON rows | Rhino 8 (Python 3) |
| `takeoff/wlca_core.py` | All quantity rules. No Rhino dependency, so it can be unit-tested | anywhere |
| `takeoff/wlca_plan_extract.py` | Measures core walls (m per floor, thickness), columns (count, size) and stairs (count, flights, treads, width, going) from a vector plan PDF, and writes an overlay image to review | Python 3 (`pymupdf`, `shapely`, `matplotlib`) |
| `calc/wlca_calc_template.py` | Builds the Excel calculation workbook from one take-off export per design option, the build-up library, a benchmark table and (optionally) a targets table. Live formulas: modules A1–A5, B4, C1–C4, D (memo), biogenic (memo), contingency, RICS reporting, QA, target boundaries | Python 3 (`openpyxl`) |
| `calc/wlca_dashboard.py` | Dashboard (one option at a time, picked from a drop-down) and Compare (all options) sheets with native Excel charts on live formulas: targets on their own boundaries, modules, element groups, basis of the number, top 10 materials, GLA element comparison, structure range, carbon budget | Python 3 (`openpyxl`) |
| `rhino_ui/wlca_dialog.py` | The WLCA dialog in Rhino 8: project and options, area schedule and plan, façade mix (up to three types with shares and glazing ratios), structure, targets, then **Run take-off** and **Create workbook**. Settings are saved in the .3dm | Rhino 8 (Python 3, Eto) |
| `rhino_ui/wlca_state.py` | The dialog's state, checks, façade mix and config builders - plain Python, unit-tested | anywhere |
| `rhino_ui/install_wlca.py` | One-time install per PC: adds the `WLCA` command alias and a WLCA toolbar button pointing at the shared package folder | Rhino 8 |
| `calc/config.example.json` | Config template for the generator (paths, options, targets, branding; keep real configs private) | — |
| `tests/` | pytest suite on an invented test tower and an invented library; pilot regression on private data (opt-in) | Python 3 (+ LibreOffice for the workbook number checks) |
| `docs/decisions.md` | Methodology decisions and defaults, with their status | — |

## Inputs and routes

| Input | Exact route | Assumed route |
|---|---|---|
| Floor arrangement | Area schedule xlsx (Level / GEA / GIA, optional AOD, Floor to Floor, NIA) | Massing sliced at storey heights; GIA = massing offset inward by the façade zone |
| Envelope | Massing (always): façade by 8 orientations × WWR, roofs, parapets | — |
| Core + columns | Plan extract JSON | Core area (m², % GIA, or schedule GIA − NIA) × wall density; column grid × edge factor |
| Substructure | Engineer's figures (method `Supplied`) | Bored piles per column + core group; hard/firm secant wall + RC liner; pile caps (method `Derived`, `[ASSUMED]`) |
| Stairs | Supplied volume | Count and flight geometry from the plan extract; waist and landings assumed |
| Edge beams, louvres, doors, roof elements | Supplied length / area | Slab-edge length, plant-level façade, entrance count, roof area × office allowances |

Rows carry RICS element codes and follow the office boundary rules (BR-01 to BR-04): slab allocation
1.2.1 / 1.2.2 / 2.2.1, roof slab vs roof coverings, basement walls in 1.2.3.

The take-off also covers elements a massing model cannot show (v0.8):
- pile caps;
- stairs, counted from the plan drawing;
- edge beams;
- louvres on plant levels and entrance doors;
- other roof elements.

These rules use office assumptions until project information arrives. Each one prefers figures you
supply, then drawings or the model, then the assumption. Rows that still rest on an assumption start
their notes with `[ASSUMED]`, and the calculation workbook lists them and shows their share of the
result.

## Run

**Designers (dialog):** put `wlca_*.py`, `install_wlca.py` in a shared package folder and the office settings file (`wlca_office_settings.json`: library, benchmarks, targets, branding, façade types; relative paths allowed) in `..\07_Settings\` next to it. Each user drags `install_wlca.py` onto Rhino once; after that the WLCA button (or typing `WLCA`) opens the dialog.

**In Rhino 8:** open `takeoff/wlca_massing_takeoff.py` in ScriptEditor, with `wlca_core.py` next to
it. Edit `CONFIG` (project header, area schedule or storey heights, structure and substructure
inputs, build-up codes), then run. Outputs are written next to the .3dm unless `output_dir` is set.

**Plan extract:**
```
python takeoff/wlca_plan_extract.py config.json      # pdf, scale, core window(s), plate window in sheet mm
```
Check `<stem>_overlay.png` before using the numbers.

**Calculation workbook:**
```
python calc/wlca_calc_template.py my_config.json     # see calc/config.example.json
```
Open the workbook and read the sheets in this order:
1. `Project`: inputs, targets to show, scenario and budget target, and the options table (name, GIA, façade route per option).
2. `O<k>_QA`: every FLAG must be fixed or justified, for each option.
3. `Dashboard`: pick an option at the top; every chart follows it. `Compare`: all options side by side.
4. `O<k>_Results`: the RICS element × module table per option.

`O<k>_Lines` shows the working for each take-off row × layer. Target values are not in this repo:
the targets table (UKNZCBS, LETI, RIBA 2030, GLA, structure ranges) is private data supplied through the config.

**Tests:**
```
pip install -r requirements-dev.txt
python -m pytest tests                 # invented test tower; no project data
WLCA_PILOT_DIR=<private folder> python -m pytest tests   # + pilot regression (see test_pilot_private.py)
```

## Data policy

This repository is a **public** fork. Do not commit project schedules, drawings or models, or the
office factor and build-up libraries. Pilot data lives in a private folder and is read through
`WLCA_PILOT_DIR`.
