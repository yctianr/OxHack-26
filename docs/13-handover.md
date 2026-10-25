# 13 · Handover — Spillcast (OxHack 2026)

Written Sun 25 Oct 2026, 01:25 BST (replaces the Sat 23:00 version). **Deadline: Sun 25 Oct, 16:00 GMT.** Clocks go back at 02:00 tonight, so 16:00 GMT is 16:00 on the clock. **Code freeze 14:00, submit 15:30.**

## What we're building

**Spillcast tells the Environment Agency which sewage works to inspect first.** The regulator has thousands of overflows and few inspectors. We screen the 53 Thames Water treatment works within 25 km of Oxford for two kinds of avoidable spill:

1. **Spilling while treating below the permit.** Works may only spill once they treat their full permitted flow (flow to full treatment, FFT).
2. **Spilling when the weather doesn't explain it.**

Avoidable discharges are the ones that harm rivers and wildlife for no reason. Target prize: **HRT "Best Use of Data for Predictions and Decision Making"**, judged by quants. Lead with the decision (where to inspect) and back it with honest, out-of-sample evidence.

**Use case decided Sun 00:45:** regulator decision 1, *which works to investigate*.

Not yet built, in priority order:
- **Decision 2:** which overflows to fix first, ranked by harm to wildlife.
- **Decision 3:** when to send a sampling team.

## Read in this order

1. **This file.**
2. [`README.md`](../README.md): how to run the website (no data needed) and how to rebuild everything.
3. [`docs/12-data-guide.md`](12-data-guide.md): every dataset, raw vs cleaned, how to rebuild.
4. [`docs/11-system-review.md`](11-system-review.md): the statistical model's audited results.
5. [`docs/10-model-v2-plan.md`](10-model-v2-plan.md): the decision log D1–D12. It predates the water balance and the watchlist; where they disagree, this file wins.

## State right now

### Done

**1. Data:** pulled, audited and cleaned (docs/12). Data is **not in git** (about 460 MB); see "Gotchas".

**2. Statistical model** (`scripts/model/1–7`): per-overflow logistic "bathtub" on Farmoor flow plus a rain store. Two folds (A: test WY2025; B: test Oct 2025 to 22 Oct 2026).

| Task | Result |
|---|---|
| **Explain** (given the rain that fell) | Brier 0.050 / 0.045, AUC 0.97–0.98; ties gradient boosting |
| **Forecast** (from 00:00, no rain forecast) | Brier 0.032 / 0.029; beats persistence by 7–8%, significant; ties gradient boosting |
| **Onset days** | AUC 0.90, but only ~15% caught confidently without a rain forecast |
| **Yearly spill-hours per site** | Weak: median error 35% |

**3. Water balance** (`scripts/model/8–10`, `wb.py`): first-principles model of each works with measured daily treated flow (52 works). Hour by hour, in m³:

```
inflow  = foul (±30% daily pattern) + groundwater infiltration + runoff from hard area + runoff from saturated ground
treated = min(inflow, capacity)
storm tank fills first; spill once the tank is full
```

- **Capacity** = 95th percentile of the works' daily treated flow. Checked against the spill record (not fitted to it): it matches treated flow on all-day spill days to about 6%.
- **Fitting** uses treated flow only. Days at capacity are censored.
- **Physics-only:** spills come out of the simulation. Optionally, one learned number per works sets where the overflow starts.

| Water balance (49 works, both folds) | Physics only | + 1 learned number | Statistical model |
|---|---|---|---|
| Skill vs climatology, A / B | 0.33 / 0.47 | 0.49 / 0.59 | 0.54 / 0.59 |
| AUC (median per site) | 0.95 | 0.97 | 0.97–0.98 |
| Spill-hours per site-year: bias / typical error | −28% / 58% | +22% / 45% | −6% / 35% |

