# Decisions log: massing take-off and calculation template

Methodology decisions behind `takeoff/` and `calc/`. **Confirmed** means agreed by the office WLCA lead.
**Assumed** means a working default that still needs confirming. **Open** means not decided yet.
Drafted by an AI agent (Claude) from the working sessions; review before relying on it.

## Method and schema

| # | Decision | Status |
|---|---|---|
| M1 | New interchange method value `Derived`: quantities from massing, schedule or plan rules, with a build-up applied. At RIBA 0–2 it is accepted where the default method is Benchmark, for elements flagged derivable in the scope matrix (1.1, 1.2.1–1.2.3, 2.1.1, 2.2.1, 2.5.1–2.5.3) | Confirmed |
| M2 | The area schedule is a valid GIA source; the header's `gia_source` names the file and sheet | Confirmed |
| M3 | Engineer's figures use the method `Supplied` and always override defaults | Confirmed |

## Floor arrangement

| # | Decision | Status |
|---|---|---|
| F1 | Two routes: (a) area schedule governs levels, FTF, GEA, GIA, slabs, roofs, including basements; (b) massing sliced at storey heights. The massing always governs façade | Confirmed |
| F2 | A volume counts as a storey only if a full storey height fits (`min_storey_fraction` = 1.0) | Assumed |
| F3 | GEA → GIA: inward offset of 0.30 m (façade zone). On the pilot tower this matched the schedule ratio, GIA/GEA = 0.963 | Confirmed |
| F4 | Massing vs schedule reconciled per level; differences above 3% are flagged | Assumed |

## Slabs, roofs, façade (BR-01 to BR-03)

| # | Decision | Status |
|---|---|---|
| S1 | Lowest level → 1.2.1. Suspended slabs below the ground line → 1.2.2. Ground floor and above → 2.2.1. The ground-floor slab over a basement counts as 2.2.1 because it is not *below* the ground line | Assumed (interpretation) |
| S2 | Any part of a storey not covered by the storey above is roof slab (2.2.1) plus roof coverings (2.5.3) | Confirmed |
| S3 | Basement roof outside the building footprint at ground level: slab 2.2.1 only; its finishes are external works 8.1.1 | Assumed (interpretation) |
| S4 | Overhang soffits are reported as insulated soffit (2.5.1), never as a second slab. v0.1 double-counted them; fixed in v0.2 | Confirmed |
| S5 | Façade split into 8 orientation bins centred on N, NE … NW. 4-bin boundaries made 45° façades ambiguous | Confirmed |
| S6 | Glazed area = storey façade × WWR. Opaque = envelope − glazed, so glazed + opaque equals the measured envelope | Confirmed |

## Structure

| # | Decision | Status |
|---|---|---|
| T1 | All core walls are RC for now, including WC and riser walls | Confirmed (for now) |
| T2 | Core walls = wall length per floor × FTF, on every level including basements | Confirmed |
| T3 | Columns per level ∝ (GEA − core area), calibrated on the typical floor | Assumed |
| T4 | Numeric-route defaults, calibrated on the pilot tower: core wall density 0.46 m per m² of core; column edge factor 1.42 on a 9 × 8 m grid | Assumed |
| T5 | Ø750 RC column build-up added (`COL-RC-750`) | Confirmed |

## Substructure (no SI data)

