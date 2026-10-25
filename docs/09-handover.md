# 09 · Handover: state, decisions, next steps

Updated Sun 25 Oct 2026, ~10:00 GMT. **Code freeze 14:00, submit 15:30, deadline 16:00 GMT.** Read [01-overview.md](01-overview.md) first for what Spillcast is; this file is what a teammate needs to pick up the work.

## State

| Part | Status | Doc |
| --- | --- | --- |
| Data: pulled, audited, cleaned (not in git) | Done | [05-data.md](05-data.md) |
| **Physics water balance (main model)**: 52 works, fitted to treated flow only, sourced storm tanks at 5 works | Done | [02-physical-model.md](02-physical-model.md) |
| Statistical model (backup): 52 overflows, explain + forecast | Done | [03-statistical-model.md](03-statistical-model.md) |
| Regulator watchlist (decision 1) | Done | [04-watchlist.md](04-watchlist.md) |
| Website: watchlist, daily views of both models, rain-scenario page with the physics model running in the browser | Done, local only | [06-website.md](06-website.md) |
| Hosting | **Not done** | below |
| Live test on the 23–24 Oct storm: data now runs to 24 Oct | Done | [02 §Live test](02-physical-model.md#live-test-the-2324-oct-storm) |
| 7-day physics forecast from the ECMWF ensemble (issued 25 Oct, 10:45 UTC), on both pages | Done | [02 §Forecast](02-physical-model.md#forecast) |
| Harm ranking (decision 2) | **Not done** | below |
| Write-up and video | **Not done** | below |

## Do these next, in order

| When | Task |
| --- | --- |
| Now | **Host the site.** Drag `web/` onto <https://app.netlify.com/drop>, rename to `spillcast.netlify.app`. Check the two licence questions below first. |
| Before hosting | **Refresh the forecast** if time has passed since 10:45 UTC: README, "Refresh the forecast" (about 25 minutes).
| Before 13:30 | **Harm ranking (decision 2).** The physics model's spill volume ÷ river flow that day (EA gauges) × sensitivity (SSSI/SAC, chalk streams, Oxford Meadows SAC). Notes and cost figures: `docs/archive/05-decisions-and-costs.md` in git history (commit 2920dab). Check first whether EA water-quality samples near the outfalls can validate it. |
| 14:00 | **Code freeze** |
| 14:00–15:30 | Write-up and 2-minute video: the inspector's decision → the physics → the evidence → honest limits |

**Never cut:** the watchlist, the scores table, the stated limits. **Cut first:** alerts (decision 3), rain forecasts, particles.

## Decisions (don't re-litigate without new evidence)

- **The physics water balance is the main model; the statistical model is the backup** (25 Oct). Physics is fitted only to treated flow and never sees a spill record, so it can judge whether a works spills when it shouldn't. The statistical model predicts spill days slightly better (skill 0.59 vs 0.47) because it learns from spill records; it covers overflows with no treated-flow data and gives the forecast.
- **Physics stays first-principles.** No knob tuned to spill records: the learned "spill start" was dropped ([02 §Why no learned spill start](02-physical-model.md#why-no-learned-spill-start)). Any new parameter needs a physical source; unsourced numbers are open questions.
- **Storm tanks:** a sourced volume where one exists (`scripts/model/tanks.csv`), else 2 hours at capacity.
- **Capacity = 95th percentile of the works' own treated flow**, not the published FFT (13% typical error) or the 99th percentile (18% high).
- **Audience is the regulator** (EA for inspection, Ofwat for enforcement), framed as avoidable harm to rivers and wildlife. Say "risk to wildlife": we model spills and dilution, not water quality.
- **Leads are "leads to check", never "illegal" or "breach".** The operator's MON4/MON3 records settle them.
- **Spill volumes rank works; they are not amounts.** No public data measures them.

## Open questions

- **ORIC capacity sheet licence:** still unchecked; the site shows FFT and population from it.
- **Thames Water terms:** `web/watchlist/data.json` republishes daily treated flow per works. If in doubt, cut the chart to spill days only.
- **HRT judging criteria:** does submission need a public repo?
- **Pitch framing:** watchlist (decision 1) first, then harm and spread (decision 2), as in [01-overview.md](01-overview.md). Agree before the write-up.
- **Storm tanks for the other 48 works:** an EIR request to Thames Water (EIR.Requests@thameswater.co.uk); replies take about 2 months.

## Gotchas

- **Setup:** system Python has no pandas. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`. Run every script from the repo root.
- **Data isn't in git** (~460 MB). Rebuild with the README; hand-download list in [05-data.md](05-data.md#rebuilding-the-data).
- **One end date:** `DATA_END` in `scripts/model/common.py` (now 2026-10-24 23:00 UTC) drives the clean data, fold B and the evaporation download; the forecast starts the hour after. Rain is available to the current hour, but EA river flow lags a day.
- **Run order:** 4 → 5 → 8 → 9 → 10 → 11 → `scripts/web/` (`data.py` before `whatif.py` and `physics.py`; `10` before `watchlist.py` and `build_stats.py`).
- **`9_wb_fit.py`** fits 52 works × 2 folds on 8 processes, about 5 minutes. Run it in the foreground or as a tracked background job; a bare `&` from a tool shell stalled once. Experiment switches by environment variable: `WB_CAP_Q`, `WB_SAT`, `WB_TANK_H`, `WB_PUMP_H`, `WB_TAU_FAST_MAX`, `WB_OUT`. Ablation outputs: `data/interim/wb_*_abl_*`.
- **Physics-only outputs are the `wb1_*` columns;** `wb_*` is the dropped learned-threshold version, kept as a diagnostic.
- **Treated volume is outlet effluent; FFT applies at the inlet.** Hence the 80% screen.
- **Testing the site:** no Node or `gh` on this machine; use headless Chrome ([06-website.md](06-website.md)).
- **Git:** commit as `yuyaox122 <yuyaoxie122@gmail.com>`, no trailers (the repo's local config says otherwise, so pass `-c user.name -c user.email`). Work on `main`. Add `.DS_Store` to `.gitignore`.
- **Stray artifact:** a superseded private claude.ai copy of the watchlist at <https://claude.ai/artifact/HB7hKw6z9c9mXpUQYGRhU2>; delete if unwanted. The model explainer doc is at <https://claude.ai/artifact/4GWAhdMWuv4NxAc3PZoZVj>.
