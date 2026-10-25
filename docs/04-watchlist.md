# 04 · Regulator watchlist (decision 1: which works to inspect)

The watchlist screens 53 Thames Water treatment works around Oxford for spills that shouldn't have happened, and ranks them for inspection. Result: **7 strong leads and 12 moderate**; 7 of the leads had no Thames Water investigation in its 2025 return.

Code: `scripts/web/watchlist.py` → `web/watchlist/data.json`, shown on the website's "Inspect works" tab ([06-website.md](06-website.md)).

## Two tests

| Test | Rule | Data | Window |
| --- | --- | --- | --- |
| **A. Spilling below the permit** | Days spilling 20+ hours when the works' daily treated flow was under **80% of its permitted flow** (FFT). The permit requires 95% of readings above 92% of FFT while spilling; 80% leaves room for outlet metering and daily averaging | Thames Water EDM alerts (hours spilled), Thames Water treated volume, ORIC permitted flow | Apr 2022 – Dec 2025 (treated volume ends there) |
| **B. Spills the weather doesn't explain** | Days with 1+ hour of spilling that **both** the physics water balance and the statistical backup gave under 5% chance, given the rain that fell and how wet the ground was | Both models' held-out predictions ([02](02-physical-model.md), [03](03-statistical-model.md)); EDM alerts | Oct 2024 – Oct 2026 (the two test years) |

Test B uses the physics model with spilling only at full capacity, so no spill record shapes it. Requiring the statistical model to agree guards against the physics model's known undercount of spills.

**Lead strength:** strong = 10+ all-day spill days with 30%+ of them under the screen, or 10+ unexplained days. Moderate = 5+ days under the screen, or 3+ unexplained.

## Current leads

| Works | Level | All-day spill days under 80% of FFT | Median treatment on all-day spill days | Unexplained spill days | Flow-data audit | Thames Water investigation (2025) |
| --- | --- | --- | --- | --- | --- | --- |
| Appleton | strong | 86 of 125 | 75% of FFT | 0 | check | none |
| Drayton | strong | 44 of 142 | 83% | 18 | check | none |
| Shabbington | strong | 52 of 54 | 22% | 6 | check | none |
| Horton-cum-Studley | strong | 1 of 50 | 115% | 13 | good | yes |
| Church Hanborough | strong | 2 of 113 | 104% | 10 | good | yes |
| Watlington | strong | 9 of 15 | 78% | 1 | check | yes |
| Cholsey | strong | 5 of 12 | 98% | 0 | groundwater-led | none |

Moderate: Combe, Bletchingdon, Chadlington, South Moreton, Bampton, Wheatley, Oxford, Middle Barton, Little Milton, Benson, Haddenham, Grendon Underwood. Totals: 335 all-day spill days under 80% of FFT; 91 unexplained spill days.

- **Clearest case: Shabbington** (population about 530) treated a median 22% of its permitted 2.8 L/s on 52 of its 54 all-day spill days. Thames Water's own return lists 3.6 L/s as the flow it should treat.
- **Church Hanborough** is independently supported: Hammond et al. 2021 (its "WWTP1", identified by its 50.52 L/s permitted flow) found it spilling well below its permitted pass-forward flow in 2009–2020.
- **Read the flow audit column.** 4 of the 7 strong leads are works whose treated-flow data the audit marks "check" ([05-data.md §2.2](05-data.md#22-treated-flow-scriptsmodel8_wb_preppy)): for them a faulty meter and real under-treatment look the same. Either way the works is worth inspecting; say so when presenting it.

## What to request for each lead

The website's evidence file lists the dates and offers a "Copy case summary". For a lead under Test A: the 15-minute flow-to-full-treatment records (MON4) for the listed dates, and storm-tank level and pump-back logs. For Test B: raw spill-monitor (MON3) signals and alarm logs for the unexplained dates, and any blockage or pump-failure reports.

## Limits

- **A lead is a reason to look, not evidence of a breach.** Treated volume is measured at the outlet and averaged over the day; the permit applies at the inlet to 15-minute readings.
- **Permitted flows come from the ORIC sheet,** whose licence is still unchecked.
- **Network and pumping-station overflows aren't screened:** they have no treated-flow data.
- **Test B depends on both models.** The physics model undercounts spills overall, which on its own would inflate unexplained days; the statistical model must also call the day very unlikely.