| # | Decision | Status |
|---|---|---|
| U1 | Foundations: bored piles, Ø0.75 m, 3 per column at the lowest level, 25 m long (user-adjustable) | Confirmed |
| U2 | Core pile group: core area ÷ (3 × Ø)² | Confirmed |
| U3 | Basement walls: perimeter = ground-floor footprint (massing), with an option for the engineer's figures | Confirmed |
| U4 | Hard/firm secant wall: Ø1.0 m piles, **1.2 m between hard-pile centres**, one firm pile centred between each pair. Overlaps are deducted once, from the firm piles. Per 1.2 m bay: 0.785 m² hard + 0.338 m² firm → equivalent to a 0.94 m wall | Confirmed |
| U5 | Secant wall length = basement depth × (1 + embedment ratio). Default ratio 0.5 (toe below formation level) | Assumed — confirm with engineer |
| U6 | RC liner, 200 mm, inside the piled wall = perimeter × basement depth | Confirmed |
| U7 | Firm piles use the C32/40 build-up as a placeholder; the real firm mix is lower strength | Open (needs a firm-mix factor) |
| U8 | Pile caps: one cap per column at the lowest level, sized for the piles per column (3 piles: equilateral triangle enclosing the piles at 3 × Ø, 0.15 m edge, corners not trimmed) × 1.2 m deep; plus a 2.0 m core cap over the core area + 0.5 m all round. The engineer's volume replaces both | Assumed |
| U9 | Basement walls take the perimeter of the largest basement level measured on the massing below ground; without a modelled basement, the ground-floor perimeter × √(largest basement GEA / ground GEA), never scaled down. An input perimeter still wins | Confirmed (XW 23/10/2026) |
| U10 | Basement levels come from the area schedule (levels below ground: floor-to-floor, GEA, GIA). When the schedule has none, or there is no schedule, step 3 asks to confirm "no basement" or to enter the levels (name, floor-to-floor, GEA, GIA - GEA / GIA blank = measured on the massing below ground); the run is blocked until answered. Depth = sum of the basement floor-to-floors; lowest level GEA = lowest slab (1.2.1), the levels above it = 1.2.2, the ground slab = 2.2.1 | Confirmed (XW 23/10/2026) |
| U11 | Massing below ground level is never counted as façade (envelope bands start at ground). Ground level in the model: the step 3 entry, else the schedule's ground AOD, else the massing's lowest point; an entry that differs from the schedule AOD moves the schedule levels onto the model | Confirmed (XW 23/10/2026) |
| U12 | Raft option (pile caps / raft basis): raft = thickness (default 1.0 m) × lowest level GEA; its top is the lowest slab (1.2.1, counted there), so the 1.1 row takes the thickness less the lowest slab build-up thickness. With piles it is a piled raft | Assumed (default thickness) |
| U13 | Substructure inputs are set per option (option picker on step 3, as on steps 4 and 5), with a button to copy one option's settings to all | Confirmed (XW 23/10/2026) |

## Maintenance and repair (B2 / B3, calculation template)

| # | Decision | Status |
|---|---|---|
| M1 | B2 (PS 5.2.2, London Plan Guidance 2.5.12) = the greater of 10 kgCO2e/m2 GIA and 1% of A1-A5, as a one-off total over the RSP (not per year), covering all element categories. The 1% is of the whole A1-A5 incl. external works and the site lumps, before contingency | Confirmed (XW 26/10/2026) |
| M2 | B3 (PS 5.2.3) = 25% of the non-MEP part of B2 (B2 x non-services share of A1-A5) + 10% of the A1-A3 of element group 5 services (CIBSE TM65), initial installation only (replacements are in B4) | Confirmed (XW 26/10/2026) |
| M3 | B2 / B3 are whole-building allowances: a block under the element table on O<k>_Results, not allocated to element groups; own bars in the module charts (workbook Dashboard and panel). The PS Table 10 contingency is applied at the end, as for every embodied module | Confirmed (XW 26/10/2026) |
| M4 | A-C, B-C and their target boundaries (LETI life cycle, RIBA 2030, GLA A-C) now include B2 / B3; UKNZCBS upfront (A1-A5) unchanged. Material decarbonisation halves B2 / B3 with B4 (PS 4.11.5 Table 15). B2 / B3 sit with "modelled + site" in the budget and scenario figures (PS defaults, not benchmarks) | Confirmed (XW 26/10/2026) |
| M5 | B4 includes the end of life (C2-C4) of each item it replaces (PS 5.2.4); C1-C4 covers only what is in place at the end of the RSP. A-C is unchanged; the decarbonised figure now halves the replaced items' C3-C4 with the rest of B4 (Table 15). Module D and biogenic carbon still count every item installed (x (1 + replacements)) | Confirmed (XW 26/10/2026) |

## Trajectory over the RSP (window chart, O<k>_Traj)

