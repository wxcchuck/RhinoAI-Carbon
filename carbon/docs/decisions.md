# Decisions log: massing take-off

Methodology decisions behind `takeoff/`. **Confirmed** means agreed by the office WLCA lead.
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
| U8 | Pile caps / raft | Open |
| U9 | Basement larger than the ground footprint: scale the perimeter? (the script warns) | Open |
