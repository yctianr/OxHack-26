# 05 · Decision outputs and cost assumptions

Every £ figure is an order-of-magnitude assumption. Show it with a slider, not as a quote.

## 1. Swim at Port Meadow (daily)

- **Signal:** P(any upstream overflow spills in the last 48 h or the next 24 h), weighting upstream sites by river distance or travel time.
- **Rule:** flag "avoid" when p > c_FA / (c_FA + c_miss). If a missed warning costs 10× a false alarm, the threshold is **p > 0.09**.
- **Present it** as tier word + number + frequency: "Avoid · about 4 in 10 days like today", plus a 10-icon row, the main reason and one action.
- **Evaluate** against E. coli > 900 cfu/100 ml samples (May–Sep 2023–26) vs the EA STP flag.

## 2. Storage vs sealing (per site; rigorous only at Oxford STW)

Replay 2022–26 weather through the fitted bucket model under each intervention and report **Δ spill-hours per year per £m** (and Δ volume at Oxford STW).

- **Storage, +V m³:** within an event, a spill starts only after the cumulative excess Σ(Q − C) exceeds V. This needs Q in m³, so only Oxford STW with TDV is rigorous.
- **Sealing:** cut the infiltration coefficient `a` by a fraction f.
  - Southern Water's evidence: sealing public sewers helps at low groundwater. Sealing **public + private** let groundwater rise about 3 m more before the system filled, halving risk from 8 in 12 years to 4 in 12.
  - Scenarios: f = 0.3 (public only) and 0.6 (public + private).

| Lever | Unit cost | Basis | Confidence |
| --- | --- | --- | --- |
| Storm tank at a works | **£1,850–2,100 /m³** | [Ofwat PR24 FD enhancement appendix](https://www.ofwat.gov.uk/wp-content/uploads/2024/12/PR24-final-determinations-Expenditure-allowances-Enhancement-cost-modelling-appendix.pdf), Table 2: STW grey storage £1,853 (DD forecast), £2,103 (FD forecast), £1,941 (historical) | Good |
| Network storage | **£2,550–2,935 /m³** | Same table | Good |
| Sewer sealing / lining | **About £100k–250k /km (assumption)** | [Southern Water SRN-DDR-050](https://www.southernwater.co.uk/media/ty4hzpov/srn-ddr-050-resilience-infiltration-enhancement-cost-evidence-case.pdf) redacts its unit rates. Its £38.9m programme with 177.4 km by the "innovative" method implies roughly £175k/km blended (our derivation). Trade CIPP prices run £80–250/m. | Low |
| Oxford STW upgrade | **> £270m, due 2032** (FFT 1,040 → 1,434 l/s; storm tanks 6,831 → 18,167 m³, tank figures unverified) | [Thames Water site page](https://www.thameswater.co.uk/about-us/performance/river-health/frequently-asked-questions/information-about-specific-sites); the GISMP's £130m is out of date | Good. Use it as the "status quo plan" comparator ([docs/10 §3.4](10-model-v2-plan.md#34-layer-4--placement)). |

Scale check: 10,000 m³ of extra storage ≈ £20m. Sealing 20% of the 1,485 km network (about 300 km) ≈ £30–75m.

## 3. Unexplained spills

See [04 §Unexplained-spill detector](04-modelling-plan.md#unexplained-spill-detector). Frame them as leads for the EA or Thames Water to check.

## Targets (Storm Overflows Discharge Reduction Plan, 2022)

Summary via [UNEP LEAP](https://leap.unep.org/en/countries/gb/national-legislation/storm-overflows-discharge-reduction-plan); verify the current status on gov.uk.

- **By 2035:** improve all overflows discharging to or near designated bathing waters, and 75% of those discharging to high-priority sites.
- **By 2050:** no overflow above an average of **10 rainfall-driven spills a year**.
- Dry-weather operation is already "unsatisfactory" under the [EA permit guidance](https://www.gov.uk/government/publications/water-companies-environmental-permits-for-storm-overflows-and-emergency-overflows/water-companies-environmental-permits-for-storm-overflows-and-emergency-overflows). Planned discharges from groundwater-surcharged sewers are normally refused.
- **Policy hook:** the 10-spill target counts *rainfall* events, so groundwater-driven spills are exactly the ones that won't be allowed. Headline each site with "spills/yr vs 10" and the "% explained by rain vs infiltration".

## Harm weighting (simple and visible)

harm = spill-hours × receptor weight:

- **3:** a designated bathing water, or upstream of one within 24 h travel.
- **2:** a chalk stream or SSSI/SAC (high-priority sites in the plan).
- **1:** everything else.

Let judges change the weights live.
