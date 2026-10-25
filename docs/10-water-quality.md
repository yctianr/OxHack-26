# 10 · Water quality: is the river safe to swim in, and safe for fish?

The river page (`web/river.html`) estimates **E. coli** and **ammonia** every 100 m of river around Oxford, for every day of the test year and the 7-day forecast. Concentrations are what the river carries **while a sewage spill upstream passes**. They come from the physics model's spills, typical concentrations in storm sewage, dilution by the day's river flow, and decay on the way downstream. They are model estimates, not measurements.

Code: `scripts/web/quality.py` → `web/data/quality.json`; the page does the arithmetic for the chosen day.

In the page's **My scenario** mode the spill days and rates come from the physics model rerun in the browser (`web/data/physics.json`) with your rainfall, storm-tank and capacity changes: a works counts as spilling at a 50%+ chance, at its modelled volume ÷ spill-hours.

## Method

```
C(segment, day) = background + Σ over works upstream that spill that day of  c0 · r / (Q + r) · exp(−k · t)
```

| Term | What it is | Where it comes from |
| --- | --- | --- |
| Spill day | Did the works spill? | Past days: its spill monitor (Thames Water EDM). Forecast days, and past days with no usable monitor record: the physics model's chance ≥ 50% |
| r | Spill rate (m³/s) | The works' typical rate in the physics model: modelled spill volume ÷ modelled spill-hours over the test year. Works the model never spills: 0.37 × capacity, the median ratio |
| Q | River flow at the segment that day (m³/s) | On the Thames, Cherwell, Evenlode, Thame, Ock and Glyme: the nearest EA gauge. Elsewhere: the gauges' median runoff per km² that day × the segment's catchment area, estimated as 1.99 km² per km of river upstream (calibrated on the Glyme, Ock and Ewelme gauges). Forecast days hold the last reading |
| t | Travel time from the works (h) | River distance along OS Open Rivers ÷ 0.5 m/s, up to 40 km |
| k | First-order loss (per day) | E. coli: die-off; ammonia: nitrification |
| c0 | Concentration in the spill | Below |

The river is cut into 17,996 segments of 100 m; 3,928 lie within 40 km downstream of a works. Mixing is assumed complete and steady over the spill.

## Parameters and sources

| Parameter | Value | Source |
| --- | --- | --- |
| E. coli in storm overflow spills | 1.5 × 10⁶ per 100 mL | [Passerat et al. 2011](https://pubmed.ncbi.nlm.nih.gov/20934197/), Water Research 45:893 (Seine; measured mean); range 4.6–7.3 log10 |
| Ammonia in storm overflow spills | 4 mg N/L | **Derived:** crude sewage ~39 mg N/L ([GOV.UK typical concentrations](https://www.gov.uk/government/publications/values-for-groundwater-risk-assessments/septic-tank-and-package-treatment-plants-liquid-effluent-pollutants-and-typical-concentrations)) diluted ~10× by runoff (Passerat: 89% of CSO discharge was surface runoff). No measured UK value found |
| E. coli die-off | 0.5 /day Oct–Mar, 1.1 /day Apr–Sep | [Servais et al. 2007](https://hess.copernicus.org/articles/11/1581/2007/), HESS 11:1581 (temperature dependent; Seine 0.19–0.81 /day) |
| Ammonia loss | 0.3 /day | **Judgement** within [Pauer & Auer 2009](https://digitalcommons.mtu.edu/michigantech-p/6309) (~0.1–1 /day for 1 m depth) |
| Background ammonia | 0.04 mg N/L | [Bowes et al. 2018](https://essd.copernicus.org/articles/10/1637/2018/), ESSD 10:1637, Table 3 (Cherwell 0.031, Thames at Swinford 0.039) |
| Background E. coli | 300 per 100 mL | **Order of magnitude only:** Servais 2007 (100–1,000 in small streams); EA samples at Wolvercote Mill Stream, June 2022 (news report) |
| Travel speed | 0.5 m/s | EA time-of-travel database ([Guymer, Warwick](https://www2.warwick.ac.uk/fac/sci/eng/research/grouplist/water/events/britcouncildyetracing/2_mixing_in_rivers.pdf)): mostly 0.05–0.5 m/s, rising with flow; spills happen at high flow |

## Advice on hover

| Label | Rule | Basis |
| --- | --- | --- |
| Safe for swimmers / Take care / Not safe to swim | E. coli ≤ 500 / ≤ 1,000 / above, per 100 mL | [Bathing Water Regulations 2013](https://www.legislation.gov.uk/uksi/2013/1675/schedule/5/made), inland waters: Excellent 500, Good 1,000 |
| Safe for fish / Stressful for sensitive fish / Harmful to fish | Total ammonia ≤ 0.6 / ≤ 1.1 / above, mg N/L | [WFD Standards Directions 2015](https://www.legislation.gov.uk/uksi/2015/1623), lowland high-alkalinity rivers (the Cherwell is Type 7): Good 0.6, Moderate 1.1 |

## Limits

- **The standards judge a season, not a day.** Bathing-water classes are 95th percentiles of many samples, and WFD ammonia is an annual 90th percentile; here they are used as daily reference levels.
- **Toxicity to fish depends on un-ionised ammonia,** which needs pH and temperature. Total ammonia alone is conservative in winter, when far more total ammonia is needed to harm fish.
- **Only storm spills are counted.** The continuous treated effluent from each works, a big source of ammonia in dry weather, is not included, nor are farm runoff and misconnections.
- **E. coli can grow for up to a day before it decays** (UKWIR 2026), so simple decay may understate it near the outfall.
- **Flow on forecast days is held at the last EA reading,** which understates dilution while rivers are rising after a storm.
- **Network and pumping-station overflows** (8 of 61, including the city's Botley and North Hinksey overflows) have no spill rate, so they add nothing.
- **Spill rates come from the physics model,** whose spill volumes no public data can check.
