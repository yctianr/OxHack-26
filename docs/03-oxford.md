# 03 · Oxford specifics

## Thames Water Oxford GISMP (verified in the PDF)

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

## Overflows to model

Permit IDs come from the Thames Water API and the EA 2025 return. The API lists **46 monitors** in a roughly 35 × 35 km box around Oxford; use about 20–30.

| Overflow | Permit | Receiving water | 2025 EA (counted spills / h) | Note |
| --- | --- | --- | --- | --- |
| Oxford STW (Sandford) | TEMP.2827 | Pottery Stream → Thames | 43 / 590.5 | Main target; tagged "Asset configuration"; TDV available |
| West Way, Botley (Syphon) | TEMP.3035 | Seacourt Stream | 10 / 40 | City CSO |
| The Willows, North Hinksey Lane | TEMP.2973 | Seacourt Stream | 7 / 47.75 | City CSO |
| Littlemore Low Level (Heyford Hill Lane SPS) | TEMP.1358 | Thames | 1 / 6.07 | Pumping station |
| Cassington STW | TEMP.2457 | Thames | 0 / 0 | **The only overflow the EA links to the Wolvercote Mill Stream bathing water** |
| Islip STW | CTCR.1313 | River Ray → Cherwell | 34 / 696.75 | GW inundation |
| Wheatley STW | CSSC.2332 | Wheatley Ditch → Thame | 76 / 1,124.75 | GW inundation |
| Standlake STW | TEMP.2906 | Windrush | 98 / 2,213.75 | GW inundation |
| Church Hanborough STW | CSSC.5783 | Evenlode tributary | 88 / 1,236 | GW inundation |
| Witney STW | (see API) | Windrush / Colwell Brook | 37 / 576 | GW inundation |

## Port Meadow

- Wolvercote Mill Stream bathing water `ukj1402-11946`, designated 2022, **classified Poor in 2025**.
- Samples are weekly in season and posted about 5 days late. There is no EA forecast outside May–Sep.
- Only Cassington is formally linked. Port Meadow is **upstream** of the city CSOs and of Oxford STW at Sandford, so its sewage risk comes from upstream works (Cassington, Eynsham, Witney/Windrush, Evenlode) and from diffuse sources. Say so honestly.

## This week (live data, 19–24 Oct 2026)

- **Rain at Osney** (15-min feed, calendar days): 20 Oct 19.2 mm, 21 Oct 8.6, 22 Oct 3.6, 23 Oct 19.8, 24 Oct 11.8 so far. About 63 mm in total, after about 4 mm on 1–19 Oct.
- **16 local overflows spilled.** The longest were:
  - Church Hanborough: 7 events, 59.5 h
  - Weston-on-the-Green STW: 15.2 h
  - Grendon Underwood: 13.2 h
  - Wheatley: 11 h
  - Bicester: 10.5 h
- **Oxford STW** spilled once, 13:30–21:45 on 23 Oct (8.2 h).
- This is a clean **out-of-sample live test**: a dry start, then a wet spell.
