# San Juan County, New Mexico QPF Monitor

Adapted from [La Plata County QPF Monitor](https://github.com/Matthew-Richardson/la-plata-qpf-monitor), preserving WPC/NBM calculations, snow probabilities, operational change detection, and separate weather/river GroupMe messages.

## Local coverage

County boundary: **San Juan County, New Mexico, FIPS 35045**. NWS hourly timing: Farmington, Aztec, Bloomfield, and Shiprock (NWS Albuquerque).

| Catchment | USGS site | NOAA river point |
|---|---|---|
| San Juan at Farmington | 09365000 | FRMN5 |
| San Juan at Shiprock | 09368000 | SHRN5 |
| La Plata near Farmington | 09367500 | LPFN5 |
| Animas at Farmington | 09364500 | ARFN5 |
| Animas below Aztec | 09364010 | AZRN5 |

County precipitation/snow use the county boundary. Gauge QPF uses the **entire upstream USGS NLDI basin**, including areas outside county/state lines. HUC8/HUC10 tables include full watershed polygons and upstream HUC10 units within county-intersecting HUC8s. Nested catchments overlap; do not add their totals together.

River values use official NOAA NWPS forecasts. Aztec and La Plata may use a fresh, clearly labeled observation if no forecast series is published. Missing/stale sources never become zero risk. San Juan flows depend on Navajo Reservoir operations; catchment QPF does not predict reservoir releases or river crests.

## Products

- WPC area-weighted liquid-equivalent precipitation in inches: Day 1, Day 2, Day 3, Days 4–5, Days 6–7, and Days 1–7. County/catchment/watershed averages, ranges, valid periods and source issuance times. Areas outside mapped contours count as zero, a lower-bound approximation.
- NBM comparison: newest complete 00/06/12/18Z 168-hour deterministic cycle, hourly increments through hour 48 and non-overlapping six-hour increments through hour 168. County/catchment grid-point means; WPC remains the trend baseline. Rolling model validity periods can differ.
- WPC Days 1–3 probabilities for at least 4, 8, and 12 inches of snow, by USGS 3DEP elevation bands below 7,000 feet, 7,000–9,000 feet, and above 9,000 feet within the county. Day 4–7 snowfall depth is not inferred from QPF.
- County WPC excessive-rainfall outlooks Days 1–5, NWS hourly timing, and NOAA river guidance with official action/flood-stage categories.

Successful runs create `data/latest.md`, `data/latest.json`, and operational checks in `data/operational_latest.json`. LPC forecast/history files are not copied.

## Schedule and GroupMe setup

GitHub Actions checks at **6:30 AM and 6:30 PM America/Denver**, handling daylight saving time with four UTC cron candidates filtered to two local hours. GitHub can delay scheduled starts. This repository has its own schedule; the existing La Plata Rain Watch task continues independently.

Add the San Juan County bot as the repository Actions secret **GROUPME_BOT_ID** under **Settings → Secrets and variables → Actions**. Secrets do not copy between repositories. Until configured, scheduled/manual runs use preview mode, save operational output, print messages to the run log, and do not advance delivery state.

Manual run: **Actions → San Juan NM WPC QPF → Run workflow**. Code pushes validate and refresh forecasts. The original external-trigger convention is also supported: update `.chatgpt-trigger` with commit message `Trigger scheduled QPF check`. Disable GitHub cron before adding another active scheduler.

## SJC OEM briefing format

Delivery uses **two concise messages normally, three maximum**, each within GroupMe's 1,000-character limit. Larger briefings place local outlook details in a third message. Every used forecast includes its source issuance time; missing issuance times are labeled unavailable. Each river forecast retains its own issuance time, including when gauges have different cycles. USBR daily observations carry the observation date and are never described as a future release schedule.

Rain messages show **7-day | Day 1 | Day 2 | Day 3 | Days 4–5 | Days 6–7** precipitation averages, with actual forecast-period dates and Mountain Time/DST labels. Periods are not calendar days. Independently mapped WPC period totals may not sum exactly to the mapped seven-day total.

- Upper Animas above Durango, USGS 09361500.
- Additional Animas drainage between Durango and Farmington, excluding the upper basin.
- Full La Plata drainage above Farmington.
- Additional San Juan drainage between Navajo Dam and Farmington, excluding both Navajo's upstream basin and the entire Animas basin.
- Additional San Juan drainage between Farmington and Shiprock (including tributary drainage added along that reach).
- Navajo upstream precipitation is shown with reservoir operations. Navajo's basin is delineated using the NLDI dam outlet flowline, COMID 17040463, located from USBR's dam coordinates. NLDI drainage boundaries approximate the outlet and may differ slightly from published drainage areas.

These are **separate area-average precipitation depths: do not add them**. The combined Animas basin average remains visible for context. Geographic polygons are subtracted and validated for nesting; precipitation averages are recalculated over each resulting polygon. No average is produced by subtracting two other averages. Small discrepancies between independently delineated NLDI boundaries are clipped; materially non-nested basins stop the calculation.

USBR Navajo daily storage, computed inflow, total release and change in storage are read from the official 40-day operations table. Missing/malformed data and records older than three days are flagged unavailable. A current daily release is not a scheduled future release. The detailed reports retain NBM comparisons (including the new divided areas), the Aztec observation, full gauge catchments and HUC tables; brief GroupMe texts focus on SJC operationally relevant totals and four river forecast points, including La Plata.

## Notification rules

- Wet: seven-day county average ≥0.50 inches, any gauge-catchment average ≥1.00 inch, or mapped ≥10% chance of ≥4 inches of snow in Days 1–3.
- Wet periods: weather first, separate river text second, morning and evening even when unchanged. Unchanged duplicate runs in the same slot are suppressed.
- Material WPC change: county/catchment average changes ≥0.25 inches versus last delivered values, labeled increased/decreased/mixed. Snow probability/elevation changes also trigger updates.
- Dry: county <0.25 inches, every gauge and divided catchment <0.50 inches, and no mapped snow signal on two consecutive successful runs. Routine messages then pause.
- River triggers: ≥20% and 100 cfs change, stage-category crossing, or peak-time shift ≥6 hours for flows ≥500 cfs. NWS timing uses sustained ≥50% hourly precipitation chance and ≥6-hour shifts.
- Quiet hours: **9 PM–6 AM Mountain**, including forced manual runs. Forecasts can refresh, but delivery baselines remain unchanged.
- Delivery state advances after successful delivery. Unavailable sources preserve prior values; partial sends can repeat on retry. River guidance older than 36 hours and hourly forecasts older than 24 hours are excluded; observations must be within six hours.

Messages use SJC OEM headings, plain text, local dates/times and issuance timestamps. Composition enforces a maximum of three texts without silently truncating a forecast; if a briefing cannot fit, delivery fails and the previous delivery baseline is preserved. Forecast liquid precipitation is not observed rain, flood probability, or a routed river forecast.

## Local validation

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python qpf_monitor.py
python snow_monitor.py
python groupme_notify.py --preview
```

Preview never sends messages or saves delivery state. Normal notification runs require GROUPME_BOT_ID when a message is due.

