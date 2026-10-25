# 01 · Overview

**Spillcast tells the Environment Agency which sewage works to inspect first.** It models every Thames Water treatment works within 25 km of Oxford from first principles, and flags the ones that spill sewage when the physics says they shouldn't.

Built at OxHack 2026 for the HRT prize "Best Use of Data for Predictions and Decision Making".

## The problem

Sewage works may discharge untreated sewage into rivers only in storms, and only once they are treating their full permitted flow (flow to full treatment, FFT). The regulator has thousands of overflows and few inspectors, and the spill monitors only say *that* a works spilled, not whether it had to. Avoidable spills harm rivers and wildlife for no reason.

## What Spillcast does

1. **Physics water balance of each works (main model).** Hour by hour: sewage, rain runoff and groundwater flow in; the works treats up to its capacity; a storm tank holds the excess; only what the tank can't hold spills. Fitted only to each works' daily treated flow, never to spill records, so it is an independent judge of when a works should spill. → [02-physical-model.md](02-physical-model.md)
2. **Statistical model (backup).** A per-overflow model of rain and wet ground, fitted to spill records. It covers overflows with no treated-flow data, gives a next-day forecast, and is the second opinion on unexplained spills. → [03-statistical-model.md](03-statistical-model.md)
3. **Regulator watchlist (decision 1).** Two tests per works: spilling all day while treating under 80% of the permitted flow, and spills that both models say the weather doesn't explain. → [04-watchlist.md](04-watchlist.md)
4. **Website.** A 3D map of the rivers and works: the watchlist with an evidence file per works, daily views of both models, and a rain-scenario page that reruns the physics model in the browser. → [06-website.md](06-website.md)

## Headline results

- **Physics works without seeing a spill record:** on the held-out year (Oct 2025 – Oct 2026) it ranks spill days with a median AUC of 0.96 per works, against 0.98 for the statistical model fitted to spills.
- **Its numbers mean what they say:** fitted foul flow is 163 litres per person per day; fitted capacity is within 7% of the published permitted flow; peak infiltration matches Thames Water's own allowance (median ratio 1.07); the standard 2-hour storm-tank rule is within 6–18% of the real tanks at the 4 works where we found them.
- **The watchlist:** see [04-watchlist.md](04-watchlist.md) for the current leads. Clearest case: Shabbington treated a median 22% of its permitted flow on 52 of its 54 all-day spill days.
- **Honest limits:** physics undercounts spill-hours by 30% because daily treated flow can't show the peaks above capacity; spill volumes rank works but can't be checked; leads are reasons to look, not proof of a breach.

## Where things are

| Doc | Read it for |
| --- | --- |
| [02-physical-model.md](02-physical-model.md) | The main model: equations, data, fitting, checks, scores, limits |
| [03-statistical-model.md](03-statistical-model.md) | The backup model and its audited results |
| [04-watchlist.md](04-watchlist.md) | How leads are found, and the current leads |
| [05-data.md](05-data.md) | Every dataset, its source, cleaning and licence; how to rebuild |
| [06-website.md](06-website.md) | Running, hosting and reading the site |
| [07-oxford.md](07-oxford.md) | Oxford context: Thames Water's plan, Port Meadow, the 19–24 Oct event |
| [08-prior-work.md](08-prior-work.md) | Prior work and our gap |
| [09-handover.md](09-handover.md) | State, decisions, next steps, gotchas |
| [sources.md](sources.md) | Every source opened |
| [archive/](archive/README.md) | Superseded plans and reviews |