| # | Decision | Status |
|---|---|---|
| T1 | A1-A5 at year 0 (practical completion); B4 in the year of each replacement; B2 / B3 spread evenly over the RSP; B6 / B7 every year; C1-C4 of what is left at the RSP. Biogenic and module D: see T6 / T7 | Confirmed (XW 26/10/2026) |
| T2 | The end of life (C2-C4) of replaced items is placed in the replacement year; the building's own C1-C4 at the RSP | Confirmed (XW 26/10/2026) |
| T3 | Benchmarked groups have no life of their own: their B4 is spread over replacement years at PS Table 20 representative lives (Project inputs: 2.7/2.8 30, finishes 15, FF&E 10, services 20, external works 35 years) | Confirmed (XW 26/10/2026) |
| T4 | Calendar years from the first year of operation, years from completion as a second scale; two lines per option, solid non-decarbonised and dashed decarbonised (that year's FES factor; Table 15 on B2-B4, C1-C2); contingency on every embodied step, so the end points equal the headline figures | Confirmed (XW 26/10/2026) |
| T5 | Replacement years carrying at least 1.5% of the final embodied figure are marked and named by their largest element groups; the Compare tab overlays one line pair per option with summary cards | Confirmed (XW 26/10/2026) |
| T6 | The lines leave biogenic carbon out, so year 0 equals the headline A1-A5 and there is no step at the RSP from the release. An optional "Biogenic (-1/+1)" view adds it back: stored at year 0, released at the RSP, a replacement's storage cancelling the release of what it replaces. It is the PS reporting convention (A1-A3 / C3-C4), not a forecast of when the carbon returns to the air, and nets to zero over A-C; the workbook keeps it in its own column of O<k>_Traj | For review (26/10/2026, after XW's query) |
| T7 | Module D is reported, never netted: its own column in the whole-life chart, a separated bar in the module chart, a row in the whole-life table (both scenarios, Table 15 halves D) and an optional dotted step beyond the RSP on the trajectory. Before contingency (adding contingency to a benefit would not be conservative) | For review (26/10/2026, after XW's query) |

## Rhino window (dialog v0.1, web window from v0.2)

| # | Decision | Status |
|---|---|---|
| D1 | Designers work in one Rhino 8 dialog (toolbar button / `WLCA` alias); no inputs in Excel. Two clicks: Run take-off (quantities and warnings to check), then Create workbook. Dialog settings are saved in the .3dm | Confirmed |
| D2 | Options: one massing layer per option in the same file (recommended), or another .3dm read without opening it. Options may share a massing and differ in façade or structure | Confirmed |
| D3 | Façade mix: up to three types per option from the office list, each with a share of the net façade (after louvres and doors) and, for punched types, a glazing ratio; shares must add to 100%. The take-off's single glazed / opaque split is replaced by one row per type and part, so the workbook needs no façade routing. Windows in punched types use the curtain wall build-up until a window build-up is in the library (likely high) | Confirmed (windows proxy: Assumed) |
| D4 | Office settings (library, benchmarks, targets, branding, façade list, defaults) live in one JSON file kept by the carbon team; relative paths resolve against the file, so one file serves every user's OneDrive | Confirmed |
| D5 | Plans: read from Rhino layers (true scale, any position; imported DWG/DGN or .3dm linework) is the default route (`takeoff/wlca_plan_rhino.py`); the PDF plan extract stays as the fallback. The Rhino route reproduced the PDF reading of the pilot floor (columns and stairs identical; core walls 137 m at ≈290 mm vs 144 m at 268 mm from the PDF pens) | Confirmed (XW 16/10/2026) |
| D6 | Punched façades take a window build-up per m² of window (glazed area = share × glazing ratio × net façade), reported to RICS 2.6. Office types: aluminium (ETPP EWS-02A) and timber-aluminium (ETPP EWS-02B); PVC not offered (ETPP data "tbc"). The window carries frame, DGU, gaskets, thermal breaks, brackets, head/sill flashings and lintel (PS App M). Rates are per m² of window opening (frame + glass), the area the take-off gives: the ETPP sample is 6 m² at 50:50 WWR, so 3.0 m² of opening holding 2.4 m² of DGU (80% vision) - window items ÷ 3.0 (corrected 16/10/2026 from ÷ 2.4, which was 25% high). The glazing ratio entered for a punched type is the window-to-wall ratio on openings, frames included. A façade type may share a wall build-up with another and differ only in its window (`id` in the office settings). Earlier the curtain wall build-up stood in for windows: similar A1-A3 per m² (≈165 vs ≈160 aluminium), but less glass per m², so it understated glazing replacement (B4) | Confirmed (XW 16/10/2026) |
| D7 | Window service life follows the CWCT / ETPP approach, as for the curtain wall: frame, gaskets, brackets, flashings and lintel 60 years; DGU 30 years (PS Table 20 windows) | Confirmed (XW 16/10/2026) |
| D8 | Stainless steel (lintels) keeps the library factor (global average, CHECK) until a supplier EPD is chosen; ETPP used a lower ICE value (≈6 kgCO2e/m² of window difference) | Confirmed (XW 16/10/2026) |
| D9 | Plan reader rules: core walls = closed outlines or hatches 100–500 mm thick (length = area ÷ thickness, thickness from the outline); columns = circles 0.2–1.5 m, and squares and rectangles as closed polylines or blocks (each side 0.2–1.5 m, long side ≤ 3 × short side so wall stubs stay out; a rectangle enters the take-off as the square of the same area) - XW 22/10/2026; an office can limit this with `plan_reader.column_shapes`; stairs = tread rectangles grouped into flights as in the PDF extractor, read in the plan's own orientation; treads are never columns or walls, columns never walls. Only shapes inside the floor plate count (largest closed outline on the wall layer). The file's unit header is checked against the shapes - a DWG said millimetres for metre coordinates - and a correction is applied and reported | Confirmed (XW 16/10/2026) |
| D10 | Plan layers fill themselves: office name patterns first (`plan_layer_patterns` in the office settings), then the layer with the most walls / columns / treads. The designer checks the proposal and the highlighted objects, and changes a layer only if it is wrong | Confirmed (XW 16/10/2026) |
| D11 | Core walls measured on a plan are scaled to their measured thickness (m² of the 250 mm build-up × t / 0.25), with a warning to check the thickness with the engineer - until the library has a build-up per wall thickness. Applies to the PDF route too | Confirmed (XW 16/10/2026) |
| D12 | The window has seven steps: 1 Project & options, 2 Drawings & schedule, 3 Substructure, 4 Superstructure - Structure, 5 Superstructure - Façade, 6 Targets & reporting, 7 Run, then Results. Step 3 holds every substructure input per option (basement levels or the no-basement confirmation, ground level, basement wall basis / type / secant geometry / liner / perimeter, piles, caps or raft) with the U1-U8 defaults, and can copy one option's settings to all | Confirmed (XW 22/10/2026) |
| D15 | File paths saved with the model (schedule, plan, output folder, last workbook, logo, option models) are kept absolute and, when they lie in or under the model's folder, also relative to it. On opening, the output folder follows the model; an input file is taken from the model's folder when it is there, else from where it was - so a moved project folder keeps working and a .3dm copied on its own still finds its inputs | Confirmed (XW 26/10/2026) |
| D16 | New panel interface (from user feedback): React + Tailwind CSS + shadcn/ui components + Lucide icons, source in `rhino_ui/panel`, built into one self-contained page (`rhino_ui/web_next/index.html`, committed so packaging needs no Node.js; nothing loaded at runtime). Same messages to Python as the current page. Built alongside the current panel, which stays the default until the new one covers every step: shell and steps 1-2 first, then steps 3-5, then targets, run and results. Charts stay the hand-drawn SVG ones, restyled. Light / dark / follow Windows switch. Users move between the two with a link in each (remembered per PC). The new interface is the default once it covered every step; the current one stays available | Confirmed (XW 27/10/2026) |
| D14 | The WLCA page lives in a dockable Rhino panel (`WlcaPanel` in WLCA.rhp: one WebView; dock, tab or float it like the Layers panel). Modeless on purpose - a modal Eto.Dialog would block Rhino, and the workflow needs Rhino while the page is open (turning layers on, checking highlighted plan objects, the GIA curves). The panel follows the open model (state reloads on Open / New). Without the plug-in, the script opens the page in a floating Eto.Form | Confirmed (XW 23/10/2026) |
| D17 | Detailed models: step 2 lists every layer with 3D objects (not the massing) in a table - one or more lines per layer: RICS element, measure (volume, vertical / horizontal pieces, plan area, face area, share of the massing façade, count, ignore), build-up, factor and the derived group it replaces. Defaults come from the layer name (`RICS_<code>_…_<build-up>`), then the office pattern list (`modelled_layer_patterns`), else the layer is ignored and flagged as not mapped. User text `WLCA_BUILDUP=<code>` takes one object off on its own. Modelled rows replace the massing-derived rows of their group (floors, columns, beams, façade, …) per option - or, on lines set to "keep the larger", whichever side carries more A1-A3 (library factor per unit) is taken forward; edge beams default to keep the larger (XW 29/10/2026: early-stage assumptions stay conservative unless the user has specific inputs); allowances the model does not show (soffits, louvres, entrance doors, other roof elements) stay derived. Cores stay measured from the plan. Measured per object with Rhino's own area / volume / bounding box: top area = V / H, face = (A − 2V/H) / 2 - exact for prismatic pieces. Façade layers default to "share": the model sets what the façade is made of, the massing how much façade there is (developed brick / fin areas would overstate the wall build-ups); vision glass × 1.25 to the window opening | Proposed (29/10/2026) |
| D13 | One window only: the web window (`WLCA` command). The classic Eto dialog (`WLCAClassic`) is retired - every change had to be made twice. Its Rhino-side logic lives on in `rhino_ui/wlca_rhino.py`. Fallback if WebView2 is missing: none in the package (Rhino 8 needs WebView2 for its own panels) | Confirmed (XW 23/10/2026) |

## Frame systems, rebar rates and reporting precision (v0.9 take-off, library v0.11)

| # | Decision | Status |
|---|---|---|
| F1 | Frame systems: RC flat slab (as measured), PT flat slab (PT build-up, columns and edge beams as RC), and four PF Stage 1 frames per m² of floor (steel + composite deck, steel + CLT + topping, steel + CLT, glulam + CLT). PF table by bay size: up to 56.25 m² uses 6 × 7.5 m, larger uses 7.5 × 9 m. Beams and connections are in the floor build-up (reported to 2.1.2); RC columns and edge beams are replaced; cores, basement, lowest and podium slabs stay RC | Confirmed |
| F2 | Steel / timber column quantities scale with height: × (storeys + 1) / 9 relative to PF's ground + 7 building, never below 1; tagged [ASSUMED] for the engineer to check | Confirmed |
| F3 | Rebar and PT rates are the average of the sources that give a rate for the element: consultant rates (07/10/2026), PF Stage 1 Report 7.3, HTS Default Embodied Carbon Rates V4.0. Placeholders and proxies are not counted. PT strand is per m³ of slab | Confirmed |
| F4 | PF's C25/30 topping and deck concrete uses the C32/40 factor (no C25/30 in the library - slightly high) | Assumed |
| P1 | Building-level results are reported to 2 significant figures at RIBA 0-2 and 3 from RIBA 3 (PS 6.1.4): Results headline, Dashboard tiles, targets table, budget, Compare totals. Element-level figures stay as calculated. Pass / fail against targets is judged on the unrounded values | Confirmed |


## Operational energy and water (B6 / B7, calculation template)

| # | Decision | Status |
|---|---|---|
| O1 | B6 needs a predictive energy model (PS 5.3: CIBSE TM54 or equivalent, never Part L): annual kWh by fuel per option (grid electricity, gas, district heat, PV used on site, PV exported). Without one, the "Indicative" basis takes each option's EUI estimate, else the UKNZCBS EUI limit for the construction start year, × GIA as all-electric use, labelled "Indicative". Default: not assessed (embodied only) | Confirmed (XW 16/10/2026) |
| O2 | RICS factor set 1, both scenarios always reported (PS 4.11.4). Without decarbonisation: electricity = generation + T&D + WTT (generation and T&D) + infrastructure (0.020 + 0.0004); gas = combustion + WTT on net CV (as the RICS supplementary tables); latest DESNZ set. With decarbonisation: NESO FES most conservative pathway (FES 2025 "Falling Behind", successor to "Falling Short"), excl. BECCS, averaged over the RSP from the first year of operation and held at 2050 beyond (PS G2); upstream, T&D and gas WTT × energy decarbonisation factor (FES average / current generation factor); infrastructure × 0.5 (PS G4). District heat uses the network's factor in both scenarios | Confirmed (XW 16/10/2026) |
| O3 | B7 = water m³/yr × (supply + 90% × treatment) × RSP, and × the energy decarbonisation factor when decarbonised (PS 4.11.4, G4). Water from the public health engineer; without it, a budget = estimated occupancy (asked at project set-up) × RIBA 2030 Climate Challenge 2025 potable water target × occupied days (office 250, homes 365; schools per pupil per year), labelled indicative | Confirmed (XW 16/10/2026) |
| O4 | No contingency on B6 / B7 (the PS Table 10 contingency covers embodied carbon); whole life = A-C (incl. contingency) + B6 + B7. PV used on site counts in the EUI at zero carbon; PV exported is reported in D2 (memo) at the decarbonised grid factor | Confirmed (XW 16/10/2026) |
| O5 | Energy use intensity is compared with the UKNZCBS limit for the year construction starts (Table OE-1, New Building; offices "General", residential "Flats", schools "Secondary") and with the RIBA 2030 Climate Challenge 2025 / 2030 targets; water with the RIBA 2025 target | Confirmed (XW 16/10/2026) |
| O6 | Material decarbonisation (PS 4.11.5 Table 15) is reported alongside the non-decarbonised result: A1–A5, C3–C4 and biogenic unchanged; B2–B4 and C1–C2 × 0.5; D × 0.5 (memo). Contingency applies to both. Decarbonised whole life = decarbonised A–C + B6 / B7 on the FES grid. Labels: "Non-decarbonised" / "Decarbonised" | Confirmed (XW 16/10/2026) |