Its fitted numbers mean what they claim, checked against independent published figures:
- **Foul flow:** about 166 L/person/day.
- **Peak infiltration vs Thames Water's maximum allowance:** median ratio 1.01, size-free Spearman 0.62.
- **Storm-tank rule (2 h at capacity):** matches the two works with known tanks. Witney: model 2,067 m³ vs actual 2,201. Church Hanborough: 422 vs 359.

Why physics alone undercounts: treated flow stops rising at capacity, so the meter never shows how far inflow went over it. That excess sets spill duration. Hourly flow data (not public) would fix it. Full diagnosis and ablation table in the conversation summary below ("Water-balance findings").

**4. Flow-data audit** (`8_wb_prep.py`, written to `data/interim/wb_works.csv`):

| Verdict | Works |
|---|---|
| Good | 40 |
| Groundwater-led | 3 (Cholsey, Dorchester, South Moreton) |
| No published capacity | 2 (Tackley, Worminghall) |
| **"Check"** | 7 (Appleton, Bletchingdon, Chadlington, Drayton, Middle Barton, Shabbington, Watlington) |
| Dropped | 1 (Middleton Stoney, 26% coverage) |
| No treated-flow data | 8 network sites, excluded |

The "check" works often report spilling while treating well below capacity.

**5. Regulator watchlist** (`scripts/web/watchlist.py`, written to `web/watchlist/data.json`):
- **Lead A:** days spilling 20+ h with daily treated flow **under 80% of FFT**. The permit test is 95% of readings above 92% of FFT; 80% leaves a margin for outlet metering and daily averaging.
- **Lead B:** spill days (≥1 h) in Oct 2024 to Oct 2026 that **both** models give under 5% chance.
- **Thresholds:** strong = ≥10 all-day spill days with 30%+ under the screen, or ≥10 unexplained days. Moderate = 5+ days under, or 3+ unexplained.
- **Result:** 6 strong leads (**Appleton, Shabbington, Drayton, Horton-cum-Studley, Watlington, Cholsey**) and 13 moderate. In total: 335 all-day spill days under 80% of FFT, 75 unexplained spill days, and 7 leads where Thames Water reported no investigation in 2025.
- **Clearest case: Shabbington.** It treated a median 22% of FFT on 52 of 54 all-day spill days.

**6. Website** (`web/`, on `main`):
- **Layout:** 3D deck.gl map plus panel.
- **"Inspect works" tab (default):**
  - **Map:** works coloured by lead strength. The selected works' river route glows, with particles along it.
  - **Evidence file:** findings; treated flow vs FFT chart; lowest-treatment dates; unexplained dates; Thames Water's stated reason and investigation status; records to request (MON4 flow, MON3 overflow, tank logs); "Copy case summary".
- **"Spills by day" tab:** the original forecast / explain / observed views.
- **Tested** from a fresh clone in headless Chrome.
- **Run:** `python3 -m http.server 8000 -d web`.

