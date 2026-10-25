# Plan review

## Overall

The data plan is strong. The plan as a whole has one big gap and a few things that won't fit together as written. You've done the hard sourcing work, and the "why" next to each dataset shows you know what each one is for. But the methodology is the project, and it's still a black box. It also decides which of your datasets you actually need.

## What's working

- The data list is well thought out. Including forecasts, ground wetness and infiltration shows you understand why spills happen, beyond just "it rained".
- The outputs answer real decisions: whether to swim, and where to invest.
- Spreading danger along the river instead of in a circle is the correct choice, and many student projects get it wrong.

## Problems to fix before modelling

1. **EDM measures how long a spill lasts, not how much spills.** Most overflows only log start and stop times. Your first output, "how much overflow", will have to be spill duration or probability. The exception is the works where your third link gives storm discharge volumes. Decide which one you're predicting.
2. **The time steps don't match.** Rainfall comes every 15 minutes, EDM events are timestamped, and Thames Water volumes are daily. Pick one modelling step (hourly or daily) and convert everything to it. Daily is easier; hourly is better for the swim advice.
3. **Many overflows aren't at a treatment works.** Storm overflows in the sewer network have no "processing capacity" or treated-volume figure. Your input of current processing capacity only applies at works, so you'll need a different approach for overflows in the network.
4. **Flow direction matters for Port Meadow.** As far as I know, Oxford STW is at Sandford, downstream of the city. If so, its spills can't reach Port Meadow, and the overflows that matter for that bathing water are the upstream ones. Check this early, because it changes which sites the swim model depends on.
5. **There's very little bacteria data to check against.** Bathing water sampling is roughly weekly, May to September, so about 20 samples a year. That's enough for a sanity check but not for calibrating the model. Present the swim model as driven by assumptions and say so.
6. **Missing source: Thames Water's near-real-time storm overflow API** (the live EDM map data). It gives you current overflow status for a live prediction demo.

## Suggested way to fill the black box

### Spill model: use two layers

- **Baseline:** a classifier (logistic regression, then gradient boosting) predicting the chance of a spill per overflow per day. Features would be rainfall summed over the last 1h, 6h, 24h, 72h and 7 days, plus groundwater level, soil moisture and season. Hold out one whole year for testing, and compare against a plain "rain above X mm" rule. If you can't beat that rule, you haven't learned anything.
- **Bucket model for the works:** inflow = foul flow + rain × catchment area × runoff coefficient + groundwater seepage, and a spill happens when inflow exceeds flow to full treatment plus storm tank storage. Fit the few parameters to the EDM data.

The bucket model is what gets you the third output. To see which works would benefit most from more capacity, enlarge each works' storage or treatment capacity in the model, rerun it, and rank the works by spill hours avoided per unit of added capacity. A pure machine-learning model can't answer that question.

### Swim heatmap

A 1D model along the river:

```
concentration = (spill load ÷ river flow) × exp(−die-off rate × travel time)
travel time   = distance ÷ flow speed
```

Only apply it downstream of each discharge point. Compare the results to the inland bathing water classification thresholds, and frame the result as a risk level, not "safe to swim".

### Wildlife list

Keep this as a short closing section (ammonia, low oxygen, fish kills). Don't build a model for it.

## Order of work

1. Download and clean the EDM start/stop data and rainfall, then join them on one time step.
2. Build the baseline classifier with an honest held-out test.
3. Build the bucket model for 2–3 key works, then run the capacity comparison.
4. Build the swim heatmap.
5. Add the forecast input and the live demo.

Steps 1–3 are already a complete project. Treat 4–5 as extras if you run short of time.

## Open question

What's the deadline and the format (report, presentation or app)? That decides how far down the list it's realistic to get.
