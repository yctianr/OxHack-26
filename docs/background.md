# Background: prior work, Oxford context and sources

## Prior work and the gap


**Gap:** no open tool tells a regulator which works spill when the physics says they shouldn't. Existing work maps spills after they happen, detects them retrospectively at a few works, explains drivers across sites, or is proprietary.

| Work | What it does | What it doesn't |
| --- | --- | --- |
| [Hammond et al. 2021, npj Clean Water](https://doi.org/10.1038/s41545-021-00108-3). Hammond is WASP's data scientist. | ML on daily effluent flow at 2 treatment works. AUC > 96% for spill vs no-spill. Flagged 926 of 7,160 "no-spill" days as likely spills, suggesting non-compliant discharges in 2009–2020. | Retrospective detection only; no groundwater; 2 sites |
| [Maes-Prior, Dobson & Mijic 2026, WST](https://www.citedrive.com/en/discovery/drivers-of-wastewater-dynamics-a-statistical-analysis-of-englands-large-wastewater-treatment-works/) | Linear regression + random forest over 951 English sewersheds. Precipitation dominates per-capita flow and spill occurrence. | Cross-sectional drivers; no forecast or decisions |
| [WWCompose preprint](https://www.researchsquare.com/article/rs-10040792/v1) (abstract only, not peer reviewed) | Splits daily influent into rainfall, soil-moisture and groundwater parts for about 2,900 English works. Mean KGE 0.68. | Models flow, not spills. **Closest to our bucket model: cite it and position against it.** |
| [StormHarvester × Southern Water](https://swan-forum.com/case-studies/stormharvester-southern-water-case-study/) | Per-site ML with hyperlocal rain. 25% of spills came from infiltration sites, which tracked groundwater level and its rate of change. Those sites spilled continuously Jan–Apr on small rain and stayed dry in summer after big storms. | Proprietary; no metrics published |
| EA short-term pollution risk prediction (bathing water API) | Daily normal / increased flag at Wolvercote Mill Stream, May–Sep | Binary, seasonal, mostly rain-driven, method not public. **A baseline to beat.** |
| [POOPy](https://github.com/AlexLipp/POOPy) / sewagemap.co.uk (Lipp, Dawe, Balaji) | Live EDM for all companies + downstream river trace on a D8 flow grid | Descriptive only; no dilution or flow. Reuse its downstream trace. |
| [Top of the Poops](https://www.top-of-the-poops.org/explore) | League tables. Explore view animates rain under overflow dots and **labels days "Dry spill", "Still spilling", "Wet spell: more sewage than the rain explains"** (verified live) | **Already does anomaly flagging**, so our unexplained-spill feature is not new. No forecast and no calibrated probability. |
| [WASP](https://www.ofwat.gov.uk/wp-content/uploads/2023/05/WASP-Response-to-Ofwat-consultation-on-storm-overflows.-1.pdf) | Joins EDM with rainfall to flag spills outside permit conditions | Rules-based; no groundwater; not probabilistic |
| Thames Water Oxford GISMP | Eyeballs monthly rainfall against monthly spills | Concludes there is "insufficient evidence to support the validity of this correlation". |

Closest prior work: Hammond et al. (2 works, machine learning on effluent flow) and WWCompose (flow decomposition, no spills). Spillcast is open, covers every works in its area, never fits to spill records, forecasts, and turns its output into decisions.


## Oxford context

### Thames Water's Oxford groundwater plan (GISMP)

[Oxford Groundwater Impacted System Management Plan](https://www.thameswater.co.uk/media-library/home/about-us/regulation/drainage-reports/groundwater-infiltration-management-plans/oxford-groundwater-impacted-system-management-plan.pdf), 2021 with 2024 and 2025 addenda.

- **Scale:** Oxford and 21 other sites' STW serves a **PE of 356,000 people** through a mostly separate foul network of about **1,485 km**.
- **Geology:** the catchment is on Oxford Clay / West Walton Formation and the Beckley Sand Member, "**not designated principal aquifers**".
- **Groundwater indicator sites** chosen by Thames Water: **Cherwell at Botanic Gardens, Cherwell at Kings Mill, Thames at Iffley Lock, Thames at Osney Lock.**
  - Our 24 Oct check: the Thames lock headwater gauges are held within about ±0.15 m, so prefer the Cherwell gauges and river flow.
- **Groundwater flooding:** Grandpont and Botley/West Oxford flood from groundwater "as high river levels cause the groundwater to increase".
- **Spills at Oxford STW:**
  - 2022: 15 spills / 163.94 h
  - 2023: 133 / 2,095.75 h
  - 2024: 162 / 3,198.30 h
- **Other overflows in the plan:**
  - Botley Road CSO: 26 / 105.4 h (2023); 0 (2024)
  - North Hinksey Lane CSO: 11 / 96.25 h (2023); 8 / 61.3 h (2024)
- **Remediation, 2023/24:** 1,245 m CCTV, 1,000 m sewer lining, 18 manholes sealed.
- **Upgrade:** "A major upgrade is planned for Oxford STW, costing more than **£130m** … larger storm tanks". Completion date "yet to be confirmed".
- **Their analysis is monthly totals by eye.** The 2025 addendum says there is "insufficient evidence" for the rainfall–spill correlation at Oxford STW.

### Port Meadow bathing water

- Wolvercote Mill Stream bathing water `ukj1402-11946`, designated 2022, **classified Poor in 2025**.
- Samples are weekly in season and posted about 5 days late. There is no EA forecast outside May–Sep.
- Only Cassington is formally linked. Port Meadow is **upstream** of the city CSOs and of Oxford STW at Sandford, so its sewage risk comes from upstream works (Cassington, Eynsham, Witney/Windrush, Evenlode) and from diffuse sources. Say so honestly.

## Sources

### APIs and services called live (24 Oct 2026)

- Thames Water open data v2: `https://api.thameswater.co.uk/opendata/v2/discharge/status` and `/alerts` ([docs](https://docs.api.thameswater.co.uk/))
- [EA flood-monitoring API](https://environment.data.gov.uk/flood-monitoring/doc/reference): rainfall 256230TP, river gauges, `stageScale`
- [EA Hydrology API](https://environment.data.gov.uk/hydrology/): rainfall, groundwater, river level and flow
- [EA bathing water data](https://environment.data.gov.uk/doc/bathing-water.json)
- [EA EDM Storm Overflows 2025 FeatureServer](https://services3.arcgis.com/Bb8lfThdhugyc4G3/arcgis/rest/services/Event_Duration_Monitoring_Storm_Overflows_2025/FeatureServer/0)
- EA LIDAR Composite DTM and DSM WCS (`environment.data.gov.uk/spatialdata/lidar-composite-…/wcs`)
- [EA Flood Map for Planning Flood Zones OGC API](https://environment.data.gov.uk/spatialdata/flood-map-for-planning-flood-zones/ogc/features/v1)
- AWS Terrain Tiles; OpenFreeMap; OS Downloads API (Open Rivers, Open Map Local)
- Stream: Thames Water Storm Overflow Activity FeatureServer
- sewagemap downstream-impact GeoJSON
- OSM Overpass

### Datasets and documents opened

- [EA EDM start/stop detailed data](https://www.data.gov.uk/dataset/39ba1e24-69ca-4031-badf-e02649b74a7b/event-duration-monitoring-storm-overflow-start-stop-detailed-data)
- [Thames Water Oxford GISMP](https://www.thameswater.co.uk/media-library/home/about-us/regulation/drainage-reports/groundwater-infiltration-management-plans/oxford-groundwater-impacted-system-management-plan.pdf)
- [Thames Water FFT methodology (DWMP28)](https://www.thameswater.co.uk/media-library/os3lcdg4/treatment-works-compliance-fft.pdf)
- [EA: calculating dry weather flow](https://www.gov.uk/government/publications/calculating-dry-weather-flow-dwf-at-waste-water-treatment-works/calculating-dry-weather-flow-dwf-at-waste-water-treatment-works)
- [EA: environmental permits for storm overflows](https://www.gov.uk/government/publications/water-companies-environmental-permits-for-storm-overflows-and-emergency-overflows/water-companies-environmental-permits-for-storm-overflows-and-emergency-overflows)
- [Ofwat PR24 FD enhancement cost modelling appendix](https://www.ofwat.gov.uk/wp-content/uploads/2024/12/PR24-final-determinations-Expenditure-allowances-Enhancement-cost-modelling-appendix.pdf)
- [Southern Water SRN-DDR-050 infiltration case](https://www.southernwater.co.uk/media/ty4hzpov/srn-ddr-050-resilience-infiltration-enhancement-cost-evidence-case.pdf)
- [Southern Water answers to Havant council (no flow meters on overflows)](https://havant.moderngov.co.uk/documents/s48769/SWA%20Answers%20to%20Questions%20Raised%20on%2020%20Feb%202023.pdf) (search result)
- [SWAN: StormHarvester × Southern Water](https://swan-forum.com/case-studies/stormharvester-southern-water-case-study/)
- [Hammond et al. 2021, npj Clean Water](https://doi.org/10.1038/s41545-021-00108-3)
- [Maes-Prior, Dobson & Mijic 2026 (abstract)](https://www.citedrive.com/en/discovery/drivers-of-wastewater-dynamics-a-statistical-analysis-of-englands-large-wastewater-treatment-works/)
- [Mapzen/joerd data sources](https://github.com/tilezen/joerd/blob/master/docs/data-sources.md)
- [EA LIDAR DTM dataset](https://ckan.publishing.service.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f)
- [MapLibre color-relief example](https://maplibre.org/maplibre-gl-js/docs/examples/add-a-color-relief-layer/)
- [wastewater-catchment-areas](https://github.com/tillahoffmann/wastewater-catchment-areas)
- [POOPy](https://github.com/AlexLipp/POOPy)
- [Top of the Poops explore](https://www.top-of-the-poops.org/explore)
- [Yang et al. 2020, prism maps](https://ar5iv.arxiv.org/html/2006.14120)
- [Padilla et al. 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5626802)
- [Peachey, Morss et al. 2013](https://atmos.washington.edu/~robwood/papers/weather/prob-revised.pdf)
- [Kay et al. 2016](https://idl.uw.edu/papers/when-ish-is-my-bus)
- [Fernandes et al. 2018](https://idl.uw.edu/papers/uncertainty-bus)
- [Met Office warnings](https://weather.metoffice.gov.uk/guides/warnings)
- [CRWA flagging programme](https://www.crwa.org/flagging-program)
- [SAS Safer Seas & Rivers](https://apps.apple.com/gb/app/safer-seas-rivers-service/id1458786821)
- [KDE heatmap explainer](https://landscapearchaeology.org/?p=551)

### Search results only (not opened)

- [Thames Water TDV flow data page](https://www.thameswater.co.uk/about-us/performance/river-health/storm-discharge-and-flow-data)
- [WWCompose preprint](https://www.researchsquare.com/article/rs-10040792/v1)
- [SODRP summary (UNEP LEAP)](https://leap.unep.org/en/countries/gb/national-legislation/storm-overflows-discharge-reduction-plan)
- [Thames21 / ORIC capacity study](https://www.thames21.org.uk/2025/07/new-research-reveals-over-half-of-thames-waters-sewage-works-struggling-to-meet-demand/)
- [BGS Geology 50k WMS](https://www.bgs.ac.uk/technologies/web-map-services-wms/web-map-services-geology-50k/)
- [Stream National Storm Overflow Hub](https://www.streamwaterdata.co.uk/pages/the-national-storm-overflow-hub)

### Population data

- Wikipedia – List of civil parishes in Oxfordshire (2011 census) (https://en.wikipedia.org/wiki/List_of_civil_parishes_in_Oxfordshire)
- ONS – Cherwell census population change (https://www.ons.gov.uk/visualisations/censuspopulationchange/E07000177/)
- ONS – Vale of White Horse census area changes (https://cy.ons.gov.uk/visualisations/censusareachanges/E07000180)
- ONS – West Oxfordshire (https://www.ons.gov.uk/explore-local-statistics/areas/E07000181)
- ONS – South Oxfordshire (https://www.ons.gov.uk/explore-local-statistics/areas/E07000179-south-oxfordshire)
- Thames Water – Oxford STW report (https://www.thameswater.co.uk/media-library/l52df1pb/oxford-stw-report.pdf)
- planningsignal.co.uk – Standlake (https://www.planningsignal.co.uk/towns/standlake)

### Storm-tank volumes (opened 25 Oct 2026)

- [Find a Tender notice 2024/S 000-031739](https://www.find-tender.service.gov.uk/Notice/031739-2024), Thames Water, Oxford STW upgrade: storm tanks 6,831 → 18,167 m³ (also [notice 027435-2024](https://www.find-tender.service.gov.uk/Notice/027435-2024))
- [Hammond et al. 2021, npj Clean Water](https://doi.org/10.1038/s41545-021-00108-3) ([PDF](https://nora.nerc.ac.uk/id/eprint/529883/1/N529883JA.pdf)), Table 1: tank sizes for WWTP1 (Church Hanborough) and WWTP2 (Witney)
- [Written evidence WQR0020](https://committees.parliament.uk/writtenevidence/22257/html/) to the Environmental Audit Committee "Water quality in rivers" inquiry, Feb 2021, Table 3: actual tank volumes for 9 Windrush and Evenlode works ([archived copy](http://web.archive.org/web/20230202143503/https://committees.parliament.uk/writtenevidence/22257/html/))
- [EA Consented Discharges to Controlled Waters with Conditions](https://environment.data.gov.uk/api/file/download?fileDataSetId=a54fdea1-7769-4b22-a518-10d51fed6f33&fileName=Consented%20Discharges%20to%20Controlled%20Waters%20with%20Conditions.zip): no tank field
- [Thames Water: information about specific sites](https://www.thameswater.co.uk/about-us/performance/river-health/frequently-asked-questions/information-about-specific-sites): no tank volumes; storm-tank increases at Chalgrove, Finstock, Cholsey and Drayton