**7. Research done.** The findings support the watchlist and the limits we state:
- **[Thames Water FFT methodology](https://www.thameswater.co.uk/media-library/os3lcdg4/treatment-works-compliance-fft.pdf):**
  - Works come in two layouts: storm tanks after FFT (FFT ≈ 3× dry-weather flow), or an inlet overflow only (≈ 6× DWF).
  - Compliance rule: 95% of readings above 92% of FFT while discharging.
  - MON3/MON4 monitors are being installed 2020–2030.
- **Ofwat:** over two-thirds of Thames Water works with FFT permits had capacity or operational issues; ~£168m in fines proposed across three companies.
- **[Hammond et al. 2021](https://www.nature.com/articles/s41545-021-00108-3):** 15-minute effluent flow via EIR. Their WWTP1/WWTP2 match Church Hanborough (50.52 L/s) and Witney (240 L/s), and WWTP1 spilled well below its permitted pass-forward flow.
- **Wallingford runoff equation:** its use of soil moisture deficit supports our wet-ground runoff term.

### Not done

- **Hosting:** the site is only local or in git.
- **Harm ranking** (decision 2).
- **Live test** on the 23–24 Oct storm.
- **Rain forecasts** for the forecast mode.
- **Write-up and video.**

## Do these next, in order

| When | Task |
|---|---|
| **First thing** | **Host the site.** Fastest: drag `web/` onto <https://app.netlify.com/drop>, rename to `spillcast.netlify.app`. Optional custom domain `spillcast.org` (looked available on 25 Oct; buy through Netlify so DNS and HTTPS are automatic). GitHub Pages needs Rain (repo owner) to enable it, with Pro or a public repo, plus a workflow serving `web/`. |
| 08:00–09:30 | **Live test.** Extend the data to 24 Oct and score the 23–24 Oct spills with the frozen models (see gotchas: hard-coded end dates). The strongest single slide for quant judges. |
| 09:30–11:30 | **Harm ranking (decision 2).** Spill volume or hours ÷ river flow on the day (EA gauges) × sensitivity (Natural England SSSI/SAC, chalk streams; Oxford Meadows SAC). **Check first** whether EA open water-quality samples (ammonia, dissolved oxygen) near our outfalls can validate it; if yes, that is the headline evidence. |
| 11:30–13:30 | Polish the site and add an "Evidence" view: backtest table, calibration, physics checks, Witney/Church Hanborough tank check. Optionally pull FFT and tank volumes from EA permits for the big works (Oxford, Witney, Bicester, Abingdon, Didcot). |
| 14:00 | **Code freeze** |
| 14:00–15:30 | Write-up and 2-minute video: the inspector's decision → the evidence → honest limits |

**Never cut:** the watchlist, the backtest table, the stated limits.

**Cut first:** decision 3 (alerts), rain forecasts, particles.

## Decisions made (don't re-litigate without new evidence)

- **Audience is the regulator** (EA for inspection, Ofwat for enforcement), framed around avoidable harm to rivers and wildlife. Say "risk to wildlife"; we predict spills and dilution, not water quality.
- **Leads are "leads to check", never "illegal" or "breach".** Daily outlet volume vs published FFT is a screen; the operator's MON4/MON3 records settle it.
- **Statistical model is the predictor; the water balance is the physical explanation and what-if engine.** The water balance doesn't beat the statistical model at prediction. Present that honestly.
- **Water balance only where treated flow is measured.** Network overflows are excluded from it.
- **Capacity = 95th percentile of treated flow**, not the published FFT (13% typical error) or the 99th percentile (18% high).
- **The learned "spill start" fraction (median 0.68 of capacity) is not a finding.** It is too uniform across works and likely absorbs the model's missing hourly peaks. Don't claim "works spill at 68% of capacity" from it.
- **Statistical model decisions** from the previous handover still stand: one Farmoor gauge, two-gauge rain mix, Explain and Forecast scored separately, what-ifs as relative change, the rejected-variants list.

## Open questions for the team

- **HRT prompt wording and judging criteria:** does it name a decision-maker? Does submission need a public repo?
- **ORIC capacity sheet licence:** still not checked. The site shows FFT figures from it. Check before publicising widely.
- **Teammates' work on `main`:** `UI-first-draft.html` and `Documentation.txt` (Keira), `tdv_datasets/` and `edm_datasets/` (Rain). Does any of it belong in the site?
- **Site list:** `docs/10-list-of-discharge-points` names ~22 overflows; the watchlist covers 53 works.

## Gotchas found the hard way

Still true from before:
- **Setup:** system Python has no pandas. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (now includes numba and openpyxl). Run scripts from the repo root.
- **Data isn't in git** (~460 MB; the OS Open Rivers file alone is 113 MB, over GitHub's per-file limit). Rebuild with the README's "Rebuild everything".
  - **Different file layout from Rain's commits.** Rain's committed `tdv_datasets/raw/` and `edm_datasets/` use other file names than our scripts expect: `data/raw/tdv/tdv{YEAR}.xlsx` and `data/raw/annual_returns/tw_edm_{YEAR}.xlsx`, the latter a Thames Water-only sheet with headers on row 5.
- **Hard-coded end date:**
  - `4_build_clean.py` builds hours to **2026-10-22 23:00**.
  - `common.py` fold B ends 2026-10-23.
  - `8_wb_prep.py` fetches evaporation to 2026-10-22.

  Move all three to score the 23–24 Oct storm, after re-running `fetch_data.py thames-alerts`, `events` and `1_fetch_gauges.py`.
- **Thames Water API, EA "water day", EA Suspect flags, Thames Water Excel quirks, Open-Meteo 429s:** see the gotchas in docs/12; they still apply.

New:
- **`9_wb_fit.py`** fits 52 works × 2 folds in parallel (8 processes, ~75 s).
  - **Experiment switches** by environment variable: `WB_CAP_Q` (capacity quantile, default 0.95), `WB_SAT` (wet-ground runoff, 1), `WB_TANK_H` (tank hours, 2), `WB_PUMP_H` (pump-back limit, off), `WB_OUT` (output suffix).
  - **Ablation outputs** are in `data/interim/wb_predictions_abl_*.pkl`.
- **Run order matters:** `10_wb_evaluate.py` writes `wb_eval_rows.pkl`, which `scripts/web/watchlist.py` needs. Order: 5 → 8 → 9 → 10 → `scripts/web/watchlist.py`.
- **Daily treated volume (TDV) is outlet effluent; FFT applies at the inlet.** Compare with a margin, which is why the screen uses 80%.
- **Annual return columns** worth knowing: "Storm Discharge Asset Type" (storm tank vs inlet overflow), "High Spill Frequency … reason", "Investigation activity", "Improvement activity".
- **Testing the site:** this machine has no Node or `gh`. Headless Chrome works:

  ```
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --virtual-time-budget=20000 --dump-dom http://localhost:8000/
  ```

  Swap `--dump-dom` for `--screenshot=shot.png` to get an image.
- **The page needs a server** (`file://` blocks its data fetches) and internet (CDN libraries).
- **Git:**
  - Commits go as `yuyaox122 <yuyaoxie122@gmail.com>`, no trailers. This repo's local git config says otherwise, so pass `-c user.name -c user.email`.
  - `main` now contains the `model-v2` pipeline again: it came back with the `water-balance` merge. `water-balance` and `model-v2` are merged; continue on `main`.
- **Stray artifact:** a superseded, private claude.ai copy of the watchlist exists at <https://claude.ai/artifact/HB7hKw6z9c9mXpUQYGRhU2>. Not the product; delete it if unwanted.

## Water-balance findings (for the write-up)

Why the first physics-only version predicted 88% too few spill-hours, and what fixed it. Skill is fold A / B. No spill records were used in any of these.

| Version | Skill | AUC | Spill-hours bias |
|---|---|---|---|
| Capacity = 99th percentile, no wet-ground runoff | 0.16 / 0.21 | 0.87 | −88% |
| + capacity = 95th percentile | 0.31 / 0.44 | 0.94 | −39% |
| + wet-ground runoff only | 0.19 / 0.25 | 0.88 | −80% |
| Both (current) | 0.33 / 0.47 | 0.95 | −28% |
| Both, no storm tank | 0.36 / 0.39 | 0.96 | +6% |
| Both, 12 h pump-back limit | 0.34 / 0.45 | 0.94 | −28% |

Causes, in order of size:
1. **Capacity set too high.** On all-day spill days works treat ~85% of their busiest-day flow, so spill days were wrongly fitted as exact readings and inflow got pinned at capacity.
2. **Missing wet-ground runoff:** high flows ran 9% low.
3. **The unobservable excess above capacity**, which the storm tank then swallows. This last one needs hourly flow to fix.

## Links

- Research brief (claude.ai doc, private to the owner): https://claude.ai/artifact/AK3Sppr7ikgc2M8AFm3fjc
- Repo: `git@github.com:yctianr/OxHack-26.git` (private; Rain owns it)
